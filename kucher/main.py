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
import logging

# Configuring logging before other packages are imported.
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


def main() -> int:
    """
    This is the main entry point of the application.
    We must import packages here, in the function, rather than globally, because the logging subsystem
    must be set up correctly at the import time.
    """
    import atexit
    import asyncio
    import datetime
    from PyQt5.QtWidgets import QApplication
    from quamash import QEventLoop
    from . import data_dir, version, resources
    from .fuhrer import Fuhrer

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

    # Configuring the event loop
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Running the application
    _logger.info('Starting version %r; package root: %r', version.__version__, resources.PACKAGE_ROOT)
    with loop:
        ctrl = Fuhrer()
        asyncio.run(ctrl.run())

    return 0
