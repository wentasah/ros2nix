# ros2nix

Tool to convert [ROS][] `package.xml` to [Nix][] expressions
compatible with [nix-ros-overlay][]. Under the hood, it uses
[rosdep][] to convert ROS package names to nixpkgs attributes so that
you don't have to be concerned with it.

[rosdep]: https://github.com/ros-infrastructure/rosdep

## Installation

- With nix-env:
  ```sh
  nix-env --install -f https://github.com/wentasah/ros2nix/archive/main.tar.gz
  ```
  or try it out without installation:
  ```sh
  nix-shell -p '(import (fetchTarball "https://github.com/wentasah/ros2nix/archive/main.tar.gz")).default'
  ```

- With Nix flakes experimental feature:
  ```sh
  nix profile install github:wentasah/ros2nix
  ```
  or try it out without installation:
  ```sh
  nix shell github:wentasah/ros2nix
  ```

## Usage examples

### Nixifying local ROS workspace

1. Create Nix expressions for local packages
   ```sh
   ros2nix $(find -name package.xml)
   ```
   This also creates `./overlay.nix` and `./default.nix` for easy
   integration and/or testing of created packages.

2. Try building some of your packages (replace `my-package` with real
   name):
   ```sh
   nix-build -A rosPackages.humble.my-package
   nix-build -A rosPackages.jazzy.my-package
   ```
   If the build succeeds, you're probably done. Failures can be caused
   by several things:
   - Missing dependencies in your `package.xml`
   - Missing/stale `nixos` keys for nixpkgs packages in [rosdep yaml database][]
   - Bugs in your packages (e.g. in `CMakeLists.txt`)
   - Bugs in `ros2nix` – please, report them
   - Bugs in `nix-ros-overlay` – report them too :-)

[rosdep yaml database]: https://github.com/ros/rosdistro/tree/master/rosdep

## Nixifying 3rd party ROS packages

You can use 3rd party ROS packages (which are not a part of ROS
distribution) in your project as follows. We'll show the procedure on
the [Autoware][] project as an example.

1. Clone the 3rd party repositories, e.g.
   ```sh
   git clone https://github.com/autowarefoundation/autoware.git
   cd autoware
   mkdir src
   vcs import src < autoware.repos
   cd ..

   ros2nix --output-as-nix-pkg-name --fetch $(find -name package.xml|grep -v ament_cmake)
   ```
   This will create all Nix expressions in the current directory and
   named according to their package names. The expressions will
   _fetch_ the source code from GitHub instead of from local
   filesystem. Note that we ignore ament_cmake packages forked by
   autoware since they break the build.

2. Try building some packages:
   ```
   nix-build -A rosPackages.humble.autoware-overlay-rviz-plugin
   ```
   Note that not all autoware packages can be build successfully.

> [!TIP]
>
> To build all generated packages, run `ros2nix` with the `--flake`
> switch and then run `nix flake check` (depending on your
> configuration, you may need to add `--experimental-features
> 'nix-command flakes'`).

[Autoware]: https://autoware.org/

## ros2nix reference

<!-- `$  python3 -m ros2nix --help` -->
```
usage: ros2nix [-h]
               [--output OUTPUT | --output-as-ros-pkg-name | --output-as-nix-pkg-name]
               [--output-dir OUTPUT_DIR] [--fetch] [--distro DISTRO]
               [--src-param SRC_PARAM] [--source-root SOURCE_ROOT]
               [--do-check] [--extra-build-inputs DEP1,DEP2,...]
               [--extra-propagated-build-inputs DEP1,DEP2,...]
               [--extra-check-inputs DEP1,DEP2,...]
               [--extra-native-build-inputs DEP1,DEP2,...] [--flake]
               [--default | --no-default] [--overlay | --no-overlay]
               [--nix-ros-overlay FLAKEREF] [--nixfmt] [--compare]
               [--copyright-holder COPYRIGHT_HOLDER] [--license LICENSE]
               package.xml [package.xml ...]

positional arguments:
  package.xml           Path to package.xml

options:
  -h, --help            show this help message and exit
  --output OUTPUT       Output filename (default: package.nix)
  --output-as-ros-pkg-name
                        Name output files based on ROS package name, e.g.,
                        package_name.nix. Implies --output-dir=. (default:
                        False)
  --output-as-nix-pkg-name
                        Name output files based on Nix package name, e.g.,
                        package-name.nix. Implies --output-dir=. (default:
                        False)
  --output-dir OUTPUT_DIR
                        Directory to generate output files in. By default,
                        package files are stored next to their corresponding
                        package.xml, top-level files like overlay.nix in the
                        current directory. (default: None)
  --fetch               Use fetches like fetchFromGitHub in src attribute
                        values. The fetch function and its parameters are
                        determined from the local git work tree. sourceRoot
                        attribute is set if needed and not overridden by
                        --source-root. (default: False)
  --distro DISTRO       ROS distro (used as a context for evaluation of
                        conditions in package.xml, in the name of the Nix
                        expression and in flake.nix). Note that the generated
                        Nix expression can be used with any ROS distro if its
                        package.xml contains no conditions. (default: rolling)
  --src-param SRC_PARAM
                        Adds a parameter to the generated function and uses it
                        as a value of the src attribute (default: None)
  --source-root SOURCE_ROOT
                        Set sourceRoot attribute value in the generated Nix
                        expression. Substring '{package_name}' gets replaced
                        with the package name. (default: None)
  --do-check            Set doCheck attribute to true (default: False)
  --extra-build-inputs DEP1,DEP2,...
                        Additional dependencies to add to the generated Nix
                        expressions (default: [])
  --extra-propagated-build-inputs DEP1,DEP2,...
                        Additional dependencies to add to the generated Nix
                        expressions (default: [])
  --extra-check-inputs DEP1,DEP2,...
                        Additional dependencies to add to the generated Nix
                        expressions (default: [])
  --extra-native-build-inputs DEP1,DEP2,...
                        Additional dependencies to add to the generated Nix
                        expressions (default: [])
  --flake               Generate top-level flake.nix instead of default.nix.
                        Use with --fetch if some package.xml files are outside
                        of the flake repo (default: False)
  --default, --no-default
                        Enforce/suppress generation of default.nix (default:
                        None)
  --overlay, --no-overlay
                        Generate overlay.nix (default: True)
  --nix-ros-overlay FLAKEREF
                        Flake reference of nix-ros-overlay. You may want to
                        change the branch from master to develop or use your
                        own fork. (default: github:lopsided98/nix-ros-
                        overlay/master)
  --nixfmt              Format the resulting expressions with nixfmt (default:
                        False)
  --compare             Don't write any file, but check whether writing the
                        file would change existing files. Exit with exit code
                        2 if a change is detected. Useful for CI. (default:
                        False)
  --copyright-holder COPYRIGHT_HOLDER
                        Copyright holder of the generated Nix expressions.
                        (default: None)
  --license LICENSE     License of the generated Nix expressions, e.g. 'BSD'
                        (default: None)
```

[ROS]: https://www.ros.org/
[Nix]: https://nixos.org/
[nix-ros-overlay]: https://github.com/lopsided98/nix-ros-overlay

<!-- Local Variables: -->
<!-- compile-command: "mdsh" -->
<!-- End: -->
