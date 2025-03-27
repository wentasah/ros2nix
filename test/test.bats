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

@test "--output-as-nix-pkg-name" {
    ros2nix --output-as-nix-pkg-name $(find ws/src -name package.xml)
    assert [ -f ros-node.nix ]
    assert [ -f library.nix ]
    nix-build -A rosPackages.jazzy.ros-node
}

@test "--output-as-ros-pkg-name" {
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
    assert_line --partial "Cannot read ws/src/ros_node/package.nix"
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
