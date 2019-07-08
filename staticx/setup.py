#!/usr/bin/env python
# Derived from https://github.com/JonathonReinhart/scuba
from __future__ import print_function
from setuptools import setup, Command, find_packages
from distutils.command.build import build
import os
from subprocess import check_call

from dynversion import get_dynamic_version


################################################################################
# Commands / hooks

class build_bootloader(Command):
    description = "Build staticx bootloader binary"

    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass

    def run(self):
        check_call(['scons'])


class build_hook(build):
    def run(self):
        self.run_command('build_bootloader')
        build.run(self)


################################################################################

setup(
    name = 'staticx',
    version = get_dynamic_version(),
    description = 'Build static self-extracting app from dynamic executable',
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Build Tools',
    ],
    license = 'GPL v2 with special exception allowing StaticX to build and'
              ' distribute non-free programs',
    author = 'Jonathon Reinhart',
    author_email = 'jonathon.reinhart@gmail.com',
    url = 'https://github.com/JonathonReinhart/staticx',
    packages = find_packages(),
    package_data = {
        'staticx': [
            'bootloader',
            'bootloader-debug',
        ],
    },

    # Ugh.
    # https://github.com/JonathonReinhart/staticx/issues/22
    # https://github.com/JonathonReinhart/scuba/issues/77
    # https://github.com/pypa/setuptools/issues/1064
    include_package_data = True,

    zip_safe = False,   # http://stackoverflow.com/q/24642788/119527
    entry_points = {
        'console_scripts': [
            'staticx = staticx.__main__:main',
        ]
    },
    install_requires = [
        'pyelftools',
        'backports.lzma;python_version<"3.3"',
    ],

    # http://stackoverflow.com/questions/17806485
    # http://stackoverflow.com/questions/21915469
    # PyInstaller setup.py
    cmdclass = {
        'build_bootloader': build_bootloader,
        'build':            build_hook,
    },
)
