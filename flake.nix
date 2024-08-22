{
  description = "A basic flake with a shell";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nix-ros-overlay.url = "github:lopsided98/nix-ros-overlay/master";
  inputs.nixpkgs.follows = "nix-ros-overlay/nixpkgs";

  outputs =
    { nixpkgs, flake-utils, nix-ros-overlay, ... }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ nix-ros-overlay.overlays.default ];
        };
      in
      {
        devShells.default = pkgs.mkShell {
          inputsFrom = [
          ];
          packages = [
            pkgs.bashInteractive
            pkgs.superflore
            pkgs.python3Packages.rosdep
          ];
        };
      }
    );
}
