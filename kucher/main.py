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
import atexit
import logging
import datetime

import data_dir
import version

if sys.version_info[:2] < (3, 6):
    raise ImportError('A newer version of Python is required')

try:
    # noinspection PyUnresolvedReferences
    sys.getwindowsversion()
    RUNNING_ON_WINDOWS = True
except AttributeError:
    RUNNING_ON_WINDOWS = False

#
# Configuring logging before other packages are imported
#
if '--debug' in sys.argv:
    sys.argv.remove('--debug')
    LOGGING_LEVEL = logging.DEBUG
else:
    LOGGING_LEVEL = logging.INFO

logging.basicConfig(stream=sys.stderr,
                    level=LOGGING_LEVEL,
                    format='%(asctime)s pid=%(process)-5d %(levelname)s: %(name)s: %(message)s')

logging.getLogger('quamash').setLevel(logging.INFO)

_logger = logging.getLogger(__name__.replace('__', ''))

#
# Configuring the third-party modules
#
SOURCE_PATH = os.path.abspath(os.path.dirname(__file__))
LIBRARIES_PATH = os.path.join(SOURCE_PATH, 'libraries')

sys.path.insert(0, SOURCE_PATH)
sys.path.insert(0, os.path.join(LIBRARIES_PATH))
sys.path.insert(0, os.path.join(LIBRARIES_PATH, 'popcop', 'python'))
sys.path.insert(0, os.path.join(LIBRARIES_PATH, 'construct'))
sys.path.insert(0, os.path.join(LIBRARIES_PATH, 'dataclasses'))
sys.path.insert(0, os.path.join(LIBRARIES_PATH, 'quamash'))

#
# Now we can import the other modules, since the path is now configured and the third-party libraries are reachable.
#
import asyncio
from PyQt5.QtWidgets import QApplication
from quamash import QEventLoop

from fuhrer import Fuhrer


def main():
    data_dir.init()

    # Only the main process will be logging into the file
    log_file_name = os.path.join(data_dir.LOG_DIR, f'{datetime.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.log')
    file_handler = logging.FileHandler(log_file_name)
    file_handler.setLevel(LOGGING_LEVEL)
    file_handler.setFormatter(logging.Formatter('%(asctime)s pid=%(process)-5d %(levelname)-8s %(name)s: %(message)s'))
    logging.root.addHandler(file_handler)

    if '--profile' in sys.argv:
        try:
            # noinspection PyPep8Naming
            import cProfile as profile
        except ImportError:
            import profile

        def save_profile():
            prof.disable()
            prof.dump_stats(log_file_name.replace('.log', '.pstat'))

        prof = profile.Profile()
        atexit.register(save_profile)
        prof.enable()

    if '--test' in sys.argv:
        if not os.environ.get('PYTHONASYNCIODEBUG'):
            raise RuntimeError('PYTHONASYNCIODEBUG should be set while unit testing')

        import pytest
        args = sys.argv[:]
        args.remove('--test')
        args.append('--ignore=' + LIBRARIES_PATH)
        args.append('--capture=no')
        args.append('--fulltrace')
        args.append('-vv')
        args.append('.')
        return pytest.main(args)

    # Configuring the event loop
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Running the application
    _logger.info('Starting version %r', version.__version__)
    with loop:
        ctrl = Fuhrer()
        loop.run_until_complete(ctrl.run())


if __name__ == '__main__':
    sys.exit(main())
