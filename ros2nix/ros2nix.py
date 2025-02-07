#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

# Copyright 2019-2024 Ben Wolsieffer <benwolsieffer@gmail.com>
# Copyright 2024 Michal Sojka <michal.sojka@cvut.cz>

from os.path import dirname
import argcomplete, argparse
import difflib
import io
import itertools
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from textwrap import dedent, indent
from typing import Iterable, Set, List

from catkin_pkg.package import Package, parse_package_string
from superflore.exceptions import UnresolvedDependency
from superflore.generators.nix.nix_package import NixPackage
from superflore.utils import err, ok, resolve_dep, warn

from .nix_expression import NixExpression, NixLicense


def resolve_dependencies(deps: Iterable[str]) -> Set[str]:
    return set(itertools.chain.from_iterable(map(resolve_dependency, deps)))


def resolve_dependency(d: str) -> Iterable[str]:
    try:
        # Try resolving as system dependency via rosdep
        return resolve_dep(d, "nix")[0]
    except UnresolvedDependency:
        # Assume ROS or 3rd-party package
        return (NixPackage.normalize_name(d),)


# Adapted from rosdistro.dependency_walker.DependencyWalker._get_dependencies()
def get_dependencies_as_set(pkg, dep_type):
    deps = {
        "build": pkg.build_depends,
        "buildtool": pkg.buildtool_depends,
        "build_export": pkg.build_export_depends,
        "buildtool_export": pkg.buildtool_export_depends,
        "exec": pkg.exec_depends,
        "run": pkg.run_depends,
        "test": pkg.test_depends,
        "doc": pkg.doc_depends,
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


compare_failed = False


@contextmanager
def file_writer(path: str, compare: bool):
    # Code to acquire resource, e.g.:
    f = open(path, "w") if not compare else io.StringIO()
    try:
        yield f
    finally:
        if compare:
            global compare_failed
            ondisk = None
            try:
                ondisk = open(path, "r", encoding="utf-8").read()
            except Exception as e:
                compare_failed = True
                err(f'Cannot read {path}: {e}')

            current = f.getvalue()
            if ondisk is not None and current != ondisk:
                err(f"{path} is not up-to-date")
                for line in difflib.unified_diff(
                    ondisk.splitlines(),
                    current.splitlines(),
                    fromfile=path,
                    tofile="up-to-date",
                ):
                    print(line)
                compare_failed = True
        f.close()


def generate_overlay(expressions: dict[str, str], args):
    with file_writer(f'{args.output_dir or "."}/overlay.nix', args.compare) as f:
        print("final: prev:\n{", file=f)
        for pkg in sorted(expressions):
            expr = (
                expressions[pkg]
                if args.output_dir is None
                else f"./{os.path.basename(expressions[pkg])}"
            )
            print(f"  {pkg} = final.callPackage {expr} {{}};", file=f)
        print("}", file=f)


ros_distro_overlays_def = dedent(
    """
    applyDistroOverlay =
      rosOverlay: rosPackages:
      rosPackages
      // builtins.mapAttrs (
        rosDistro: rosPkgs: if rosPkgs ? overrideScope then rosPkgs.overrideScope rosOverlay else rosPkgs
      ) rosPackages;
    rosDistroOverlays = final: prev: {
      # Apply the overlay to multiple ROS distributions
      rosPackages = applyDistroOverlay (import ./overlay.nix) prev.rosPackages;
    };
"""
).strip()


def flakeref_to_expr(flakeref) -> str:
    match flakeref[0]:
        case '.' | '/':
            expr = flakeref
        case _:
            match re.match("(?P<type>.*?):(?P<owner>.*?)/(?P<repo>.*?)(?:/(?P<ref>.*))?$", flakeref):
                case None:
                    raise Exception(f'Unsupported flakeref: "{flakeref}"')
                case parts:
                    match parts.groups():
                        case ('github', owner, repo, None):
                            expr = f'builtins.fetchTarball "https://github.com/{owner}/{repo}/archive/HEAD.tar.gz"'
                        case ('github', owner, repo, branch):
                            expr = f'builtins.fetchTarball "https://github.com/{owner}/{repo}/archive/{branch}.tar.gz"'
                        case _:
                            raise Exception(f'Unsupported flakeref: "{flakeref}"')
    return expr


def generate_default(args):
    nix_ros_overlay = flakeref_to_expr(args.nix_ros_overlay)
    with file_writer(f'{args.output_dir or "."}/default.nix', args.compare) as f:
        f.write(f'''{{
  nix-ros-overlay ? {nix_ros_overlay},
}}:
let
{indent(ros_distro_overlays_def, "  ")}
in
import nix-ros-overlay {{
  overlays = [ rosDistroOverlays ];
}}
''')


def generate_flake(args):
    with file_writer(f'{args.output_dir or "."}/flake.nix', args.compare) as f:
        f.write('''
{
  inputs = {
    nix-ros-overlay.url = "''' + args.nix_ros_overlay + '''";
    nixpkgs.follows = "nix-ros-overlay/nixpkgs";  # IMPORTANT!!!
  };
  outputs = { self, nix-ros-overlay, nixpkgs }:
    nix-ros-overlay.inputs.flake-utils.lib.eachDefaultSystem (system:
      let
''' + indent(ros_distro_overlays_def, "        ") + '''
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            nix-ros-overlay.overlays.default
            rosDistroOverlays
          ];
        };
''' + f'''
        rosDistro = "{args.distro}";
''' + '''
      in {
        legacyPackages = pkgs.rosPackages;
        packages = builtins.intersectAttrs (import ./overlay.nix null null) pkgs.rosPackages.${rosDistro};
        checks = builtins.intersectAttrs (import ./overlay.nix null null) pkgs.rosPackages.${rosDistro};
        devShells.default = pkgs.mkShell {
          name = "Example project";
          packages = [
            pkgs.colcon
            # ... other non-ROS packages
            (with pkgs.rosPackages.${rosDistro}; buildEnv {
              paths = [
                ros-core
                # ... other ROS packages
              ];
            })
          ];
        };
      });
  nixConfig = {
    extra-substituters = [ "https://ros.cachix.org" ];
    extra-trusted-public-keys = [ "ros.cachix.org-1:dSyZxI8geDCJrwgvCOHDoAfOm5sV1wCPjBkKL+38Rvo=" ];
  };
}
''')


def comma_separated(arg: str) -> list[str]:
    return [i.strip() for i in arg.split(",")]


def strip_empty_lines(text: str) -> str:
    return os.linesep.join([s for s in text.splitlines() if s and not s.isspace()])

def ros2nix(args):
    parser = argparse.ArgumentParser(
        prog="ros2nix", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("source", nargs="+", metavar="package.xml", help="Path to package.xml").completer = \
        argcomplete.completers.FilesCompleter(("xml"))

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", default="package.nix", help="Output filename")
    group.add_argument(
        "--output-as-ros-pkg-name",
        action="store_true",
        help="Name output files based on ROS package name, e.g., package_name.nix. Implies --output-dir=.",
    )
    group.add_argument(
        "--output-as-nix-pkg-name",
        action="store_true",
        help="Name output files based on Nix package name, e.g., package-name.nix. Implies --output-dir=.",
    )

    parser.add_argument(
        "--output-dir",
        help="Directory to generate output files in. "
        "By default, package files are stored next to their corresponding package.xml, "
        "top-level files like overlay.nix in the current directory.",
    )

    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Use fetches like fetchFromGitHub in src attribute values. "
        "The fetch function and its parameters are determined from the local git work tree. "
        "sourceRoot attribute is set if needed and not overridden by --source-root.",
    )

    parser.add_argument(
        "--use-package-git-hash",
        action="store_true",
        help="When using --fetch, use the git hash of the package sub-directory instead of the one of the upstream repo."
        "This will lead to longer generation time and multiple source checkouts when building but will safe rebuilds of packages that have not changed."
    )
    parser.add_argument(
        "--patches",
        action=argparse.BooleanOptionalAction,
        help="""Add local git commits not present in git remote named "origin" to patches in the """
        """generated Nix expression. Only allowed with --fetch. This option is experimental """
        """and may be changed in the future.""",
    )
    parser.add_argument(
        "--distro",
        default="rolling",
        help="ROS distro (used as a context for evaluation of conditions "
        "in package.xml, in the name of the Nix expression and in flake.nix). "
        "Note that the generated Nix expression can be used with any ROS distro if its package.xml contains no conditions.",
    )
    parser.add_argument(
        "--src-param",
        help="Adds a parameter to the generated function and uses it as a value of the src attribute",
    )
    parser.add_argument(
        "--source-root",
        help="Set sourceRoot attribute value in the generated Nix expression. "
        "Substring '{package_name}' gets replaced with the package name.",
    )
    parser.add_argument(
        "--do-check",
        action="store_true",
        help="Set doCheck attribute to true",
    )

    parser.add_argument(
        "--extra-build-inputs", type=comma_separated, metavar="DEP1,DEP2,...", default=[],
        help="Additional dependencies to add to the generated Nix expressions",
    )
    parser.add_argument(
        "--extra-propagated-build-inputs", type=comma_separated, metavar="DEP1,DEP2,...", default=[],
        help="Additional dependencies to add to the generated Nix expressions",
    )
    parser.add_argument(
        "--extra-check-inputs", type=comma_separated, metavar="DEP1,DEP2,...", default=[],
        help="Additional dependencies to add to the generated Nix expressions",
    )
    parser.add_argument(
        "--extra-native-build-inputs", type=comma_separated, metavar="DEP1,DEP2,...", default=[],
        help="Additional dependencies to add to the generated Nix expressions",
    )

    parser.add_argument(
        "--flake",
        action="store_true",
        help="Generate top-level flake.nix instead of default.nix. "
        "Use with --fetch if some package.xml files are outside of the flake repo",
    )
    parser.add_argument(
        "--default",
        action=argparse.BooleanOptionalAction,
        help="Enforce/suppress generation of default.nix",
    )
    parser.add_argument(
        "--overlay",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate overlay.nix",
    )
    parser.add_argument(
        "--nix-ros-overlay",
        metavar="FLAKEREF",
        default="github:lopsided98/nix-ros-overlay/master",
        help="Flake reference of nix-ros-overlay. You may want to change the branch from master to develop or use your own fork.",
    )
    parser.add_argument(
        "--nixfmt",
        action="store_true",
        help="Format the resulting expressions with nixfmt",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Don't write any file, but check whether writing the file would change existing files. "
        "Exit with exit code 2 if a change is detected. Useful for CI.",
    )

    parser.add_argument(
        "--copyright-holder", help="Copyright holder of the generated Nix expressions."
    )
    parser.add_argument(
        "--license", help="License of the generated Nix expressions, e.g. 'BSD'"
    )

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.output_dir is None and (args.output_as_nix_pkg_name or args.output_as_ros_pkg_name):
        args.output_dir = "."

    if args.patches and not args.fetch:
        err("--patches cannot be used without --fetch")
        return 1

    expressions: dict[str, str] = {}
    git_cache = {}
    patch_filenames = set()

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
            patches = []

            if args.src_param:
                kwargs["src_param"] = args.src_param
                kwargs["src_expr"] = args.src_param
            elif args.fetch:
                srcdir = os.path.dirname(source) or "."

                def check_output(cmd: List[str]):
                    return subprocess.check_output(cmd, cwd=srcdir).decode().strip()

                url = check_output("git config remote.origin.url".split())
                prefix = check_output("git rev-parse --show-prefix".split())
                toplevel = check_output("git rev-parse --show-toplevel".split())
                head = check_output("git rev-parse HEAD".split())

                def merge_base_to_upstream(commit: str) -> str:
                    return subprocess.check_output(f"git merge-base {head} $(git for-each-ref refs/remotes/origin --format='%(objectname)')", cwd=srcdir,shell=True).decode().strip()

                if args.use_package_git_hash:
                    # we need to get merge_base again to filter out applied patches from the package git hash
                    merge_base = merge_base_to_upstream(head)
                    head = check_output(f"git rev-list {merge_base} -1 -- .".split())

                if not args.use_package_git_hash and toplevel in git_cache: #only use cache if not using separate checkout per package
                    info = git_cache[toplevel]
                    upstream_rev = info["rev"]
                else:
                    # Latest commit present in the upstream repo. If
                    # the local repository doesn't have additional
                    # commits, it is the same as HEAD. Should work
                    # even with detached HEAD.
                    upstream_rev = merge_base_to_upstream(head)
                    info = json.loads(
                        subprocess.check_output(
                            ["nix-prefetch-git", "--quiet"]
                            + (
                                ["--sparse-checkout", prefix]
                                if prefix and args.use_package_git_hash
                                else []
                            )
                            + [toplevel, upstream_rev],
                        ).decode()
                    )
                    git_cache[toplevel] = info

                match = re.match("https://github.com/(?P<owner>[^/]*)/(?P<repo>.*?)(.git|/.*)?$", url)
                sparse_checkout = f"sparseCheckout = [\"{prefix}\"];" if (prefix and args.use_package_git_hash) else ""
                if match is not None:
                    kwargs["src_param"] = "fetchFromGitHub"
                    kwargs["src_expr"] = strip_empty_lines(dedent(f'''
                      fetchFromGitHub {{
                        owner = "{match["owner"]}";
                        repo = "{match["repo"]}";
                        rev = "{info["rev"]}";
                        sha256 = "{info["sha256"]}";
                        {sparse_checkout}
                      }}''')).strip()
                else:
                    kwargs["src_param"] = "fetchgit"
                    kwargs["src_expr"] = strip_empty_lines(dedent(f'''
                      fetchgit {{
                        url = "{url}";
                        rev = "{info["rev"]}";
                        sha256 = "{info["sha256"]}";
                        {sparse_checkout}
                      }}''')).strip()

                if prefix:
                    # kwargs["src_expr"] = f'''let fullSrc = {kwargs["src_expr"]}; in "${{fullSrc}}/{prefix}"'''
                    kwargs["source_root"] = f"${{src.name}}/{prefix}"

                if args.patches:
                    patches = subprocess.check_output(
                        dedent(f"""
                          for i in $(git rev-list --reverse --relative {upstream_rev}..HEAD -- .); do
                            git format-patch --zero-commit --relative --no-signature -1 $i
                          done"""),
                        shell=True, cwd=srcdir,
                    ).decode().strip().splitlines()
                elif head != upstream_rev:
                    warn(f"{toplevel} contains commits not available upstream. Consider using --patches")

            else:
                if args.output_dir is None:
                    kwargs["src_expr"] = "./."
                else:
                    kwargs["src_expr"] = f"./{os.path.dirname(os.path.relpath(source, args.output_dir)) or '.'}"

            if args.source_root:
                kwargs["source_root"] = args.source_root.replace('{package_name}', pkg.name)

            if args.do_check:
                kwargs["do_check"] = True

            derivation = NixExpression(
                name=NixPackage.normalize_name(pkg.name),
                version=pkg.version,
                description=pkg.description,
                licenses=map(NixLicense, pkg.licenses),
                distro_name=args.distro,
                build_type=pkg.get_build_type(),
                build_inputs=build_inputs | set(args.extra_build_inputs),
                propagated_build_inputs=propagated_build_inputs | set(args.extra_propagated_build_inputs),
                check_inputs=check_inputs | set(args.extra_check_inputs),
                native_build_inputs=native_build_inputs | set(args.extra_native_build_inputs),
                patches=[f"./{p}" for p in patches],
                **kwargs,
            )

        except Exception as e:
            err(f'Failed to prepare Nix expression from {source}')
            raise e

        try:
            our_cmd_line = " ".join(
                [os.path.basename(sys.argv[0])]
                + [
                    arg
                    for arg in sys.argv[1:]
                    if not (arg.endswith("package.xml") and os.path.isfile(arg))
                    and arg != "--compare"
                ]
            )
            derivation_text = f"# Automatically generated by: {our_cmd_line}\n"
            derivation_text += derivation.get_text(args.copyright_holder, args.license)
        except UnresolvedDependency as e:
            err(f"Failed to resolve required dependencies for package {pkg}!")
            raise e
        except Exception as e:
            err('Failed to generate derivation for package {}!'.format(pkg))
            raise e

        if args.nixfmt:
            nixfmt = subprocess.Popen(["nixfmt"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            derivation_text, _ = nixfmt.communicate(input=derivation_text)

        try:
            output_file_name = get_output_file_name(source, pkg, args)
            with file_writer(output_file_name, args.compare) as recipe_file:
                recipe_file.write(derivation_text)
            for patch in patches:
                patch_filename = os.path.join(dirname(output_file_name), patch)
                if not patch_filename in patch_filenames:
                    patch_filenames.add(patch_filename)
                else:
                    # TODO Allow better handling of patch name collisions (e.g. by
                    # having them in per-package directories, perhaps via
                    # --output_subdir_as_nix_pkg_name)
                    msg = f"Patch {patch_filename} already exists"
                    err(msg)
                    raise Exception(msg)
                with file_writer(patch_filename, args.compare) as patch_dest, \
                     open(os.path.join(os.path.dirname(source), patch), "r") as patch_src:
                    patch_dest.write(patch_src.read())
            if not args.compare:
                ok(f"Successfully generated derivation for package '{pkg.name}' as '{output_file_name}'.")

            expressions[NixPackage.normalize_name(pkg.name)] = output_file_name
        except Exception as e:
            err("Failed to write derivation to disk!")
            raise e

    if args.overlay:
        generate_overlay(expressions, args)

    if args.flake:
        generate_flake(args)
    if args.default or (args.default is None and not args.flake):
        generate_default(args)
        # TODO generate also release.nix (for testing/CI)?

    if args.compare and compare_failed:
        err("Some files are not up-to-date")
        return 2


def main():
    import sys
    return ros2nix(sys.argv[1:])


if __name__ == '__main__':
    sys.exit(main())
