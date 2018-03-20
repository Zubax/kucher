#!/bin/bash

pip install -r requirements.txt || exit 1

pyinstaller --clean --noconfirm pyinstaller.spec || exit 2
