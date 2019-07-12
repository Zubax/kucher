#!/bin/bash
#
# Before running this, make sure all PIP dependencies are installed.
#

sudo apt-get install -y patchelf
sudo apt-get install -y gcc
sudo apt-get install -y scons
sudo apt-get install -y liblzma-dev
pip install backports.lzma

pyinstaller --clean --noconfirm pyinstaller.spec || exit 2
pushd kucher/libraries/staticx
scons
python setup.py install

# https://github.com/JonathonReinhart/staticx/issues/79
popd
pushd dist
mv Kucher Kucher.tmp
staticx --loglevel DEBUG Kucher.tmp Kucher

rm -rf *.tmp
popd
