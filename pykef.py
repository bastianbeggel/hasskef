#! /usr/bin/env python
"""Based on code from Gronis (https://github.com/Gronis/pykef)"""

from enum import Enum
import socket
import logging
import datetime
from time import sleep, time
from threading import Thread

_LOGGER = logging.getLogger(__name__)
_VOL_STEP = 0.05 # 5 percent
_RESPONSE_OK = 17
_TIMEOUT = 1.0  # in secs
_CONNECTION_KEEP_ALIVE = 1.0  # in secs
_SCALE = 100.0
_RETRIES = 1

class InputSource(Enum):
    WIFI = bytes([0x53, 0x30, 0x81, 0x12, 0x82])
    BLUETOOTH = bytes([0x53, 0x30, 0x81, 0x19, 0xad])
    AUX = bytes([0x53, 0x30, 0x81, 0x1a, 0x9b])
    OPT = bytes([0x53, 0x30, 0x81, 0x1b, 0x00])
    USB = bytes([0x53, 0x30, 0x81, 0x1c, 0xf7])

class KefSpeaker():
    def __init__(self, host, port):
        self.__connection = None
        self.__connected = False
        self.__online = False
        self.__last_timestamp = 0
        self.__host = host
        self.__port = port
        self.__update_thread = Thread(target=self.__update, daemon=True)
        self.__update_thread.start()

    def __refresh_connection(self):
        """Connect if not connected.

        Retry at max for 100 times, with longer interval each time.
        Update timestamp that keep connection alive.

        If unable to connect due to no route to host, set to offline

        If speaker is offline, max retires is infinite.

        """
        self.__last_timestamp = time()
        if not self.__connected:
            def setup_connection():
                self.__connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.__connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.__connection.settimeout(_TIMEOUT)
                return self.__connection

            self.__connection = setup_connection()
            self.__connected = False
            wait = 0.1
            retries = 0
            while retries < _RETRIES:
                self.__last_timestamp = time()
                try:
                    self.__connection.connect((self.__host, self.__port))
                    self.__connected = True
                    self.__online = True
                    _LOGGER.debug("Online")
                    _LOGGER.debug("Connected")
                    break
                except ConnectionRefusedError:
                    self.__connection = setup_connection()
                    wait += 0.1
                    sleep(wait)
                except BlockingIOError: # Connection ingoing
                    retries = 0
                    wait = _TIMEOUT
                    sleep(wait)
                except OSError: # Host is down
                    self.__online = False
                    _LOGGER.debug("Offline")
                    retries = 0
                    wait = _TIMEOUT
                    sleep(wait)
                    self.__connection = setup_connection()
                except socket.timeout: # Host went offline (probably)
                    self.__online = False
                    _LOGGER.debug("Offline")
                    retries = 0
                    wait = _TIMEOUT
                    sleep(wait)
                retries += 1

    def __disconnect_if_passive(self):
        """Disconnect if connection is not used for a while (old timestamp)."""
        if self.__connected and time() - self.__last_timestamp > _CONNECTION_KEEP_ALIVE:
            self.__connected = False
            self.__connection.close()
            _LOGGER.debug("Disconneced")

    def __update(self):
        """Thread running in the background, disconnects speakers when passive."""
        while 1:
            sleep(0.1)
            self.__disconnect_if_passive()

    def __sendCommand(self, message):
        """Send command to speakers, returns the response."""
        self.__refresh_connection()
        if self.__connected:

            self.__connection.sendall(message)
            data = self.__connection.recv(1024)

        else:
            #data = None
            raise OSError('__sendCommand failed')
        return data[len(data) - 2] if data else None

    def __getVolume(self):
        _LOGGER.debug("__getVolume")
        msg = bytes([0x47, 0x25, 0x80, 0x6c])
        return self.__sendCommand(msg)

    def __setVolume(self, volume):
        _LOGGER.debug("__setVolume: " + "volume:" + str(volume))
        # write vol level in 4th place , add 128 to current level to mute
        msg = bytes([0x53, 0x25, 0x81, int(volume), 0x1a])
        return self.__sendCommand(msg) == _RESPONSE_OK

    def __getSource(self):
        _LOGGER.debug("__getSource")
        msg = bytes([0x47, 0x30, 0x80, 0xd9])
        table = {
            18: InputSource.WIFI,
            31: InputSource.BLUETOOTH,
            26: InputSource.AUX,
            27: InputSource.OPT,
            28: InputSource.USB
        }
        response = self.__sendCommand(msg)

        return table.get(response) if response else None

    def __setSource(self, source):
        _LOGGER.debug("__setSource: " + "source:" + str(source))
        return self.__sendCommand(source.value) == _RESPONSE_OK


    @property
    def volume(self):
        """Volume level of the media player (0..1). None if muted"""
        volume = self.__getVolume()

        #__getVolume/_sendcommand might return None due too network errors
        if not (volume is None):
            return volume / _SCALE if volume < 128 else None
        else:
            return None;


    @volume.setter
    def volume(self, value):

            if value:
                volume = int(max(0.0, min(1.0, value)) * _SCALE)
            else:
                volume = int(self.__getVolume()) % 128 + 128
                _LOGGER.info("In volume.setter else case: volume:" +str( volume))
            self.__setVolume(volume)

    @property
    def source(self):
        """Get the input source of the speaker."""
        return self.__getSource()

    @source.setter
    def source(self, value):
        self.__setSource(value)

    @property
    def muted(self):
        return self.__getVolume() > 128

    @muted.setter
    def muted(self, value):

        current_volume = self.__getVolume()
        if current_volume is None:
            return
        if value :
            self.__setVolume(int(current_volume) % 128 + 128 )
        else:
            self.__setVolume( int(current_volume) % 128)

    @property
    def online(self):
        self.__refresh_connection()
        return self.__online

    def turnOff(self):

        msg = bytes([0x53, 0x30, 0x81, 0x9b, 0x0b])
        self.__sendCommand(msg)

    def increaseVolume(self, step = None):
        """Increase volume by step, or 5% by default. Constrait: 0.0 < step < 1.0."""

        volume = self.__getVolume()
        if volume:
            step = step if step else _VOL_STEP
            self.__setVolume(volume + step * _SCALE)


    def decreaseVolume(self, step = None):
        """Decrease volume by step, or 5% by default. Constrait: 0.0 < step < 1.0."""
        self.increaseVolume(-(step or _VOL_STEP))


