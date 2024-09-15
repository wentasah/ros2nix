# ros2nix

Tool to convert [ROS][] `package.xml` to [Nix][] expressions
compatible with [nix-ros-overlay][].

This is work-in-progress. I'll add documentation after it works
reasonably well.

<!-- `$  python3 -m ros2nix --help` -->

```
usage: ros2nix [-h]
               [--output OUTPUT | --output-as-ros-pkg-name | --output-as-nix-pkg-name]
               [--output-dir OUTPUT_DIR] [--fetch] [--distro DISTRO]
               [--src-param SRC_PARAM] [--source-root SOURCE_ROOT]
               [--extra-build-inputs DEP1,DEP2,...]
               [--extra-propagated-build-inputs DEP1,DEP2,...]
               [--extra-check-inputs DEP1,DEP2,...]
               [--extra-native-build-inputs DEP1,DEP2,...] [--flake]
               [--nixfmt] [--compare] [--copyright-holder COPYRIGHT_HOLDER]
               [--license LICENSE]
               source [source ...]

positional arguments:
  source                Path to package.xml

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
                        current directory) (default: None)
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
  --nixfmt              Format the resulting expressions with nixfmt (default:
                        False)
  --compare             Don't write any file, but check whether writing the
                        file would change existing files. Exit with exit code
                        2 if a change is detected. Useful for CI. (default:
                        False)
  --copyright-holder COPYRIGHT_HOLDER
  --license LICENSE     License of the generated Nix expression, e.g. 'BSD'
                        (default: None)
```

[ROS]: https://www.ros.org/
[Nix]: https://nixos.org/
[nix-ros-overlay]: https://github.com/lopsided98/nix-ros-overlay

<!-- Local Variables: -->
<!-- compile-command: "mdsh" -->
<!-- End: -->
