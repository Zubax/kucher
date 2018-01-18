#!/bin/bash
#
# Add more options via the environment variable PYTEST_ADDOPTS. For example:
#   PYTEST_ADDOPTS=--ignore=kucher/libraries ./unittest.sh
#

function die()
{
    if which cowsay &> /dev/null; then
        cowsay "$@" 1>&2
    else
        echo "$@" 1>&2
    fi
    exit 1
}

which pytest &> /dev/null || die "Install Pytest first: sudo pip3 install pytest"

next_option=''
while [ -n "$1" ]; do
    case $1 in
    --skip-third-party)
        export PYTEST_ADDOPTS="$PYTEST_ADDOPTS --ignore=kucher/libraries"
        ;;

    --verbose)
        export PYTEST_ADDOPTS="$PYTEST_ADDOPTS --capture=no -vv"
        ;;

    --help)
        echo "Options:"
        echo "  --help                  Show this help."
        echo "  --skip-third-party      Ignore unit tests of third-party code."
        echo "  --verbose               Enable verbose output."
        exit 0
        ;;

    *)
        die "Invalid option: $1; use --help to get help."
        ;;
    esac
    shift
done

pytest --ignore=kucher/libraries/pyqtgraph -v .