def mainTest1():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)
    #print(speaker.__setSource(InputSource.OPT))
    #print(speaker.__getSource())

    # TIMER = 0.1
    # sleep(TIMER)
    # speaker.connect(host, port)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    # sleep(TIMER)
    # print(speaker.volume)
    # sleep(TIMER)
    speaker.source = InputSource.USB
    print("isOnline:" + str(speaker.online))
    print(speaker.source)
    speaker.volume = 0.5
    print(speaker.volume)
    #print ("vol:" + str(speaker.increaseVolume()))
    speaker.volume = None
    #print("getvol: ", speaker.__getVolume())
    speaker.muted = False
    print("getvol: ", speaker.volume)
    speaker.volume = 0.6
    print("getvol: ", speaker.volume)
    print("vol: ", speaker.volume)
    print("getvol: ", speaker.volume)
    print("vol up:" + str(speaker.increaseVolume(0.05)))
    print("getvol: ", speaker.volume)
    print("vol: ", speaker.volume)
    speaker.increaseVolume()
    print("vol up:" + str(speaker.volume))
    speaker.increaseVolume()
    print("vol up:" + str(speaker.volume))
    speaker.volume = None
    speaker.increaseVolume()
    print("vol up:" + str(speaker.volume))
    speaker.muted = False
    print("vol: ", speaker.volume)
    speaker.decreaseVolume()
    print("vol down:" + str(speaker.volume))
    speaker.decreaseVolume()
    print("vol down:" + str(speaker.volume))
    speaker.decreaseVolume()
    print("vol down:" + str(speaker.volume))

    while 1:
        sleep(3)
        print(speaker.source)

def mainTest2():
    host = '192.168.178.52'
    port = 50001
    service = KefSpeaker(host, port)
    print("isOnline:" + str(service.online))
    service.source = InputSource.USB
    service.source = InputSource(("USB",))
    #service.turnOff()

def mainTest3():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)

    while 1:
        sleep(2)
        print("vol:" +str(speaker.volume))
        print("mute:" + str(speaker.muted))
        print("source:" + str(speaker.source))
        print ("online:" + str(speaker.online))

def mainTest4():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)

    while 1:


        speaker.muted = True
        print ("Is Mutted:" +  str(speaker.muted ))
        sleep(5)
        speaker.muted = False
        print("Is Mutted:" + str(speaker.muted))
        sleep(5)

def mainTest5():
    host = '192.168.178.52'
    port = 50001
    speaker = KefSpeaker(host, port)

    while 1:
        #speaker.increaseVolume(0.1)
        print ("Volume:" +  str(speaker.volume ))
        sleep(5)
        #speaker.decreaseVolume(0.1)
        print("Volume:" + str(speaker.volume))
        sleep(5)

        #speaker.muted = True
        print("Is Mutted:" + str(speaker.muted))
        #sleep(5)
        #speaker.muted = False
        #print("Is Mutted:" + str(speaker.muted))
        #sleep(5)

        sleep(5)


if __name__ == '__main__':
    mainTest3()
