#!/usr/bin/env python3

# Copyright 2019-2024 Ben Wolsieffer <benwolsieffer@gmail.com>
# Copyright 2024 Michal Sojka <michal.sojka@cvut.cz>

import os
import argparse
import itertools
import subprocess
from textwrap import dedent, indent
from catkin_pkg.package import parse_package_string, Package
from rosinstall_generator.distro import get_distro
from superflore.PackageMetadata import PackageMetadata
from superflore.exceptions import UnresolvedDependency
from superflore.generators.nix.nix_package import NixPackage
from .nix_expression import NixExpression, NixLicense
from superflore.utils import (download_file, get_distro_condition_context,
                              get_distros, get_pkg_version, info, resolve_dep,
                              retry_on_exception, warn)
from typing import Dict, Iterable, Set, reveal_type
from superflore.utils import err
from superflore.utils import ok
from superflore.utils import warn
import urllib.parse
import re
import json

def resolve_dependencies(deps: Iterable[str]) -> Set[str]:
    return set(itertools.chain.from_iterable(
        map(resolve_dependency, deps)))

def resolve_dependency(d: str) -> Iterable[str]:
    try:
        # Try resolving as system dependency via rosdep
        return resolve_dep(d, 'nix')[0]
    except UnresolvedDependency:
        # Assume ROS or 3rd-party package
        return (NixPackage.normalize_name(d),)

# Adapted from rosdistro.dependency_walker.DependencyWalker._get_dependencies()
def get_dependencies_as_set(pkg, dep_type):
    deps = {
        'build': pkg.build_depends,
        'buildtool': pkg.buildtool_depends,
        'build_export': pkg.build_export_depends,
        'buildtool_export': pkg.buildtool_export_depends,
        'exec': pkg.exec_depends,
        'run': pkg.run_depends,
        'test': pkg.test_depends,
        'doc': pkg.doc_depends,
    }
    return set([d.name for d in deps[dep_type] if d.evaluated_condition is not False])


def get_output_file_name(source: str, pkg: Package, args):
    if args.output_as_ros_pkg_name:
        fn = f"{pkg.name}.nix"
    elif args.output_as_nix_pkg_name:
        fn = f"{NixPackage.normalize_name(pkg.name)}.nix"
    else:
        fn = args.output
    dir = args.output_dir if args.output_dir is not None else os.path.dirname(source)
    return os.path.join(dir, fn)

def generate_overlay(expressions: dict[str, str], args):
    with open(f'{args.output_dir or "."}/overlay.nix', "w") as f:
        print("self: super:\n{", file=f)
        for pkg in sorted(expressions):
            expr = expressions[pkg] if args.output_dir is None else f"./{os.path.basename(expressions[pkg])}"
            print(f"  {pkg} = super.callPackage {expr} {{}};", file=f)
        print("}", file=f)

def generate_default(args):
    with open(f'{args.output_dir or "."}/default.nix', "w") as f:
        f.write('''{
  nix-ros-overlay ? builtins.fetchTarball "https://github.com/lopsided98/nix-ros-overlay/archive/master.tar.gz",
}:
let
  applyDistroOverlay =
    rosOverlay: rosPackages:
    rosPackages
    // builtins.mapAttrs (
      rosDistro: rosPkgs: if rosPkgs ? overrideScope then rosPkgs.overrideScope rosOverlay else rosPkgs
    ) rosPackages;
  rosDistroOverlays = self: super: {
    # Apply the overlay to multiple ROS distributions
    rosPackages = applyDistroOverlay (import ./overlay.nix) super.rosPackages;
  };
in
import nix-ros-overlay {
  overlays = [ rosDistroOverlays ];
}
''')

def generate_flake(args):
    with open(f'{args.output_dir or "."}/flake.nix', "w") as f:
        f.write('''
TODO
''')

