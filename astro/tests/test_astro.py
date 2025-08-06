import json
from unittest import TestCase

from ..configuration import ConfigurationFactory, Configuration, ConfigurationVersion, Coordinates, SunLocation, ValidationJob, GroupActionJob, ValidationJobAction




class AstroTest(TestCase):
    def test_calculate_mapping_v1(self):
        config_factory = ConfigurationFactory()
        input_config_str = '{"bright_bit":-1,"horizon_bit":200,"bright_offset":60,"location":"","astronomical_bit":-1,"nautical_bit":-1,"civil_bit":-1,"coordinates":"51.064630;3.737539","group_action":0}'
        input_config = json.loads(input_config_str)

        # import pudb; pudb.set_trace()
        config = config_factory.parse_configuration(input_config)

        expected_config = Configuration(
                coordinates=Coordinates.from_string("51.064630;3.737539"),
                group_action_jobs=[
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.SUNRISE,
                        offset=0,
                        ),
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.SUNSET,
                        offset=0,
                        )
                    ],
                validation_jobs=[
                    ValidationJob(
                        action=ValidationJobAction.SET,
                        bit_id=200,
                        sun_location=SunLocation.SUNRISE,
                        offset=0,
                        ),
                    ValidationJob(
                        action=ValidationJobAction.CLEAR,
                        bit_id=200,
                        sun_location=SunLocation.SUNSET,
                        offset=0,
                        )
                    ],
                version=ConfigurationVersion.V3_0
                )
        assert config == expected_config

    def test_calculate_mapping_v1_with_bright(self):
        config_factory = ConfigurationFactory()
        input_config_str = '{"bright_bit":1,"horizon_bit":-1,"bright_offset":60,"location":"","astronomical_bit":-1,"nautical_bit":-1,"civil_bit":-1,"coordinates":"51.064630;3.737539","group_action":0}'
        input_config = json.loads(input_config_str)

        # import pudb; pudb.set_trace()
        config = config_factory.parse_configuration(input_config)

        expected_config = Configuration(
                coordinates=Coordinates.from_string("51.064630;3.737539"),
                group_action_jobs=[
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.SUNRISE,
                        offset=60,
                        ),
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.SUNSET,
                        offset=-60,
                        )
                    ],
                validation_jobs=[
                    ValidationJob(
                        action=ValidationJobAction.SET,
                        bit_id=1,
                        sun_location=SunLocation.SUNRISE,
                        offset=60,
                        ),
                    ValidationJob(
                        action=ValidationJobAction.CLEAR,
                        bit_id=1,
                        sun_location=SunLocation.SUNSET,
                        offset=-60,
                        )
                    ],
                version=ConfigurationVersion.V3_0
                )
        assert config == expected_config


    def test_calculate_mapping_v1_with_multiple(self):
        config_factory = ConfigurationFactory()
        input_config_str = '{"bright_bit":1,"horizon_bit":-1,"bright_offset":60,"location":"","astronomical_bit":2,"nautical_bit":-1,"civil_bit":-1,"coordinates":"51.064630;3.737539","group_action":0}'
        input_config = json.loads(input_config_str)

        # import pudb; pudb.set_trace()
        config = config_factory.parse_configuration(input_config)

        expected_config = Configuration(
                coordinates=Coordinates.from_string("51.064630;3.737539"),
                group_action_jobs=[
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.ASTRONOMICAL_DAWN,
                        offset=0,
                        ),
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.ASTRONOMICAL_DUSK,
                        offset=0,
                        ),
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.SUNRISE,
                        offset=60,
                        ),
                    GroupActionJob(
                        group_action_id=0,
                        sun_location=SunLocation.SUNSET,
                        offset=-60,
                        ),
                    ],
                validation_jobs=[
                    ValidationJob(
                        action=ValidationJobAction.SET,
                        bit_id=2,
                        sun_location=SunLocation.ASTRONOMICAL_DAWN,
                        offset=0,
                        ),
                    ValidationJob(
                        action=ValidationJobAction.CLEAR,
                        bit_id=2,
                        sun_location=SunLocation.ASTRONOMICAL_DUSK,
                        offset=0,
                        ),
                    ValidationJob(
                        action=ValidationJobAction.SET,
                        bit_id=1,
                        sun_location=SunLocation.SUNRISE,
                        offset=60,
                        ),
                    ValidationJob(
                        action=ValidationJobAction.CLEAR,
                        bit_id=1,
                        sun_location=SunLocation.SUNSET,
                        offset=-60,
                        ),
                    ],
                version=ConfigurationVersion.V3_0
                )
        assert config == expected_config



 
    def test_calculate_mapping_v2(self):
        config_factory = ConfigurationFactory()
        input_config_str = '{"basic_configuration":[{"sun_location":"sunset","group_action_id":3,"offset":"30"},{"sun_location":"sunrise","group_action_id":5,"offset":"-90"}],"advanced_configuration":[],"coordinates":"42.854040, 13.896781"}'
        input_config = json.loads(input_config_str)

        # import pudb; pudb.set_trace()
        config = config_factory.parse_configuration(input_config)

        expected_config = Configuration(
                coordinates=Coordinates.from_string("42.854040;13.896781"),
                group_action_jobs=[
                    GroupActionJob(
                        group_action_id=3,
                        sun_location=SunLocation.SUNSET,
                        offset=30,
                        ),
                    GroupActionJob(
                        group_action_id=5,
                        sun_location=SunLocation.SUNRISE,
                        offset=-90,
                        )
                    ],
                validation_jobs=[],
                version=ConfigurationVersion.V3_0
                )
        assert config == expected_config



 
