from __future__ import annotations, absolute_import
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

import typing
if typing.TYPE_CHECKING:
    from typing import Optional, Any

logger = logging.getLogger(__name__)

class ConfigurationVersion(Enum):
    V3_0 = '3.0'
    V2_0 = '2.0'
    V1_0 = '1.0'

class SunLocation(Enum):
    SOLAR_NOON = 'solar noon'
    SUNSET = 'sunset'
    CIVIL_DAWN = 'civil dawn'
    NAUTICAL_DAWN = 'nautical dawn'
    ASTRONOMICAL_DAWN = 'astronomical dawn'
    ASTRONOMICAL_DUSK = 'astronomical dusk'
    NAUTICAL_DUSK = 'nautical dusk'
    CIVIL_DUSK = 'civil dusk'
    SUNRISE = 'sunrise'


@dataclass
class GroupActionJob:
    group_action_id: int
    sun_location: SunLocation
    offset: int


class ValidationJobAction(Enum):
    SET = 'set'
    CLEAR = 'clear'

@dataclass
class ValidationJob:
    action: ValidationJobAction
    bit_id: int
    sun_location: SunLocation
    offset: int


@dataclass
class Coordinates:
    latitude: float = None
    longitude: float = None

    def __str__(self):
        return f"{self.latitude:.6f};{self.longitude:.6f}"

    @staticmethod
    def from_string(coord_str: str) -> Coordinates:
        if coord_str == '':
            return Coordinates(0.0, 0.0)

        match = re.match(r'^(-?\d+[\.,]\d+).*?[;,/].*?(-?\d+[\.,]\d+)$', coord_str)
        if match:
            latitude = match.group(1)
            if ',' in latitude:
                latitude = latitude.replace(',', '.')
            longitude = match.group(2)
            if ',' in longitude:
                longitude = longitude.replace(',', '.')
            try:
                latitude = float(latitude)
                longitude = float(longitude)
                return Coordinates(latitude, longitude)
            except ValueError as ex:
                logger.error('Could not parse coordinates: {0}'.format(ex))
                raise
        else:
            raise ValueError(f"Invalid coordinates format: {coord_str}. Expected format is 'lat;long' or 'lat,long'.")


@dataclass
class Configuration:
    coordinates: Coordinates = field(default_factory=lambda: Coordinates(0.0, 0.0))
    group_action_jobs: list[GroupActionJob] = field(default_factory=list)
    validation_jobs: list[ValidationJob] = field(default_factory=list)
    version: ConfigurationVersion = ConfigurationVersion.V3_0


