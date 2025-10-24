# ros2nix

Tool that simplifies using [ROS][] with the [Nix][] package manager,
compatible with [nix-ros-overlay][]. It has two main use cases:

- Converting ROS `package.xml` files to Nix expressions so that you
  can build your ROS packages with Nix.

- Creating Nix-based development environment for compiling ROS
  workspaces with e.g. `colcon`. The environment contains all
  dependencies declared in `package.xml` files in the workspace.

Under the hood, `ros2nix` uses [rosdep][] to convert ROS package names
to nixpkgs attributes, so that you don't have to be concerned with it.

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
   This also creates `./shell.nix` for development in the local
   workspace and `./overlay.nix` and `./default.nix` for easy
   integration and/or testing of created Nix packages.

2. To build the local workspace with `colcon`, run:

   ```sh
   nix-shell
   colcon build
   ```

   If `nix-shell` fails, it might be due to missing packages in
   `nixpkgs` or `nix-ros-overlay`. Feel free to submit a bug or
   provide the package in `extraPkgs` argument as shown below.

3. To build some of your packages with Nix, replace `my-package` with
   a real name and run:

   ```sh
   nix-build -A rosPackages.humble.my-package
   nix-build -A rosPackages.jazzy.my-package
   ```
   Build failures can be caused by several things:
   - Missing dependencies in your `package.xml`
   - Missing/stale `nixos` keys for nixpkgs packages in [rosdep yaml database][]
   - Bugs in your packages (e.g. in `CMakeLists.txt`)
   - Bugs in `ros2nix` – please, report them
   - Bugs in `nix-ros-overlay` – report them too :-)

[rosdep yaml database]: https://github.com/ros/rosdistro/tree/master/rosdep

### Nixifying 3rd party ROS packages

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

   This will create all Nix expressions in the current directory. The
   files will be named according to their package names. The
   expressions will _fetch_ the source code from GitHub instead of
   from the local filesystem. Note that we ignore ament_cmake packages
   forked by autoware since they break the build.

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

