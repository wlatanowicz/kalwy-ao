import json
import asyncio
import serial


class NodeSerial:
    def __init__(self, port, onupdate):
        self.port = port
        self.baud = 9600

        self.connection = None
        self.onupdate = onupdate

        self.current_position = None
        self.current_status = None

        self._last_update = None
        self.is_connected = True

    def set_position(self, position):
        self._send_command(position=position)

    def get_position(self):
        return self.current_position

    def get_status(self):
        return self.current_status

    def reset_position(self, position):
        self._send_command(reset=position)

    def set_speed(self, speed):
        self._send_command(speed=speed)

    def _send_command(self, **cmd):
        if self.connection.is_open:
            self.connection.write(json.dumps(cmd).encode())

    def connect(self):
        self.connection = serial.Serial(self.port, self.baud)


        th = threading.Thread(target=connection_thread)
        th.start()

    def disconnect(self):
        self.connection.close()

    def polling(self):
        while self.connection.is_open:
            in_data = self.connection.readline()
            if not in_data:
                continue

            in_data = json.loads(in_data.decode())

            if "status" in in_data:
                status = in_data["status"]

                if status != self._last_update:
                    self.current_position = status["position"]
                    self.current_status = status["status"]
                    self._last_update = status
                    self.onupdate()
