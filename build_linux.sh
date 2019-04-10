#!/bin/bash
#
# Before running this, make sure all PIP dependencies are installed.
#

sudo apt-get install patchelf -y

pyinstaller --clean --noconfirm pyinstaller.spec || exit 2

# https://github.com/JonathonReinhart/staticx/issues/79
cd dist
mv Kucher Kucher.tmp
staticx --loglevel DEBUG Kucher.tmp Kucher

rm -rf *.tmp
