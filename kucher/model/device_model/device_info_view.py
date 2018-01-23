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
    major: int = 0
    minor: int = 0

    build_timestamp_utc: datetime.datetime = datetime.datetime.fromtimestamp(0)

    vcs_commit_id: int = 0
    image_crc: int = 0

    release_build: bool = False
    dirty_build: bool = False

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
    major: int = 0
    minor: int = 0

    @staticmethod
    def populate(prototype: NodeInfoMessage):
        return HardwareVersion(
            major=prototype.hardware_version_major,
            minor=prototype.hardware_version_minor,
        )


@_struct_view
class MathRange:
    min: float = 0
    max: float = 0


@_struct_view
class Characteristics:
    @_struct_view
    class Capabilities:
        number_of_can_interfaces:             int = 0
        battery_eliminator_circuit_available: bool = False

    @_struct_view
    class VSIModel:
        @_struct_view
        class HBR:
            high: float = 0
            low:  float = 0

        resistance_per_phase:                     typing.Tuple[HBR, HBR, HBR] = (HBR(), HBR(), HBR())
        gate_ton_toff_imbalance:                  float = 0
        phase_current_measurement_error_variance: float = 0

    @_struct_view
    class Limits:
        @_struct_view
        class MeasurementRange:
            vsi_dc_voltage:    MathRange = MathRange()

        @_struct_view
        class SafeOperatingArea:
            vsi_dc_voltage:    MathRange = MathRange()
            vsi_dc_current:    MathRange = MathRange()
            vsi_phase_current: MathRange = MathRange()
            cpu_temperature:   MathRange = MathRange()
            vsi_temperature:   MathRange = MathRange()

        @_struct_view
        class PhaseCurrentZeroBiasLimit:
            low_gain:  float = 0
            high_gain: float = 0

        measurement_range:             MeasurementRange = MeasurementRange()
        safe_operating_area:           SafeOperatingArea = SafeOperatingArea()
        phase_current_zero_bias_limit: PhaseCurrentZeroBiasLimit = PhaseCurrentZeroBiasLimit()

        @staticmethod
        def populate(msg: typing.Mapping):
            mr = msg['measurement_range']
            soa = msg['safe_operating_area']
            return Characteristics.Limits(
                measurement_range=Characteristics.Limits.MeasurementRange(
                    vsi_dc_voltage=MathRange(**mr['vsi_dc_voltage']),
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

    capabilities: Capabilities = Capabilities()
    vsi_model:    VSIModel = VSIModel()
    limits:       Limits = Limits()

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
        'limits':           {'measurement_range':             {'vsi_dc_voltage': {'max': 62.040000915527344,
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
    name:                        str = ''
    description:                 str = ''
    software_version:            SoftwareVersion = SoftwareVersion
    hardware_version:            HardwareVersion = HardwareVersion
    globally_unique_id:          bytes = b'\0' * 16
    certificate_of_authenticity: bytes = b''

    characteristics: Characteristics = Characteristics()

    @staticmethod
    def populate(node_info_message: NodeInfoMessage,
                 characteristics_message: typing.Mapping) -> 'DeviceInfoView':
        return DeviceInfoView(
            name=node_info_message.node_name,
            description=node_info_message.node_description,
            software_version=SoftwareVersion.populate(node_info_message),
            hardware_version=HardwareVersion.populate(node_info_message),
            globally_unique_id=node_info_message.globally_unique_id,
            certificate_of_authenticity=node_info_message.certificate_of_authenticity,
            characteristics=Characteristics.populate(characteristics_message),
        )
