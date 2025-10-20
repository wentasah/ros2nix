# -*- bats-mode -*-

# shellcheck disable=SC2046

bats_require_minimum_version 1.5.0
load common.bash

@test "ros2nix --help" {
    ros2nix --help
}

@test "fail on non-existent package.xml" {
    run ! ros2nix ./non-existent.xml
}

@test "nixify local workspace" {
    ros2nix $(find ws/src -name package.xml)
    nix-build -A rosPackages.humble.ros-node -A rosPackages.jazzy.ros-node -A rosPackages.rolling.ros-node
}

@test "nixify local workspace and build it by colcon in nix-shell" {
    cd ws
    ros2nix --distro=jazzy $(find src -name package.xml)
    nix-shell --run "colcon build"
}

@test "generate just shell.nix and build workspace by colcon in nix-shell" {
    cd ws
    ros2nix --distro=jazzy --output-as-nix-pkg-name \
            --no-packages --no-overlay --no-default \
            $(find src -name package.xml)
    assert [ -f shell.nix ]

    assert [ ! -f default.nix ]
    assert [ ! -f overlay.nix ]
    # Check that no packages were generated
    assert [ ! -f library.nix ]
    assert [ ! -f ros-node.nix ]

    nix-shell --run "colcon build"
}

@test "nix-shell for local workspace with additional ROS package" {
    ros2nix --distro=jazzy $(find ws/src -name package.xml)
    nix-shell --arg withPackages 'p: with p; [ compressed-image-transport ]' \
              --run "ros2 pkg list | grep compressed_image_transport"
}

@test "nix-shell for local workspace with additional nixpkgs package" {
    ros2nix --distro=jazzy $(find ws/src -name package.xml)
    nix-shell --arg withPackages 'p: with p; [ hello ]' \
              --run "which hello"
}

@test "nix-shell for local workspace with additional extraPaths" {
    cd ws
    ros2nix --distro=jazzy $(find src -name package.xml)
    cat <<EOF > my-shell.nix
{
  nix-ros-overlay ? builtins.fetchTarball "https://github.com/lopsided98/nix-ros-overlay/archive/master.tar.gz",
  pkgs ? import nix-ros-overlay { },
  sterm ? builtins.fetchTarball "https://github.com/wentasah/sterm/archive/refs/heads/master.tar.gz",
}:
import ./shell.nix {
  inherit pkgs;
  extraPaths = [
    (import sterm { inherit pkgs; })
  ];
}
EOF
    nix-shell my-shell.nix --pure --run "sterm -h"
}

@test "nix-shell for local workspace with additional extraPkgs" {
    cd ws
    ros2nix --distro=jazzy $(find src -name package.xml)
    cat <<EOF > my-shell.nix
{
  nix-ros-overlay ? builtins.fetchTarball "https://github.com/lopsided98/nix-ros-overlay/archive/master.tar.gz",
  pkgs ? import nix-ros-overlay { },
}:
import ./shell.nix {
  inherit pkgs;
  extraPkgs = {
    my-package = pkgs.writeScriptBin "my-script" ''
      echo "hi"
    '';
  };
}
EOF
    nix-shell my-shell.nix --pure --run "my-script"
}

@test "nix-shell for local workspace with extraShellHook" {
    ros2nix --distro=jazzy $(find ws/src -name package.xml)
    nix-shell --argstr extraShellHook 'VAR=123' \
              --run '[[ $VAR -eq 123 ]] || echo "VAR value incorrect"'
}

@test "nixify local workspace and build it by colcon in nix develop" {
    cd ws
    ros2nix --flake --distro=jazzy $(find src -name package.xml)
    nix develop --command colcon build
}

@test "nixify package in the current directory" {
    cd ws/src/library
    ros2nix package.xml
    nix-build -A rosPackages.jazzy.library
}

@test "--output-dir without --output-as" {
    run ! ros2nix --output-dir=nix $(find ws/src -name package.xml)
}

@test "--output-as-nix-pkg-name" {
    ros2nix --output-as-nix-pkg-name $(find ws/src -name package.xml)
    assert [ -f ros-node.nix ]
    assert [ -f library.nix ]
    nix-build -A rosPackages.jazzy.ros-node
}

@test "--output-as-nix-pkg-name with --output-dir" {
    ros2nix --output-as-nix-pkg-name --output-dir=nix $(find ws/src -name package.xml)
    assert [ -f nix/ros-node.nix ]
    assert [ -f nix/library.nix ]
    nix-build ./nix -A rosPackages.jazzy.ros-node
}

