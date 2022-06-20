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

import typing
import datetime
from dataclasses import dataclass

# This is an undesirable coupling, but it allows us to avoid excessive code duplication.
# We keep it this way while the codebase is new and fluid. In the future we may want to come up with an
# independent state representation in View, and add a converter into Fuhrer.
# noinspection PyUnresolvedReferences
from kucher.model.device_model import (
    GeneralStatusView,
    TaskStatisticsView,
    TaskID,
    TaskSpecificStatusReport,
    Commander,
)

# noinspection PyUnresolvedReferences
from kucher.model.device_model import (
    ControlMode,
    MotorIdentificationMode,
    LowLevelManipulationMode,
)

# noinspection PyUnresolvedReferences
from kucher.model.device_model import Register

from .utils import cached


_TASK_ID_TO_ICON_MAPPING: typing.Dict[TaskID, str] = {
    TaskID.IDLE: "sleep",
    TaskID.FAULT: "skull",
    TaskID.BEEP: "speaker",
    TaskID.RUN: "running",
    TaskID.HARDWARE_TEST: "pass-fail",
    TaskID.MOTOR_IDENTIFICATION: "caliper",
    TaskID.LOW_LEVEL_MANIPULATION: "hand-button",
}


@cached
def get_icon_name_for_task_id(tid: TaskID) -> str:
    try:
        return _TASK_ID_TO_ICON_MAPPING[tid]
    except KeyError:
        return "question-mark"


@cached
def get_human_friendly_task_name(tid: TaskID, multi_line=False, short=False) -> str:
    words = str(tid).split(".")[-1].split("_")
    out = " ".join([w.capitalize() for w in words])

    if short and (
        " " in out
    ):  # If short name requested, collapse multi-word names into acronyms
        out = "".join([w[0].upper() for w in out.split()])

    if multi_line:
        out = "\n".join(out.rsplit(" ", 1))

    return out


@cached
def get_human_friendly_control_mode_name_and_its_icon_name(
    control_mode: ControlMode, short=False
) -> typing.Tuple[str, str]:
    try:
        full_name, short_name, icon_name = {
            ControlMode.RATIOMETRIC_CURRENT: (
                "Ratiometric current",
                "%A",
                "muscle-percent",
            ),
            ControlMode.RATIOMETRIC_ANGULAR_VELOCITY: (
                "Ratiometric RPM",
                "%\u03C9",
                "rotation-percent",
            ),
            ControlMode.RATIOMETRIC_VOLTAGE: (
                "Ratiometric voltage",
                "%V",
                "voltage-percent",
            ),
            ControlMode.CURRENT: ("Current", "A", "muscle"),
            ControlMode.MECHANICAL_RPM: ("Mechanical RPM", "RPM", "rotation"),
            ControlMode.VOLTAGE: ("Voltage", "V", "voltage"),
        }[control_mode]
    except KeyError:
        return str(control_mode).split(".")[-1].replace("_", " "), "question-mark"
    else:
        return (short_name if short else full_name), icon_name


@dataclass
class SoftwareVersion:
    major: int = 0
    minor: int = 0

    build_timestamp_utc: datetime.datetime = datetime.datetime.utcfromtimestamp(0)

    vcs_commit_id: int = 0
    image_crc: int = 0

    release_build: bool = False
    dirty_build: bool = False


@dataclass
class HardwareVersion:
    major: int = 0
    minor: int = 0


@dataclass
class BasicDeviceInfo:
    name: str
    description: str
    build_environment_description: str
    runtime_environment_description: str
    software_version: SoftwareVersion
    hardware_version: HardwareVersion
    globally_unique_id: bytes
