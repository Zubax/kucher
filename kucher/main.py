#!/usr/bin/env python3
#
# Copyright (C) 2018 Zubax Robotics OU
#
# This file is part of Kucher.
# Kucher is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
# Kucher is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with Kucher.
# If not, see <http://www.gnu.org/licenses/>.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import os
import sys

if sys.version_info[:2] < (3, 6):
    raise ImportError('A newer version of Python is required')

SOURCE_PATH = os.path.abspath(os.path.dirname(__file__))
LIBRARIES_PATH = os.path.join(SOURCE_PATH, 'libraries')

sys.path.insert(0, SOURCE_PATH)
sys.path.insert(0, os.path.join(LIBRARIES_PATH))
sys.path.insert(0, os.path.join(LIBRARIES_PATH, 'popcop', 'python'))
sys.path.insert(0, os.path.join(LIBRARIES_PATH, 'construct'))
sys.path.insert(0, os.path.join(LIBRARIES_PATH, 'dataclasses'))

from model.device_model import DeviceModel


def main():
    if '--test' in sys.argv:
        import pytest
        args = sys.argv[:]
        args.remove('--test')
        args.append('--ignore=' + LIBRARIES_PATH)
        args.append('--capture=no')
        args.append('-vv')
        args.append('.')
        pytest.main(args)
        return 0


if __name__ == '__main__':
    sys.exit(main())