@test "--output-as-ros-pkg-name" {
    ros2nix --output-as-ros-pkg-name $(find ws/src -name package.xml)
    assert [ -f ros_node.nix ]
    assert [ -f library.nix ]
    nix-build -A rosPackages.jazzy.ros-node
}

@test "--output-as-pkg-dir" {
    ros2nix --output-as-ros-pkg-name $(find ws/src -name package.xml)
    assert [ -f ros_node.nix ]
    assert [ -f library.nix ]
    nix-build -A rosPackages.jazzy.ros-node
}

@test "--flake" {
    ros2nix --flake --distro=jazzy $(find ws/src -name package.xml)
    nix flake check path:"${PWD}"
    nix build path:"${PWD}#ros-node"
}

@test "--compare" {
    ros2nix $(find ws/src -name package.xml)
    ros2nix --compare $(find ws/src -name package.xml)
}

@test "--compare with changed package.xml" {
    ros2nix $(find ws/src -name package.xml)
    sed -i -e '4a<depend>libpng</depend>' ws/src/ros_node/package.xml
    run -2 ros2nix --compare $(find ws/src -name package.xml)
    assert_line "+  propagatedBuildInputs = [ libpng library ];"
}

@test "--compare with added package" {
    ros2nix ws/src/library/package.xml
    run -2 ros2nix --compare ws/src/{library,ros_node}/package.xml
    assert_line --partial "Some files are not up-to-date"
}

@test "--fetch from github over https" {
    git clone https://github.com/wentasah/ros2nix
    ros2nix --output-as-nix-pkg-name --fetch $(find "ros2nix/test/ws/src" -name package.xml)
    nix-build -A rosPackages.jazzy.ros-node
    run ./result/lib/ros_node/node
    assert_success
    assert_line --partial "hello world"
}

@test "--patches without --fetch" {
    run ! ros2nix --patches $(find ws/src -name package.xml)
}

@test "--fetch --patches" {
    git clone https://github.com/wentasah/ros2nix
    pushd ros2nix
    sed -i -e 's/hello world/hello patch/' test/ws/src/ros_node/src/node.cpp
    git commit -m 'test patch' -- test/ws/src/ros_node/src/node.cpp
    popd
    ros2nix --output-as-nix-pkg-name --fetch --patches $(find "ros2nix/test/ws/src" -name package.xml)
    # remove original (abd patched) sources
    rm -rf ros2nix
    nix-build -A rosPackages.jazzy.ros-node
    # validate that we get patched binary
    run ./result/lib/ros_node/node
    assert_success
    assert_line --partial "hello patch"
}

@test "--fetch --patches with colliding changes" {
    git clone https://github.com/wentasah/ros2nix
    pushd ros2nix
    sed -i -e 's/hello world/hello patch/' test/ws/src/ros_node/src/node.cpp
    git commit -m 'test patch' -- test/ws/src/ros_node/src/node.cpp
    sed -i -e '1a// comment' test/ws/src/library/src/library.cpp
    git commit -m 'test patch' -- test/ws/src/library/src/library.cpp
    popd
    run ros2nix --output-as-nix-pkg-name --fetch --patches $(find "ros2nix/test/ws/src" -name package.xml)
    assert_failure
    assert_line --partial "Patch ./0001-test-patch.patch already exists"
}

@test "--fetch --patches with two changes, each for different package " {
    git clone https://github.com/wentasah/ros2nix
    pushd ros2nix
    sed -i -e 's/hello world/hello patch/' test/ws/src/ros_node/src/node.cpp
    git commit -m 'node patch' -- test/ws/src/ros_node/src/node.cpp
    sed -i -e '1a// comment' test/ws/src/library/src/library.cpp
    git commit -m 'library patch' -- test/ws/src/library/src/library.cpp
    popd
    ros2nix --output-as-nix-pkg-name --fetch --patches $(find "ros2nix/test/ws/src" -name package.xml)
    assert_file_contains ./library.nix library-patch\.patch
    assert_file_contains ./ros-node.nix node-patch\.patch
    assert_file_not_contains ./library.nix node-patch\.patch
    assert_file_not_contains ./ros-node.nix library-patch\.patch
    nix-build -A rosPackages.jazzy.ros-node
}

@test "--use-per-package-src" {
    git clone https://github.com/wentasah/ros2nix
    ros2nix --output-as-nix-pkg-name --fetch --use-per-package-src $(find "ros2nix/test/ws/src" -name package.xml)
    nix-build -A rosPackages.jazzy.ros-node
    run ./result/lib/ros_node/node
    assert_success
    assert_line --partial "hello world"
}