class ConfigurationFactory:
    def __init__(self):
        self.config = None

    def _determine_configuration_version(self, config_data: dict) -> ConfigurationVersion:
        if 'version' in config_data:
            version_str = config_data['version']
            return ConfigurationVersion(version_str)

        if 'basic_configuration' in config_data and 'advanced_configuration' in config_data:
            return ConfigurationVersion.V2_0

        return ConfigurationVersion.V1_0

    def _migrate_configuration_v1(self, config_data: dict) -> Configuration:
        version = self._determine_configuration_version(config_data)
        if version != ConfigurationVersion.V1_0:
            raise ValueError("Configuration version is not V1.0, cannot migrate.")

        coordinates = config_data.get('coordinates')
        horizon_bit_id = config_data.get('horizon_bit', -1)
        civil_bit_id = config_data.get('civil_bit', -1)
        nautical_bit_id = config_data.get('nautical_bit', -1)
        astronomical_bit_id = config_data.get('astronomical_bit', -1)
        bright_bit_id = config_data.get('bright_bit', -1)
        bright_offset = config_data.get('bright_offset', 0)
        group_action_id = config_data.get('group_action', -1)

        if not coordinates:
            raise ValueError("Coordinates must be provided in the configuration. (location only is no longer supported)")

        coordinates_parsed = Coordinates.from_string(coordinates)

        group_action_jobs = [] 
        validation_jobs = []

        for bit, start, stop, account_offset in [
            (horizon_bit_id, SunLocation.SUNRISE, SunLocation.SUNSET, False),
            (civil_bit_id, SunLocation.CIVIL_DAWN, SunLocation.CIVIL_DUSK, False),
            (nautical_bit_id, SunLocation.NAUTICAL_DAWN, SunLocation.NAUTICAL_DUSK, False),
            (astronomical_bit_id, SunLocation.ASTRONOMICAL_DAWN, SunLocation.ASTRONOMICAL_DUSK, False),
            (bright_bit_id, SunLocation.SUNRISE, SunLocation.SUNSET, True)
            ]:
            if bit >= 0:
                validation_jobs.append(ValidationJob(
                    action=ValidationJobAction.SET,
                    bit_id=bit,
                    sun_location=start,
                    offset=bright_offset if account_offset else 0
                ))
                validation_jobs.append(ValidationJob(
                    action=ValidationJobAction.CLEAR,
                    bit_id=bit,
                    sun_location=stop,
                    offset=-bright_offset if account_offset else 0
                ))
                group_action_jobs.append(GroupActionJob(
                    group_action_id=group_action_id,
                    sun_location=start,
                    offset=bright_offset if account_offset else 0
                ))
                group_action_jobs.append(GroupActionJob(
                    group_action_id=group_action_id,
                    sun_location=stop,
                    offset=-bright_offset if account_offset else 0
                ))

        return Configuration(
            coordinates=coordinates_parsed,
            group_action_jobs=group_action_jobs,
            validation_jobs=validation_jobs,
            version=ConfigurationVersion.V3_0
        )

    def _migrate_configuration_v2(self, config_data: dict) -> Configuration:
        version = self._determine_configuration_version(config_data)
        if version != ConfigurationVersion.V2_0:
            raise ValueError("Configuration version is not V2.0, cannot migrate.")

        coordinates = config_data.get('coordinates')
        if not coordinates:
            raise ValueError("Coordinates must be provided in the configuration.")
        coordinates_parsed = Coordinates.from_string(coordinates)
        group_action_jobs = [
            GroupActionJob(
                group_action_id=job['group_action_id'],
                sun_location=SunLocation(job['sun_location']),
                offset=int(job['offset'] or 0)
            ) for job in config_data.get('basic_configuration', [])
        ]
        validation_jobs = [
            ValidationJob(
                action=ValidationJobAction(job['action']),
                bit_id=job['bit_id'],
                sun_location=SunLocation(job['sun_location']),
                offset=int(job['offset'] or 0)
            ) for job in config_data.get('advanced_configuration', [])
        ]
        return Configuration(coordinates_parsed, group_action_jobs, validation_jobs, ConfigurationVersion.V3_0)

    def _migrate_configuration_v3(self, config_data: dict) -> Configuration:
        version = self._determine_configuration_version(config_data)
        if version != ConfigurationVersion.V3_0:
            raise ValueError("Configuration version is not V3.0, cannot migrate.")

        coordinates = config_data.get('coordinates')
        if not coordinates:
            raise ValueError("Coordinates must be provided in the configuration.")
        coordinates_parsed = Coordinates.from_string(coordinates)
        group_action_jobs = [
            GroupActionJob(
                group_action_id=job['group_action_id'],
                sun_location=SunLocation(job['sun_location']),
                offset=int(job['offset'] or 0)
            ) for job in config_data.get('basic_configuration', [])
        ]
        validation_jobs = [
            ValidationJob(
                action=ValidationJobAction(job['action']),
                bit_id=job['bit_id'],
                sun_location=SunLocation(job['sun_location']),
                offset=int(job['offset'] or 0)
            ) for job in config_data.get('advanced_configuration', [])
        ]
        return Configuration(coordinates_parsed, group_action_jobs, validation_jobs, ConfigurationVersion.V3_0)


    def _verify_configuration(self, config: Configuration):
        if not config.coordinates:
            raise ValueError("Coordinates must be provided in the configuration.")

        for job in config.group_action_jobs:
            try:
                if isinstance(job.group_action_id, str):
                    job.group_action_id = int(job.group_action_id)
            except ValueError:
                raise ValueError(f"Invalid group action ID: {job.group_action_id}, should be an integer.")
            if job.group_action_id < 0:
                raise ValueError(f"Invalid group action ID: {job.group_action_id}")

        for job in config.validation_jobs:
            try:
                if isinstance(job.bit_id, str):
                    job.bit_id = int(job.bit_id)
            except ValueError:
                raise ValueError(f"Invalid bit ID: {job.bit_id}, should be an integer.")
            if job.bit_id < 0:
                raise ValueError(f"Invalid bit ID: {job.bit_id}, for validation job {job.sun_location.value}")
            if job.sun_location not in SunLocation:
                raise ValueError(f"Invalid sun location: {job.sun_location}")


    def parse_configuration(self, config_data: dict) -> Configuration:
        current_version = self._determine_configuration_version(config_data)

        curr_config = None

        if current_version == ConfigurationVersion.V1_0:
            curr_config = self._migrate_configuration_v1(config_data)
        elif current_version == ConfigurationVersion.V2_0:
            curr_config = self._migrate_configuration_v2(config_data)
        elif current_version == ConfigurationVersion.V3_0:
            curr_config = self._migrate_configuration_v3(config_data)
        else:
            raise ValueError(f"Unsupported configuration version: {current_version}")

        self._verify_configuration(curr_config)
        self.config = curr_config
        return curr_config

    def get_json_configuration(self, config:Optional[Configuration] = None) -> dict[str, Any]:
        if config is None:
            config = self.config
        if config is None:
            raise ValueError("Configuration has not been parsed yet.")

        return {
            'coordinates': str(config.coordinates),
            'basic_configuration': [
                {
                    'group_action_id': job.group_action_id,
                    'sun_location': job.sun_location.value,
                    'offset': job.offset
                } for job in config.group_action_jobs
            ],
            'advanced_configuration': [
                {
                    'action': job.action.value,
                    'bit_id': job.bit_id,
                    'sun_location': job.sun_location.value,
                    'offset': job.offset
                } for job in config.validation_jobs
            ],
            'version': config.version.value
        }

    @staticmethod
    def get_config_description() -> list:
        # note that there is no versioning in the config description
        # this will be added manually when the configuration changes and is passed trough the configuration factory
        config_description = [{'name': 'coordinates',
                               'type': 'str',
                               'description': 'Coordinates in the form of `lat;long`.'},
                              {'name': 'basic_configuration',
                               'type': 'section',
                               'description': 'Executing automations at a certain point',
                               'repeat': True, 'min': 0,
                               'content': [{'name': 'group_action_id',
                                            'type': 'int',
                                            'description': 'The Id of the Group Action / Automation that needs to be executed'},
                                           {'name': 'sun_location',
                                            'type': 'enum',
                                            'description': 'The location of the sun at this point',
                                            'choices': ['solar noon',
                                                        'sunset', 'civil dawn', 'nautical dawn', 'astronomical dawn',
                                                        'astronomical dusk', 'nautical dusk', 'civil dusk', 'sunrise']},
                                           {'name': 'offset',
                                            'type': 'int',
                                            'description': 'Offset in minutes before (negative value) or after (positive value) the given sun location'}]},
                              {'name': 'advanced_configuration',
                               'type': 'section',
                               'description': 'Setting/clearing validation bit at a certain point',
                               'repeat': True, 'min': 0,
                               'content': [{'name': 'action',
                                            'type': 'enum',
                                            'description': 'Whether to set or clear the validation bit',
                                            'choices': ['set', 'clear']},
                                           {'name': 'bit_id',
                                            'type': 'int',
                                            'description': 'The Id of the Validaten Bit that needs to set/cleared'},
                                           {'name': 'sun_location',
                                            'type': 'enum',
                                            'description': 'The location of the sun at this point',
                                            'choices': ['solar noon',
                                                        'sunset', 'civil dawn', 'nautical dawn', 'astronomical dawn',
                                                        'astronomical dusk', 'nautical dusk', 'civil dusk', 'sunrise']},
                                           {'name': 'offset',
                                            'type': 'int',
                                            'description': 'Offset in minutes before (negative value) or after (positive value) the given sun location'}]}
                              ]
        return config_description

    def get_default_configuration(self) -> dict[str, Any]:
        config = Configuration(
            coordinates=Coordinates(0.0, 0.0),
            group_action_jobs=[],
            validation_jobs=[],
            version=ConfigurationVersion.V3_0
        )
        json_config = self.get_json_configuration(config)
        return json_config











