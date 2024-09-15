{
  description = "Tool to convert ROS package.xml to Nix expressions compatible with nix-ros-overlay";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nix-ros-overlay.url = "github:lopsided98/nix-ros-overlay/master";
  inputs.nixpkgs.follows = "nix-ros-overlay/nixpkgs";
  inputs.rosdistro = { url = "github:ros/rosdistro"; flake = false; };
  inputs.flake-compat.url = "https://flakehub.com/f/edolstra/flake-compat/1.tar.gz";

  outputs =
    { nixpkgs, flake-utils, nix-ros-overlay, ... } @ inputs:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ nix-ros-overlay.overlays.default ];
        };
        rosdistro = pkgs.stdenv.mkDerivation {
          pname = "rosdistro";
          version = inputs.rosdistro.lastModifiedDate;
          src = inputs.rosdistro;
          postPatch = ''
            substituteInPlace rosdep/sources.list.d/20-default.list \
              --replace-fail https://raw.githubusercontent.com/ros/rosdistro/master/ file://${placeholder "out"}/
          '';
          postInstall = ''
            mkdir -p $out
            cp -r * $out
          '';
        };
        rosdep-unwrapped = pkgs.python3Packages.rosdep.overrideAttrs ({ postPatch ? "", ...}: {
          postPatch = postPatch + ''
            substituteInPlace src/rosdep2/rep3.py \
              --replace-fail https://raw.githubusercontent.com/ros/rosdistro/master/ file://${rosdistro}/
          '';
        });
        rosdep-cache = pkgs.stdenv.mkDerivation {
          pname = "rosdep-cache";
          version = inputs.rosdistro.lastModifiedDate;
          nativeBuildInputs = [
            rosdep-unwrapped
          ];
          ROSDEP_SOURCE_PATH = "${rosdistro}/rosdep/sources.list.d";
          ROSDISTRO_INDEX_URL = "file://${rosdistro}/index-v4.yaml";
          ROS_HOME = placeholder "out";
          buildCommand = ''
            mkdir -p $out
            rosdep update
          '';
        };
        # rosdep with offline database
        rosdep = pkgs.python3Packages.rosdep.overrideAttrs ({ postFixup ? "", ...}: {
          postFixup = postFixup + ''
            wrapProgram $out/bin/rosdep --set-default ROS_HOME ${rosdep-cache}
          '';
        });
        ros2nix = pkgs.python3Packages.buildPythonApplication {
          pname = "ros2nix";
          version = inputs.self.lastModifiedDate;
          src = pkgs.lib.cleanSource ./.;
          pyproject = true;

          nativeBuildInputs = with pkgs.python3Packages; [
            setuptools
          ];
          propagatedBuildInputs = with pkgs; [
            git
            nix-prefetch-git
            nixfmt-rfc-style
            superflore
          ];
          makeWrapperArgs = [
            "--set-default ROS_HOME ${rosdep-cache}"
            "--set-default ROSDEP_SOURCE_PATH ${rosdistro}/rosdep/sources.list.d"
            "--set ROSDISTRO_INDEX_URL file://${rosdistro}/index-v4.yaml"
            "--set ROS_OS_OVERRIDE nixos"
          ];
        };
      in
      {
        devShells.default = pkgs.mkShell {
          inputsFrom = [
            ros2nix
          ];
          packages = [
            pkgs.bashInteractive
            pkgs.python3Packages.flake8
            pkgs.python3Packages.flake8-bugbear
          ];
          ROSDEP_SOURCE_PATH = "${rosdistro}/rosdep/sources.list.d";
          ROSDISTRO_INDEX_URL = "file://${rosdistro}/index-v4.yaml";
        };
        packages = {
          default = ros2nix;
          inherit rosdistro rosdep-cache rosdep ros2nix;
        };
      }
    );
}
