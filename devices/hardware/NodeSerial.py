import json
import asyncio
from serial_asyncio import open_serial_connection
from typing import Optional

class NodeSerial:
    def __init__(self, port, onupdate):
        self.port = port
        self.baud = 9600

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False

        self.onupdate = onupdate

        self.current_position = None
        self.current_status = None

        self._last_update = None
        self.is_connected = True

    def set_position(self, position):
        asyncio.get_running_loop().create_task(
            self._send_command(position=position)
        )

    def get_position(self):
        return self.current_position

    def get_status(self):
        return self.current_status

    def reset_position(self, position):
        asyncio.get_running_loop().create_task(
            self._send_command(reset=position)
        )

    def set_speed(self, speed):
        asyncio.get_running_loop().create_task(
            self._send_command(speed=speed)
        )

    async def _send_command(self, **cmd):
        if self.connected and self.writer:
            self.writer.write(json.dumps(cmd).encode())
            await self.writer.drain()

    def connect(self):
        if not self.connected:
            asyncio.get_running_loop().create_task(self.listener())

    def disconnect(self):
        self.connected = False

    async def listener(self):
        self.reader, self.writer = await open_serial_connection(url=self.port, baudrate=self.baud)
        try:
            while self.connected:
                in_data = await self.reader.readline()
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
        finally:
            self.connected = False

        self.writer.close()
        await self.writer.wait_closed()

        self.reader = None
        self.writer = None
