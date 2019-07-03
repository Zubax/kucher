#!/bin/bash
PYTHONPATH=kucher pytest

bash build_linux.sh
pycodestyle
