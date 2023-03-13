import math
import time
import json
import threading

import requests
import serial


class NodeSim:
    def __init__(self, port, onupdate):
        self.port = port
        self.baud = 9600

        self.connection = False
        self.onupdate = onupdate

        self.current_position = 0
        self.current_status = None
        self.speed = 0

        self._last_update = None
        self.is_connected = True

    def set_position(self, position):
        self.current_position = position

    def get_position(self):
        return self.current_position

    def get_status(self):
        return self.current_status

    def reset_position(self, position):
        self.current_position = position

    def set_speed(self, speed):
        self.speed = speed

    def connect(self):
        self.connection = True

        def connection_thread():
            while self.connection:
                time.sleep(5)
                self.onupdate()

        th = threading.Thread(target=connection_thread)
        th.start()

    def disconnect(self):
        self.connection = False
