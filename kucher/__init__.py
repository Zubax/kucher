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

from .version import *  # noqa
from .main import main  # noqa

#
# Configuring the third-party modules.
# The list of paths defined here can also be used by external packaging tools such as PyInstaller.
#
_SOURCE_PATH = os.path.abspath(os.path.dirname(__file__))
THIRDPARTY_PATH_ROOT = os.path.join(_SOURCE_PATH, 'libraries')

THIRDPARTY_PATH = [
    os.path.join(THIRDPARTY_PATH_ROOT),
    os.path.join(THIRDPARTY_PATH_ROOT, 'popcop', 'python'),
    os.path.join(THIRDPARTY_PATH_ROOT, 'construct'),
    os.path.join(THIRDPARTY_PATH_ROOT, 'qasync'),
]

# 'dataclasses' module is included in Python libraries since version 3.7. For Python versions below, the dataclass
# module located in the 'libraries' directory will be used. It is not compatible with Python 3.7, so we only declare
# its path if Python version is below 3.7. Otherwise, the built-in module will be used by default.
if sys.version_info[:2] < (3, 7):
    THIRDPARTY_PATH.append(os.path.join(THIRDPARTY_PATH_ROOT, 'dataclasses'))

for tp in THIRDPARTY_PATH:
    sys.path.insert(0, tp)
