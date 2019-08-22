#!/bin/bash
#
# Before running this, make sure all PIP dependencies are installed.
#

pyinstaller --clean --noconfirm pyinstaller.spec || exit 2
