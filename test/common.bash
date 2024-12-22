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