3. If some packages need changes, you can generate Nix expressions
   with appropriate patches. Commit the needed changes and run
   `ros2nix` with the `--patches` flag, e.g.:

   ```sh
   pushd autoware/src/...package...
   $EDITOR some-file.cxx
   git commit some-file.cxx
   popd
   ros2nix --output-as-nix-pkg-name --fetch --patches $(find -name package.xml|grep -v ament_cmake)
   ```

   An example of the resulting Nix expression can be seen
   [here](https://github.com/wentasah/autoware.nix/blob/68772be6c4c263cfa213921e205f27f68dc4826a/pkgs/autoware-universe-utils.nix#L15-L18).

[Autoware]: https://autoware.org/

## Working with development environments

By default, `ros2nix` generates `shell.nix` file, which declares
development environment for compilation of your workspace. In the
simplest case, you can enter it by running `nix-shell` and run
`colcon`. For greater flexibility, you can extend it as described
below.

### ROS distribution

By default, `nix-shell` environment will contain the ROS distribution
which was specified by the `--distro` option passed to `ros2nix`,
which defaults to `rolling`. If you want to change it, rerun `ros2nix`
with different `--distro=...` value.

Alternatively, you can override the default distribution when invoking
`nix-shell`:

    nix-shell --argstr rosDistro jazzy

### Adding other packages

The generated `shell.nix` has three parameters `withPackages`,
`extraPkgs` and `extraPaths` that allows you to extend or modify the
development environment.

Use `withPackages` to add additional packages to the environment.
Define a Nix function, which returns the packages from the given
package set (`p` below):

    nix-shell --arg withPackages 'p: with p; [ compressed-image-transport ]'

This ensures that `compressed-image-transport` plugin will be
available in your development environment. You can use more space
separated packages inside `[ ]`. You can use any [ROS
package](https://index.ros.org/) (just replace `_` with `-`) or any
package from [nixpkgs](https://search.nixos.org/packages). If a
package with the same name is present in both ROS and nixpkgs, the ROS
package takes precedence.

Parameters `extraPkgs` and `extraPaths` are meant for programmatic use
and are described in the next section.

### Making the changes permanent

To make the changes permanent, create a new file, say `my-shell.nix`
and import the generated `shell.nix` as follows:

```nix
import ./shell.nix {
  withPackages = p: with p; [ compressed-image-transport ];
}
```

Then enter the extended environment by running:

    nix-shell my-shell.nix

A similar effect can be achieved with the `extraPaths` parameter. It
gives you full control over the packages. For example, you can
explicitly specify a package from nixpkgs (or other repository) even
if a same-named ROS package would override it when using
`withPackages`.

```nix
{
  nix-ros-overlay ? builtins.fetchTarball "https://github.com/lopsided98/nix-ros-overlay/archive/master.tar.gz",
  pkgs ? import nix-ros-overlay { },
  sterm ? builtins.fetchTarball "https://github.com/wentasah/sterm/archive/refs/heads/master.tar.gz",
}:
import ./shell.nix {
  inherit pkgs;
  extraPaths = [
    pkgs.clang-tools
    (import sterm { inherit pkgs; })
  ];
}
```

The above example adds to the development environment `clangd` (from
`clang-tools` in nixpkgs) and `sterm` tool from a 3rd party
repository.

### Providing missing dependencies

If your ROS packages depend on a package, which is neither in ROS nor
in nixpkgs, `nix-shell` fails with errors like: `error: undefined
variable 'my-package`. You can use the `extraPkgs` parameter to
provide such missing packages. For example:

```nix
{
  nix-ros-overlay ? builtins.fetchTarball "https://github.com/lopsided98/nix-ros-overlay/archive/master.tar.gz",
  pkgs ? import nix-ros-overlay { },
}:
import ./shell.nix {
  inherit pkgs;
  extraPkgs = {
    my-package = pkgs.callPackage ./my-package { };
    broken-package = null;
  };
}
```

This ensures that `my-package` will be available in the environment as
defined in `./my-package/default.nix`. Additionally, `broken-package`
will be replaced with `null`, which can be useful for resolving build
failures in optional dependencies.

### Running graphical applications

Since Nix environments aim to be completely independent from your host
system (unless it's NixOS), Nix-compiled programs don't use user space
portions of graphics drivers from your host distribution. Therefore,
running most graphical applications like `rviz2` fails. There are
multiple possible solutions, but we recommend using
[nix-system-graphics][].

If you have Intel or AMD GPU, follow their [install
instructions][nix-system-graphics-install]. In a nutshell:

1. Store `flake.nix` from their README into an empty directory.
2. Run there `nix run 'github:numtide/system-manager' -- switch --flake .`.

This will create a few files in `/etc/systemd/system` that will create
`/run/opengl-driver` (location where Nix programs expect graphics
drivers).

If you have NVIDIA GPU, the setup is more complex because you need to
manually select the same version of the driver as the one used by the
kernel of your host system.

[nix-system-graphics]: https://github.com/soupglasses/nix-system-graphics
[nix-system-graphics-install]: https://github.com/soupglasses/nix-system-graphics?tab=readme-ov-file#installing-with-nix-flakes

### Automatically entering the environment

## ros2nix reference

<!-- `$  python3 -m ros2nix --help` -->

```
usage: ros2nix [-h] [--output OUTPUT | --output-as-ros-pkg-name |
               --output-as-nix-pkg-name] [--output-dir OUTPUT_DIR] [--fetch]
               [--use-per-package-src] [--patches | --no-patches]
               [--distro DISTRO] [--src-param SRC_PARAM]
               [--source-root SOURCE_ROOT] [--no-cache] [--do-check]
               [--extra-build-inputs DEP1,DEP2,...]
               [--extra-propagated-build-inputs DEP1,DEP2,...]
               [--extra-check-inputs DEP1,DEP2,...]
               [--extra-native-build-inputs DEP1,DEP2,...] [--flake]
               [--default | --no-default] [--overlay | --no-overlay]
               [--packages | --no-packages] [--shell | --no-shell]
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
  --use-per-package-src
                        When using --fetch, fetch only the package sub-
                        directory instead of the whole repo. For repos with
                        multiple packages, this will avoid rebuilds of
                        unchanged packages at the cost of longer generation
                        time. (default: False)
  --patches, --no-patches
                        Add local git commits not present in git remote named
                        "origin" to patches in the generated Nix expression.
                        Only allowed with --fetch. This option is experimental
                        and may be changed in the future. (default: None)
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
  --no-cache            Don't use cache of git checkout sha265 hashes across
                        generation runs. (default: False)
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
  --packages, --no-packages
                        Enforce/suppress generation of package Nix
                        expressions. (default: True)
  --shell, --no-shell   Generate shell.nix (default: True)
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

**Acknowledgment:**

This project was co-financed from the state budget by the Technology
agency of the Czech Republic under the project TN01000026 *Božek
Vehicle Engineering National Center of Competence*.

<a href="https://tacr.gov.cz/program/program-narodni-centra-kompetence/"><img width="400" height="109" alt="National Centres of Competence Programme_red_small" src="https://github.com/user-attachments/assets/15931535-8dcb-4d39-9d52-0ad1326fa203" /></a>


[ROS]: https://www.ros.org/
[Nix]: https://nixos.org/
[nix-ros-overlay]: https://github.com/lopsided98/nix-ros-overlay

<!-- Local Variables: -->
<!-- compile-command: "mdsh" -->
<!-- End: -->
