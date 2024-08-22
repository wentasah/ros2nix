#!/usr/bin/env python3

# Copyright 2019-2024 Ben Wolsieffer <benwolsieffer@gmail.com>
# Copyright 2024 Michal Sojka <michal.sojka@cvut.cz>

import argparse
import itertools
from catkin_pkg.package import parse_package_string
from rosinstall_generator.distro import get_distro
from superflore.PackageMetadata import PackageMetadata
from superflore.exceptions import UnresolvedDependency
from superflore.generators.nix.nix_package import NixPackage
from superflore.generators.nix.nix_expression import NixExpression, NixLicense
from superflore.utils import (download_file, get_distro_condition_context,
                              get_distros, get_pkg_version, info, resolve_dep,
                              retry_on_exception, warn)
from typing import Dict, Iterable, Set
from superflore.utils import err
from superflore.utils import ok
from superflore.utils import warn

org = "Open Source Robotics Foundation" # TODO change
org_license = "BSD"                     # TODO change


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


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("xml", help="Path to package.xml")
    args = parser.parse_args()

    try:
        distro_name = "humble"

        with open(args.xml, 'r') as f:
            package_xml = f.read()

        pkg = parse_package_string(package_xml)
        pkg.evaluate_conditions(NixPackage._get_condition_context(distro_name))

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

        derivation = NixExpression(
            name=NixPackage.normalize_name(pkg.name),
            version=pkg.version,
            src_url="src_uri",  # TODO
            src_sha256="src_sha256",
            description=pkg.description,
            licenses=map(NixLicense, pkg.licenses),
            distro_name=distro_name,
            build_type=pkg.get_build_type(),
            build_inputs=build_inputs,
            propagated_build_inputs=propagated_build_inputs,
            check_inputs=check_inputs,
            native_build_inputs=native_build_inputs)

    except Exception as e:
        err('Failed to generate derivation for package {}!'.format(pkg))
        raise e

    try:
        derivation_text = derivation.get_text(org, org_license)
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

    ok(f"Successfully generated derivation for package '{pkg.name}'.")
    try:
        with open('package.nix', "w") as recipe_file:
            recipe_file.write(derivation_text)
    except Exception as e:
        err("Failed to write derivation to disk!")
        raise e


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
