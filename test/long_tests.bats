# -*- bats-mode -*-

# shellcheck disable=SC2046

bats_require_minimum_version 1.5.0
load common.bash

@test "autoware" {
    rm -rf ws # we don't use our simple workspace
    git clone https://github.com/autowarefoundation/autoware.git
    cd autoware
    mkdir -p src
    vcs import src < repositories/autoware.repos
    cd ..

    ros2nix --output-as-nix-pkg-name --fetch $(find -name package.xml|grep -v ament_cmake)
}
