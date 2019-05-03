"""
Support for interfacing HA with the KEF Wireless Speakers .

Ich wollte noch was ändern!!!
Ich wollte noch was ändern. Was viel wichtiger war. Habs nur vergessen. 

"""

import asyncio
from datetime import timedelta
from collections import OrderedDict
from custom_components.media_player.pykef import *
import json
import logging
import socket

import os
import aiohttp
import voluptuous as vol
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA, SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_SELECT_SOURCE, SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP,SUPPORT_TURN_OFF,SUPPORT_TURN_ON,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_IDLE, STATE_PAUSED, STATE_PLAYING,STATE_OFF , STATE_ON)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle


_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = 'KEFWIRELESS'
DEFAULT_PORT = 50001
DATA_KEFWIRELESS = 'kefwireless'
VOLUME_STEP = 0.05
CONF_TURN_ON_SERVICE = 'turn_on_service'
CONF_TURN_ON_DATA = 'turn_on_data'


# configure source options to communicate to HA
KEF_LS50_SOURCE_DICT = OrderedDict([('1','WIFI'), ('2', 'BLUETOOTH'), ('3', 'AUX'), ('4', 'OPT'), ('5', 'USB')])

#supported features
SUPPORT_KEFWIRELESS = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE | SUPPORT_TURN_OFF


#yaml configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port ,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TURN_ON_SERVICE): cv.service,
    vol.Optional(CONF_TURN_ON_DATA): cv.string,      
})


#setup of component
def setup_platform(hass, config, add_devices,
                               discovery_info=None):

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    turn_on_service = config.get(CONF_TURN_ON_SERVICE)
    turn_on_data = config.get(CONF_TURN_ON_DATA)


    _LOGGER.info("Setting up " + DATA_KEFWIRELESS + " + using " + "host:" + str(host)+ ", port:" + str(port)+ ", name:" + str(name) + ", turn_on_service:" + str(turn_on_service) + ", turn_on_data:" + str(turn_on_data))
    _LOGGER.debug(
        "Setting up source_dict " + str(KEF_LS50_SOURCE_DICT))

    # Add devices
    add_devices([KefWireless( name, host, port, turn_on_service,
                             turn_on_data, KEF_LS50_SOURCE_DICT,hass)])

class KefWireless(MediaPlayerDevice):
    """Kef Player Object."""

    def __init__(self, name, host, port,turn_on_service, turn_on_data,source_dict, hass):
        """Initialize the media player."""
        self._hass = hass
        self._name = name
        self._source_dict = source_dict
        self._reverse_mapping = {value: key for key, value in self._source_dict.items()}
        self._speaker = KefSpeaker(host, port)
        self._turn_on_service = turn_on_service
        self._turn_on_data = turn_on_data


        #set internal state to None
        self._state =None;
        self._mute = None;
        self._source = None
        self._volume = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state


    def __internal_state (self) :
        """Return text with the internal states, just for debugging."""
        ret = []
        ret.append("self._state=" +str(self._state))
        ret.append("self._mute=" + str(self._mute))
        ret.append("self._source=" + str(self._source))
        ret.append("self._volume=" + str(self._volume))
        return ', '.join([str(x) for x in ret])


    def __short_state_desc (self) :
        """Return a short text with key kef parameters to show in HA."""
        if not (self._source is None or self._mute is None):
            if  self._mute:
                return   str(self._source).split(".")[1] + " - " + "muted"
            else:
                return  str(self._source).split(".")[1] + " - " + str(int(self._volume * 100)) + "%"

        return None


    def update(self):
        """update latest state.
           This function is called from HA in regular intervals
           Here we query the speaker to update the internal state of this class.
           """
        try:
            isOnline = self._speaker.online
            if isOnline:
                self._mute = self._speaker.muted;
                self._source = str(self._speaker.source)
                self._volume = self._speaker.volume
                # set state to selected input and volumne . This way this info is shown in HA at a glance
                self._state = self.__short_state_desc()

            else:

                self._mute = None
                self._source = None
                self._volume = None
                self._state = STATE_OFF;
        except Exception as ex:

            _LOGGER.debug("update: " + self.__internal_state());
            _LOGGER.debug(ex);

        _LOGGER.debug("update: " + self.__internal_state() );


    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (SUPPORT_KEFWIRELESS |
                (SUPPORT_TURN_ON if self.__is_turning_on_supported() else 0))

    def turn_off(self):
        """Turn the media player off."""
        try:
            self._speaker.turnOff()
        except Exception :
            _LOGGER.warning("turn_off: failed" );


    def volume_up(self):
        """Volume up the media player."""
        try:
            self._speaker.increaseVolume ()
        except Exception :
            _LOGGER.warning("increaseVolume: failed" );


    def volume_down(self):
        """Volume down the media player."""
        try:
            self._speaker.decreaseVolume()
        except Exception :
            _LOGGER.warning("volume_down: failed" );


    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        try:
            self._speaker.volume = volume
        except Exception :
            _LOGGER.warning("set_volume_level: failed" );


    def select_source(self, source):
        """Select input source."""
        try:
            if source == "WIFI":
                self._speaker.source = InputSource.WIFI
            elif source == "BLUETOOTH":
                self._speaker.source = InputSource.BLUETOOTH
            elif source == "AUX":
                self._speaker.source = InputSource.AUX
            elif source == "OPT":
                self._speaker.source = InputSource.OPT
            elif source == "USB":
                self._speaker.source = InputSource.USB
            else:
                _LOGGER.warning("unknown input was selected " + str(source))
        except Exception :
            _LOGGER.warning("select_source: failed" );


    @property
    def source(self):
        """Name of the current input source."""
        _LOGGER.debug("source - returning " + str(self._source));
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        _LOGGER.debug("source_list");
        return sorted(list(self._reverse_mapping.keys()))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        try:
            if mute:
                self._speaker.muted = True
            else:
                self._speaker.muted =  False
        except Exception :
            _LOGGER.warning("mute_volume: failed");

    def __is_turning_on_supported(self):
        return True #self._turn_on_service 

    def turn_on(self):
        """Turn the media player on via service call."""

        # even if the SUPPORT_TURN_ON is not set as supported feature, HA still
        # offers to call turn_on, thus we have to exit here to prevent errors
        if (not self.__is_turning_on_supported() ):
            return

        # note that turn_on_service has the correct syntax as we validated the
        # input
        service_domain = self._turn_on_service.split(".")[0]
        service_name = self._turn_on_service.split(".")[1]

        # this might need some more work. The self._hass.services.call expects
        # a python dict this input is specified as a string. I was not able to
        # use config validation to make sure it is a dict
        service_data = json.loads(self._turn_on_data)
        self._hass.services.call(
            service_domain, service_name, service_data, False)


