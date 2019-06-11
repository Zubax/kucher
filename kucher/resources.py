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

if getattr(sys, 'frozen', False):
    # https://pythonhosted.org/PyInstaller/runtime-information.html
    # noinspection PyUnresolvedReferences, PyProtectedMember
    PACKAGE_ROOT = sys._MEIPASS
else:
    PACKAGE_ROOT = os.path.dirname(os.path.abspath(__file__))


def get_absolute_path(*relative_path_items: str, check_existence=False) -> str:
    out = os.path.abspath(os.path.join(PACKAGE_ROOT, *relative_path_items)).replace('\\','/')
    if check_existence:
        if not os.path.exists(out):
            raise ValueError(f'The specified path does not exist: {out}')

    return out
