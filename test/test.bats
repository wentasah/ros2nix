# -*- bats-mode -*-

# shellcheck disable=SC2046

bats_require_minimum_version 1.5.0
bats_load_library bats-support
bats_load_library bats-assert
bats_load_library bats-file

setup_file() {
    # get the containing directory of this file
    # use $BATS_TEST_FILENAME instead of ${BASH_SOURCE[0]} or $0,
    # as those will point to the bats executable's location or the preprocessed file respectively
    DIR="$( cd "$( dirname "$BATS_TEST_FILENAME" )" >/dev/null 2>&1 && pwd )"
    export DIR
    # make executables in this directory visible to PATH
    PATH="$DIR:$PATH"
}

setup() {
    cd "$BATS_TEST_TMPDIR"
    cp -a "$DIR/ws" .
}

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
    ros2nix --flake $(find ws/src -name package.xml)
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
