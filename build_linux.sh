#!/bin/bash
#
# Before running this, make sure all PIP dependencies are installed.
#

sudo apt-get install patchelf -y
sudo apt install gcc
sudo apt-get install scons
sudo apt-get install -y liblzma-dev
pip install backports.lzma

pyinstaller --clean --noconfirm pyinstaller.spec || exit 2
cd staticx
scons
python setup.py install

# https://github.com/JonathonReinhart/staticx/issues/79
cd ../dist
mv Kucher Kucher.tmp
staticx --loglevel DEBUG Kucher.tmp Kucher

rm -rf *.tmp
cd ..