# This is Version 2.0 of the configuration description
    # config_description = [{'name': 'coordinates',
    #                        'type': 'str',
    #                        'description': 'Coordinates in the form of `lat;long`.'},
    #                       {'name': 'basic_configuration',
    #                        'type': 'section',
    #                        'description': 'Executing automations at a certain point',
    #                        'repeat': True, 'min': 0,
    #                        'content': [{'name': 'group_action_id',
    #                                     'type': 'int',
    #                                     'description': 'The Id of the Group Action / Automation that needs to be executed'},
    #                                    {'name': 'sun_location',
    #                                     'type': 'enum',
    #                                     'description': 'The location of the sun at this point',
    #                                     'choices': ['solar noon',
    #                                                 'sunset', 'civil dawn', 'nautical dawn', 'astronomical dawn',
    #                                                 'astronomical dusk', 'nautical dusk', 'civil dusk', 'sunrise']},
    #                                    {'name': 'offset',
    #                                     'type': 'str',
    #                                     'description': 'Offset in minutes before (negative value) or after (positive value) the given sun location'}]},
    #                       {'name': 'advanced_configuration',
    #                        'type': 'section',
    #                        'description': 'Setting/clearing validation bit at a certain point',
    #                        'repeat': True, 'min': 0,
    #                        'content': [{'name': 'action',
    #                                     'type': 'enum',
    #                                     'description': 'Whether to set or clear the validation bit',
    #                                     'choices': ['set', 'clear']},
    #                                    {'name': 'bit_id',
    #                                     'type': 'int',
    #                                     'description': 'The Id of the Validaten Bit that needs to set/cleared'},
    #                                    {'name': 'sun_location',
    #                                     'type': 'enum',
    #                                     'description': 'The location of the sun at this point',
    #                                     'choices': ['solar noon',
    #                                                 'sunset', 'civil dawn', 'nautical dawn', 'astronomical dawn',
    #                                                 'astronomical dusk', 'nautical dusk', 'civil dusk', 'sunrise']},
    #                                    {'name': 'offset',
    #                                     'type': 'str',
    #                                     'description': 'Offset in minutes before (negative value) or after (positive value) the given sun location'}]}
    #                       ]


