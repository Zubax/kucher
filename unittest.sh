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

# Add "--capture=no" to suppress stdout capture
pytest --ignore=kucher/libraries/pyqtgraph -v .
