#!/usr/bin/env python3
#
# Copyright (C) 2018 Zubax Robotics OU
#
# This file is part of Kucher.
#
# Kucher is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Kucher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Kucher.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import os
import sys

SOURCE_PATH = os.path.abspath(os.path.dirname(__file__))
LIBRARIES_PATH = os.path.join(SOURCE_PATH, 'libraries')

sys.path.append(os.path.join(LIBRARIES_PATH))
sys.path.append(os.path.join(LIBRARIES_PATH, 'popcop', 'python'))
