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
import time
import errno
import threading
from logging import getLogger


_logger = getLogger(__name__)


if hasattr(sys, 'getwindowsversion'):
    _appdata_env = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA')
    USER_SPECIFIC_DATA_DIR = os.path.abspath(os.path.join(_appdata_env, 'Zubax', 'Kucher'))
else:
    USER_SPECIFIC_DATA_DIR = os.path.expanduser('~/.zubax/kucher')

LOG_DIR = os.path.join(USER_SPECIFIC_DATA_DIR, 'log')


_MAX_AGE_OF_LOG_FILE_IN_DAYS = 30
_MIN_USEFUL_LOG_FILE_SIZE = 1
_MAX_LOG_FILES_TO_KEEP = 50


def _create_directory(*path_items):
    try:
        os.makedirs(os.path.join(*path_items), exist_ok=True)
    except OSError as ex:
        if ex.errno != errno.EEXIST:  # http://stackoverflow.com/questions/12468022
            raise


def _old_log_cleaner():
    # noinspection PyBroadException
    try:
        _logger.info('Old log cleaner is waiting...')
        # This delay is needed to avoid slowing down application startup, when disk access rates may be high
        time.sleep(10)

        _logger.info('Old log cleaner is ready to work now')

        files_sorted_new_to_old = map(lambda x: os.path.join(LOG_DIR, x), os.listdir(LOG_DIR))
        files_sorted_new_to_old = list(sorted(files_sorted_new_to_old, key=lambda x: -os.path.getctime(x)))
        _logger.info('Log files found: %r', files_sorted_new_to_old)

        num_kept = 0
        num_removed = 0
        current_time = time.time()

        for f in files_sorted_new_to_old:
            creation_time = os.path.getctime(f)

            too_old = (current_time - creation_time) / (24 * 3600) >= _MAX_AGE_OF_LOG_FILE_IN_DAYS
            too_small = os.path.getsize(f) < _MIN_USEFUL_LOG_FILE_SIZE
            too_many = num_kept >= _MAX_LOG_FILES_TO_KEEP

            if too_old or too_small or too_many:
                # noinspection PyBroadException
                try:
                    os.unlink(f)
                except Exception:
                    _logger.exception('Could not remove file %r', f)
                else:
                    _logger.info(f'File {f} removed successfully; old={too_old} small={too_small} many={too_many}')
                    num_removed += 1
            else:
                num_kept += 1

        _logger.info('Background old log cleaner has finished successfully; total files removed: %r', num_removed)
    except Exception:
        _logger.exception('Background old log cleaner has failed')


def init():
    # noinspection PyBroadException
    try:
        _create_directory(USER_SPECIFIC_DATA_DIR)
        _create_directory(LOG_DIR)
    except Exception:
        _logger.exception('Could not create user-specific application data directories')

    # Fire and forget
    threading.Thread(target=_old_log_cleaner, name='old_log_cleaner', daemon=True).start()
