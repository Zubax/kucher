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

from popcop.standard import NodeInfoMessage
import dataclasses
import typing
import datetime

_struct_view = dataclasses.dataclass(frozen=True)


@_struct_view
class SoftwareVersion:
    major: int
    minor: int

    build_timestamp_utc: datetime.datetime

    vcs_commit_id: int
    image_crc: int

    release_build: bool
    dirty_build: bool

    @staticmethod
    def populate(prototype: NodeInfoMessage):
        return SoftwareVersion(
            major=prototype.software_version_major,
            minor=prototype.software_version_minor,
            build_timestamp_utc=prototype.software_build_timestamp_utc,
            vcs_commit_id=prototype.software_vcs_commit_id,
            # We don't want None here, the field is supposed to be always available
            image_crc=prototype.software_image_crc or 0,
            release_build=prototype.software_release_build,
            dirty_build=prototype.software_dirty_build,
        )


@_struct_view
class HardwareVersion:
    major: int
    minor: int

    @staticmethod
    def populate(prototype: NodeInfoMessage):
        return HardwareVersion(
            major=prototype.hardware_version_major,
            minor=prototype.hardware_version_minor,
        )


@_struct_view
class MathRange:
    min: float
    max: float


@_struct_view
class Characteristics:
    @_struct_view
    class Capabilities:
        number_of_can_interfaces:             int
        battery_eliminator_circuit_available: bool

    @_struct_view
    class VSIModel:
        @_struct_view
        class HBR:
            high: float
            low:  float

        resistance_per_phase:                     typing.Tuple[HBR, HBR, HBR]
        gate_ton_toff_imbalance:                  float
        phase_current_measurement_error_variance: float

    @_struct_view
    class Limits:
        @_struct_view
        class AbsoluteMaximumRatings:
            vsi_dc_voltage:    MathRange

        @_struct_view
        class SafeOperatingArea:
            vsi_dc_voltage:    MathRange
            vsi_dc_current:    MathRange
            vsi_phase_current: MathRange
            cpu_temperature:   MathRange
            vsi_temperature:   MathRange

        @_struct_view
        class PhaseCurrentZeroBiasLimit:
            low_gain:  float
            high_gain: float

        absolute_maximum_ratings:      AbsoluteMaximumRatings
        safe_operating_area:           SafeOperatingArea
        phase_current_zero_bias_limit: PhaseCurrentZeroBiasLimit

        @staticmethod
        def populate(msg: typing.Mapping):
            amr = msg['absolute_maximum_ratings']
            soa = msg['safe_operating_area']
            return Characteristics.Limits(
                absolute_maximum_ratings=Characteristics.Limits.AbsoluteMaximumRatings(
                    vsi_dc_voltage=MathRange(**amr['vsi_dc_voltage']),
                ),
                safe_operating_area=Characteristics.Limits.SafeOperatingArea(
                    vsi_dc_voltage=MathRange(**soa['vsi_dc_voltage']),
                    vsi_dc_current=MathRange(**soa['vsi_dc_current']),
                    vsi_phase_current=MathRange(**soa['vsi_phase_current']),
                    cpu_temperature=MathRange(**soa['cpu_temperature']),
                    vsi_temperature=MathRange(**soa['vsi_temperature']),
                ),
                phase_current_zero_bias_limit=Characteristics.Limits.PhaseCurrentZeroBiasLimit(
                    low_gain=msg['phase_current_zero_bias_limit']['low_gain'],
                    high_gain=msg['phase_current_zero_bias_limit']['high_gain'],
                ),
            )

    capabilities: Capabilities
    vsi_model:    VSIModel
    limits:       Limits

    @staticmethod
    def populate(msg: typing.Mapping) -> 'Characteristics':
        caps = Characteristics.Capabilities(
            number_of_can_interfaces=int(msg['capability_flags']['doubly_redundant_can_bus']) + 1,
            battery_eliminator_circuit_available=msg['capability_flags']['battery_eliminator_circuit']
        )

        vsi_model = Characteristics.VSIModel(
            resistance_per_phase=tuple(map(lambda x: Characteristics.VSIModel.HBR(**x),
                                           msg['vsi_model']['resistance_per_phase'])),
            gate_ton_toff_imbalance=msg['vsi_model']['gate_ton_toff_imbalance'],
            phase_current_measurement_error_variance=msg['vsi_model']['phase_current_measurement_error_variance'],
        )

        return Characteristics(
            capabilities=caps,
            vsi_model=vsi_model,
            limits=Characteristics.Limits.populate(msg['limits'])
        )


def _unittest_characteristics_populating():
    from pytest import raises, approx

    sample = {
        'capability_flags': {'battery_eliminator_circuit': True,
                             'doubly_redundant_can_bus':   True},
        'limits':           {'absolute_maximum_ratings':      {'vsi_dc_voltage': {'max': 62.040000915527344,
                                                                                  'min': 4.0}},
                             'phase_current_zero_bias_limit': {'high_gain': 0.5,
                                                               'low_gain':  2.0},
                             'safe_operating_area':           {'cpu_temperature':   {'max': 355.1499938964844,
                                                                                     'min': 236.14999389648438},
                                                               'vsi_dc_current':    {'max': 25.0,
                                                                                     'min': -25.0},
                                                               'vsi_dc_voltage':    {'max': 51.0,
                                                                                     'min': 11.0},
                                                               'vsi_phase_current': {'max': 30.0,
                                                                                     'min': -30.0},
                                                               'vsi_temperature':   {'max': 358.1499938964844,
                                                                                     'min': 233.14999389648438}}},
        'vsi_model':        {'gate_ton_toff_imbalance':                  -1.1000000021965661e-08,
                             'phase_current_measurement_error_variance': 1.0,
                             'resistance_per_phase':                     [{'high': 0.004000000189989805,
                                                                           'low':  0.007000000216066837},
                                                                          {'high': 0.004000000189989805,
                                                                           'low':  0.007000000216066837},
                                                                          {'high': 0.004000000189989805,
                                                                           'low':  0.004000000189989805}]}
    }
    print('Sample:\n', sample, sep='')

    pop = Characteristics.populate(sample)
    print('Populated:\n', pop, sep='')

    with raises(dataclasses.FrozenInstanceError):
        pop.limits = 123

    assert pop.limits.safe_operating_area.vsi_dc_voltage.max == approx(51)
    assert pop.capabilities.number_of_can_interfaces == 2
    assert pop.vsi_model.gate_ton_toff_imbalance == approx(-11e-09)
    assert pop.vsi_model.resistance_per_phase[1].low == approx(0.007)


@_struct_view
class DeviceInfoView:
    name:                               str
    description:                        str
    build_environment_description:      str
    runtime_environment_description:    str
    software_version:                   SoftwareVersion
    hardware_version:                   HardwareVersion
    globally_unique_id:                 bytes
    certificate_of_authenticity:        bytes

    characteristics: Characteristics

    @staticmethod
    def populate(node_info_message: NodeInfoMessage,
                 characteristics_message: typing.Mapping) -> 'DeviceInfoView':
        return DeviceInfoView(
            name=node_info_message.node_name,
            description=node_info_message.node_description,
            build_environment_description=node_info_message.build_environment_description,
            runtime_environment_description=node_info_message.runtime_environment_description,
            software_version=SoftwareVersion.populate(node_info_message),
            hardware_version=HardwareVersion.populate(node_info_message),
            globally_unique_id=node_info_message.globally_unique_id,
            certificate_of_authenticity=node_info_message.certificate_of_authenticity,
            characteristics=Characteristics.populate(characteristics_message),
        )
