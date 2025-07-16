"""
An astronomical plugin, for providing the system with astronomical data (e.g. whether it's day or not, based on the sun's location)
"""

import six
import time
import requests
import logging
import json
from threading import Thread, Event
from datetime import datetime, timedelta
from .configuration import ConfigurationFactory
from plugins.base import om_expose, background_task, OMPluginBase, PluginConfigChecker


logger = logging.getLogger(__name__)

config_factory = ConfigurationFactory()


class Astro(OMPluginBase):
    """
    An astronomical plugin, for providing the system with astronomical data (e.g. whether it's day or not, based on the sun's location)
    """

    name = 'Astro'
    version = '1.1.0'
    interfaces = [('config', '1.0')]

    config_description = config_factory.get_config_description()

    default_config = config_factory.get_default_configuration()

    def __init__(self, webinterface, connector):
        super(Astro, self).__init__(webinterface=webinterface, connector=connector)
        logger.info('Starting Astro plugin...')

        self._config = self.read_config(Astro.default_config)
        self._config_checker = PluginConfigChecker(Astro.config_description)

        self._parsed_config = None

        self._latitude = None
        self._longitude = None

        self._group_actions = {}
        self._bits = {}

        self._last_request_date = None
        self._execution_plan = {}

        self._sleeper = Event()
        self._sleep_until = 0

        thread = Thread(target=self._sleep_manager)
        thread.start()

        self._read_config()

        logger.info("Started Astro plugin")

    def _read_config(self):
        logger.info('Reading configuration...')
        logger.info('Configuration: {0}'.format(self._config))
        self._parsed_config = config_factory.parse_configuration(self._config)

        try:
            import pytz
            from pytz import reference
            enabled = True
        except ImportError:
            logger.error('Could not import pytz')
            enabled = False

        if enabled:
            # Parse coordinates
            coordinates = self._parsed_config.coordinates
            self._latitude = coordinates.latitude
            self._longitude = coordinates.longitude
            self._print_coordinate_time()


        if enabled:
            group_actions = {}
            for entry in self._parsed_config.group_action_jobs:
                sun_location = entry.sun_location.value
                if not sun_location:
                    continue
                try:
                    group_action_id = int(entry.group_action_id)
                except ValueError:
                    continue
                try:
                    offset = int(entry.offset or 0)
                except ValueError:
                    offset = 0
                actions = group_actions.setdefault(sun_location, [])
                actions.append({'group_action_id': group_action_id,
                                'offset': offset})
                self._group_actions = group_actions

            bits = {}
            for entry in self._parsed_config.validation_jobs:
                sun_location = entry.sun_location
                if not sun_location:
                    continue
                action = entry.action.value or 'clear'
                try:
                    bit_id = int(entry.bit_id)
                except ValueError:
                    continue
                try:
                    offset = int(entry.offset or 0)
                except ValueError:
                    offset = 0
                actions = bits.setdefault(sun_location, [])
                actions.append({'bit_id': bit_id,
                                'action': action,
                                'offset': offset})
                self._bits = bits

        self._print_actions()
        self._enabled = enabled and (self._group_actions or self._bits)
        self._last_request_date = None
        logger.info('Astro is {0}abled'.format('en' if self._enabled else 'dis'))
        self._sleeper.set()

    @staticmethod
    def _format_date(date, timezone=None):
        from pytz import reference

        if timezone is None:
            timezone = reference.LocalTimezone()
        if date.tzinfo is None:
            date = date.replace(tzinfo=reference.LocalTimezone())
        return date.astimezone(timezone).strftime('%Y-%m-%d %H:%M')

    @staticmethod
    def _format_offset(offset):
        return ' with a {0} min offset'.format(
            '+{0}'.format(offset) if offset > 0 else offset
        ) if offset else ''

    def _print_coordinate_time(self):
        import pytz

        now = datetime.now()
        logger.info('Location:')
        logger.info('* Latitude: {0} - Longitude: {1}'.format(self._latitude, self._longitude))
        logger.info('* Time: {0} local time, {1} UTC'.format(Astro._format_date(now),
                                                             Astro._format_date(now, timezone=pytz.UTC)))

    def _print_actions(self):
        sun_locations = set(self._group_actions.keys()) | set(self._bits.keys())
        if sun_locations:
            logger.info('Configured actions:')
        for sun_location in sun_locations:
            group_actions = self._group_actions.get(sun_location, [])
            bits = self._bits.get(sun_location, [])
            for entry in bits:
                logger.info('* At {0}{1}: {2} Validation Bit {3}'.format(
                    sun_location,
                    Astro._format_offset(entry['offset']),
                    entry['action'].capitalize(),
                    entry['bit_id']
                ))
            for entry in group_actions:
                logger.info('* At {0}{1}: Execute Automation {2}'.format(
                    sun_location,
                    Astro._format_offset(entry['offset']),
                    entry['group_action_id']
                ))

    def _print_execution_plan(self):
        if not self._execution_plan:
            logger.info('Empty execution plan for {0}'.format(self._last_request_date.strftime('%Y-%m-%d')))
            return
        logger.info('Execution plan for {0}:'.format(self._last_request_date.strftime('%Y-%m-%d')))
        for date in sorted(self._execution_plan.keys()):
            date_plan = self._execution_plan.get(date, [])
            if not date_plan:
                continue
            for action in date_plan:
                if action['task'] == 'group_action':
                    logger.info('* {0}: Execute Automation {1} ({2})'.format(Astro._format_date(date),
                                                                             action['data']['group_action_id'],
                                                                             action['source']))
                elif action['task'] == 'bit':
                    logger.info('* {0}: {1} Validation Bit {2} ({3})'.format(Astro._format_date(date),
                                                                             action['data']['action'].capitalize(),
                                                                             action['data']['bit_id'],
                                                                             action['source']))

    def _sleep_manager(self):
        while True:
            if not self._sleeper.is_set() and self._sleep_until < time.time():
                self._sleeper.set()
            time.sleep(5)

    def _sleep(self, timestamp):
        self._sleep_until = timestamp
        self._sleeper.clear()
        self._sleeper.wait()

    def _convert(self, dt_string):
        import pytz

        if dt_string is None:
            return None
        try:
            date = datetime.strptime(dt_string, '%Y-%m-%dT%H:%M:%S+00:00')
            date = pytz.utc.localize(date)
            if date.year == 1970:
                return None
            return date
        except Exception as ex:
            logger.exception('Could not parse date {0}'.format(dt_string))
            return None

    @background_task
    def run(self):
        while True:
            from pytz import reference

            if not self._enabled:
                self._sleep(time.time() + 30)
                continue

            now = datetime.now(reference.LocalTimezone())
            today = datetime(now.year, now.month, now.day,
                             tzinfo=reference.LocalTimezone())
            tomorrow = today + timedelta(days=1)
            try:
                if today != self._last_request_date:
                    self._last_request_date = today
                    self._build_execution_plan(now=now, date=now)
                    self._print_execution_plan()

                if not self._execution_plan:
                    logger.info('Suspending. Wakeup scheduled at {0}...'.format(Astro._format_date(tomorrow)))
                    sleep = (tomorrow - now).total_seconds()
                    self._sleep(time.time() + sleep + 5)
                    continue

                next_action_date = tomorrow
                next_action_delta = timedelta(days=2)
                for date in list(self._execution_plan.keys()):
                    delta = abs(date - now)
                    if delta > timedelta(minutes=5):
                        if date > now and delta < next_action_delta:
                            next_action_date = date
                            next_action_delta = delta
                        continue
                    plan = self._execution_plan.get(date, [])
                    if plan:
                        logger.info('Executing plan...')
                    for entry in plan:
                        if entry['task'] == 'group_action':
                            group_action_id = entry['data']['group_action_id']
                            try:
                                result = json.loads(self.webinterface.do_basic_action(action_type=2,
                                                                                      action_number=group_action_id))
                                if not result.get('success'):
                                    raise RuntimeError(result.get('msg', 'Unknown error'))
                                logger.info('* Executing Automation {0}: Done'.format(group_action_id))
                            except Exception as ex:
                                logger.error('* Executing Automation {0} failed: {1}'.format(group_action_id, ex))
                        elif entry['task'] == 'bit':
                            bit_id = entry['data']['bit_id']
                            action_words = 'Setting' if entry['data']['action'] == 'set' else 'Clearing'
                            action = 237 if entry['data']['action'] == 'set' else 238
                            try:
                                result = json.loads(self.webinterface.do_basic_action(action_type=action,
                                                                                      action_number=bit_id))
                                if not result.get('success'):
                                    raise RuntimeError(result.get('msg', 'Unknown error'))
                                logger.info('* {0} Validation Bit {1}: Done'.format(action_words, bit_id))
                            except Exception as ex:
                                logger.error('* {0} Validation Bit {1} failed: {2}'.format(action_words, bit_id, ex))
                    self._execution_plan.pop(date, None)
                logger.info('Processing complete')
                logger.info('Suspending. Wakeup scheduled at {0}...'.format(Astro._format_date(next_action_date)))
                sleep = (next_action_date - now).total_seconds()
                self._sleep(time.time() + sleep + 5)
            except Exception as ex:
                logger.info('Unexpected error while processing: {0}'.format(ex))
                logger.info('Suspending. Wakeup scheduled at {0}...'.format(Astro._format_date(tomorrow)))
                sleep = (tomorrow - now).total_seconds()
                self._sleep(time.time() + sleep + 5)

    def _build_execution_plan(self, now, date):
        retries = 5
        while retries > 0:
            retries = retries - 1
            try:
                req = requests.get('http://api.sunrise-sunset.org/json?lat={0}&lng={1}&date={2}&formatted=0'.format(
                    self._latitude, self._longitude, date.strftime('%Y-%m-%d')
                ))
                if req.status_code != 200:
                    raise RuntimeError("Invalid request response")
                data = req.json()
                if data['status'] != 'OK':
                    raise RuntimeError(data['status'])
                execution_plan = {}
                field_map = {'solar noon': 'solar_noon',
                            'sunset': 'sunset',
                            'civil dusk': 'civil_twilight_end',
                            'nautical dusk': 'nautical_twilight_end',
                            'astronomical dusk': 'astronomical_twilight_end',
                            'astronomical dawn': 'astronomical_twilight_begin',
                            'nautical dawn': 'nautical_twilight_begin',
                            'civil dawn': 'civil_twilight_begin',
                            'sunrise': 'sunrise'}
                for sun_location in set(self._group_actions.keys()) | set(self._bits.keys()):
                    group_actions = self._group_actions.get(sun_location, [])
                    bits = self._bits.get(sun_location, [])
                    if not group_actions and not bits:
                        continue
                    date = self._convert(data['results'].get(field_map.get(sun_location, 'x')))
                    if date is None:
                        continue

                    for entry in bits:
                        entry_date = date + timedelta(minutes=entry['offset'])
                        if entry_date < now:
                            continue
                        date_plan = execution_plan.setdefault(entry_date, [])
                        date_plan.append({'task': 'bit',
                                        'source': '{0}{1}'.format(
                                            sun_location,
                                            Astro._format_offset(entry['offset'])
                                        ),
                                        'data': {'action': entry['action'],
                                                'bit_id': entry['bit_id']}})

                    for entry in group_actions:
                        entry_date = date + timedelta(minutes=entry['offset'])
                        if entry_date < now:
                            continue
                        date_plan = execution_plan.setdefault(entry_date, [])
                        date_plan.append({'task': 'group_action',
                                        'source': '{0}{1}'.format(
                                            sun_location,
                                            Astro._format_offset(entry['offset'])
                                        ),
                                        'data': {'group_action_id': entry['group_action_id']}})
                self._execution_plan = execution_plan
                break
            except Exception as ex:
                logger.exception('Could not fetch or load data')
                self._execution_plan = {}
                logger.info("sleeping 5 seconds and retrying...")
                time.sleep(5)

    @om_expose
    def get_config_description(self):
        return json.dumps(Astro.config_description)

    @om_expose
    def get_config(self):
        return json.dumps(config_factory.get_json_configuration(self._parsed_config))

    @om_expose
    def set_config(self, config):
        config = json.loads(config)
        for key in config:
            if isinstance(config[key], six.string_types):
                config[key] = str(config[key])
        self._config_checker.check_config(config)
        self._config = config
        self._read_config()
        self.write_config(config)
        return json.dumps({'success': True})