# This is Version 1.0 of the configuration description
    # config_description = [{'name': 'location',
    #                        'type': 'str',
    #                        'description': 'A written location to be translated to coordinates using Google. Leave empty and provide coordinates below to prevent using the Google services.'},
    #                       {'name': 'coordinates',
    #                        'type': 'str',
    #                        'description': 'Coordinates in the form of `lat;long` where both are a decimal numbers with dot as decimal separator. Leave empty to fill automatically using the location above.'},
    #                       {'name': 'horizon_bit',
    #                        'type': 'int',
    #                        'description': 'The bit that indicates whether it is day. -1 when not in use.'},
    #                       {'name': 'civil_bit',
    #                        'type': 'int',
    #                        'description': 'The bit that indicates whether it is day or civil twilight. -1 when not in use.'},
    #                       {'name': 'nautical_bit',
    #                        'type': 'int',
    #                        'description': 'The bit that indicates whether it is day, civil or nautical twilight. -1 when not in use.'},
    #                       {'name': 'astronomical_bit',
    #                        'type': 'int',
    #                        'description': 'The bit that indicates whether it is day, civil, nautical or astronomical twilight. -1 when not in use.'},
    #                       {'name': 'bright_bit',
    #                        'type': 'int',
    #                        'description': 'The bit that indicates the brightest part of the day. -1 when not in use.'},
    #                       {'name': 'bright_offset',
    #                        'type': 'int',
    #                        'description': 'The offset (in minutes) after sunrise and before sunset on which the bright_bit should be set.'},
    #                       {'name': 'group_action',
    #                        'type': 'int',
    #                        'description': 'The ID of a Group Action to be called when another zone is entered. -1 when not in use.'}]