def ros2nix(args):
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("source", nargs="+", help="Path to package.xml")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", default="package.nix", help="Output filename")
    group.add_argument("--output-as-ros-pkg-name", action="store_true", help="Name output file based on ROS package name, e.g., package_name.nix. Implies --output-dir=.")
    group.add_argument("--output-as-nix-pkg-name", action="store_true", help="Name output file based on Nix package name, e.g., package-name.nix. Implies --output-dir=.")

    parser.add_argument("--output-dir", help="Directory to generate output files in (by default, files are stored next to their corresponding package.xml)")

    parser.add_argument("--fetch", action="store_true", help="Use fetches like fetchFromGitHub for src attribute. "
                       "The fetch function and its parameters are determined from the local git work tree."
                       "sourceRoot is set if needed and not overridden by --source-root.")
    parser.add_argument("--distro", default="rolling",
                        help="ROS distro (used as a context for evaluation of conditions in package.xml and in the name of the Nix expression)")
    parser.add_argument("--src-param",
                        help="Parameter name in arguments of the generated function to be used as a src attribute")
    parser.add_argument("--source-root",
                        help="Set sourceRoot attribute value in the generated Nix expression. "
                        "Substring '{package_name}' gets replaced with the package name.")

    parser.add_argument("--flake", action="store_true", help="Generate top-level flake.nix instead of default.nix. "
                        "Use with --fetch if some package.xml files are outside of the flake repo.")
    parser.add_argument("--nixfmt", action="store_true", help="Format the resulting expressions with nixfmt")

    parser.add_argument("--copyright-holder")
    parser.add_argument("--license", help="License of the generated Nix expression, e.g. 'BSD'")

    args = parser.parse_args()

    if args.output_dir is None and (args.output_as_nix_pkg_name or args.output_as_ros_pkg_name):
        args.output_dir = "."

    expressions: dict[str, str] = {}
    git_cache = {}

    for source in args.source:
        try:
            with open(source, 'r') as f:
                package_xml = f.read()

            pkg = parse_package_string(package_xml)
            pkg.evaluate_conditions(NixPackage._get_condition_context(args.distro))

            buildtool_deps = get_dependencies_as_set(pkg, "buildtool")
            buildtool_export_deps = get_dependencies_as_set(pkg, "buildtool_export")
            build_deps = get_dependencies_as_set(pkg, "build")
            build_export_deps = get_dependencies_as_set(pkg, "build_export")
            exec_deps = get_dependencies_as_set(pkg, "exec")
            test_deps = get_dependencies_as_set(pkg, "test")

            # buildtool_depends are added to buildInputs and nativeBuildInputs.
            # Some (such as CMake) have binaries that need to run at build time
            # (and therefore need to be in nativeBuildInputs. Others (such as
            # ament_cmake_*) need to be added to CMAKE_PREFIX_PATH and therefore
            # need to be in buildInputs. There is no easy way to distinguish these
            # two cases, so they are added to both, which generally works fine.
            build_inputs = set(resolve_dependencies(
                build_deps | buildtool_deps))
            propagated_build_inputs = resolve_dependencies(
                exec_deps | build_export_deps | buildtool_export_deps)
            build_inputs -= propagated_build_inputs

            check_inputs = resolve_dependencies(test_deps)
            check_inputs -= build_inputs

            native_build_inputs = resolve_dependencies(
                buildtool_deps | buildtool_export_deps)

            kwargs = {}

            if args.src_param:
                kwargs["src_param"] = args.src_param
                kwargs["src_expr"] = args.src_param
            elif args.fetch:
                srcdir = os.path.dirname(source)
                url = subprocess.check_output(
                    "git config remote.origin.url".split(), cwd=srcdir
                ).decode().strip()

                prefix = subprocess.check_output(
                    "git rev-parse --show-prefix".split(), cwd=srcdir
                ).decode().strip()

                toplevel = subprocess.check_output(
                    "git rev-parse --show-toplevel".split(), cwd=srcdir
                ).decode().strip()

                if toplevel in git_cache:
                    info = git_cache[toplevel]
                else:
                    info = json.loads(
                        subprocess.check_output(
                            ["nix-prefetch-git", "--quiet", toplevel],
                        ).decode()
                    )
                    git_cache[toplevel] = info

                match = re.match("https://github.com/(?P<owner>[^/]*)/(?P<repo>.*?)(.git)?$", url)
                if match is not None:
                    kwargs["src_param"] = "fetchFromGitHub";
                    kwargs["src_expr"] = dedent(f'''
                      fetchFromGitHub {{
                        owner = "{match["owner"]}";
                        repo = "{match["repo"]}";
                        rev = "{info["rev"]}";
                        sha256 = "{info["sha256"]}";
                      }}''').strip()
                else:
                    kwargs["src_param"] = "fetchgit";
                    kwargs["src_expr"] = dedent(f'''
                      fetchgit {{
                        url = "{url}";
                        rev = "{info["rev"]}";
                        sha256 = "{info["sha256"]}";
                      }}''').strip()

                if prefix:
                    #kwargs["src_expr"] = f'''let fullSrc = {kwargs["src_expr"]}; in "${{fullSrc}}/{prefix}"'''
                    kwargs["source_root"] = f"${{src.name}}/{prefix}";

            else:
                if args.output_dir is None:
                    kwargs["src_expr"] = "./."
                else:
                    kwargs["src_expr"] = f"./{os.path.relpath(os.path.dirname(source), args.output_dir)}"

            if args.source_root:
                kwargs["source_root"] = args.source_root.replace('{package_name}', pkg.name)

            derivation = NixExpression(
                name=NixPackage.normalize_name(pkg.name),
                version=pkg.version,
                description=pkg.description,
                licenses=map(NixLicense, pkg.licenses),
                distro_name=args.distro,
                build_type=pkg.get_build_type(),
                build_inputs=build_inputs,
                propagated_build_inputs=propagated_build_inputs,
                check_inputs=check_inputs,
                native_build_inputs=native_build_inputs, **kwargs)

        except Exception as e:
            err('Failed to generate derivation for package {}!'.format(pkg))
            raise e

        try:
            derivation_text = derivation.get_text(args.copyright_holder, args.license)
        except UnresolvedDependency:
            err("'Failed to resolve required dependencies for package {}!"
                .format(pkg))
            unresolved = unresolved_dependencies
            for dep in unresolved:
                err(" unresolved: \"{}\"".format(dep))
            return None, unresolved, None
        except Exception as e:
            err('Failed to generate derivation for package {}!'.format(pkg))
            raise e

        if args.nixfmt:
            nixfmt = subprocess.Popen(["nixfmt"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            derivation_text, _ = nixfmt.communicate(input=derivation_text)

        try:
            output_file_name = get_output_file_name(source, pkg, args)
            with open(output_file_name, "w") as recipe_file:
                recipe_file.write(derivation_text)
                ok(f"Successfully generated derivation for package '{pkg.name}' as '{output_file_name}'.")

            expressions[NixPackage.normalize_name(pkg.name)] = output_file_name
        except Exception as e:
            err("Failed to write derivation to disk!")
            raise e

    generate_overlay(expressions, args)

    if args.flake:
        generate_flake(args)
    else:
        generate_default(args)

def main():
    import sys
    ros2nix(sys.argv[1:])

if __name__ == '__main__':
    main()
