import logging
import asyncio

from indi.device import Driver, properties
from indi.device.pool import default_pool
from indi.message import const
from indi.device.properties.const import DriverInterface
from indi.device.properties import standard
from indi.device.events import on, Write, Change

import settings

from .hardware.NodeSerial import NodeSerial as NodeHardware

logger = logging.getLogger(__name__)


@default_pool.register
class Focuser(Driver):
    name = "NodeFocuser"

    MIN_POSITION = 0
    MAX_POSITION = 64500
    MIN_SPEED = 10
    MAX_SPEED = 300

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.focuser = NodeHardware(settings.FOCUSER_PORT, onupdate=self.device_updated)

    general = properties.Group(
        "GENERAL",
        vectors=dict(
            connection=standard.common.Connection(),
            driver_info=standard.common.DriverInfo(
                interface=(DriverInterface.FOCUSER,)
            ),
            info=properties.TextVector(
                "INFO",
                enabled=False,
                perm=const.Permissions.READ_ONLY,
                elements=dict(
                    manufacturer=properties.Text(
                        "MANUFACTURER", default="Wiktor Latanowicz"
                    ),
                    camera_model=properties.Text(
                        "FOCUSER_MODEL", default="NodeFocuser"
                    ),
                    ip=properties.Text("IP_ADDRESS", default=settings.FOCUSER_IP),
                ),
            ),
        ),
    )

    position = properties.Group(
        "POSITION",
        enabled=False,
        vectors=dict(
            position=standard.focuser.AbsolutePosition(min=MIN_POSITION, max=MAX_POSITION, step=1),
            motion=standard.focuser.FocusMotion(),
            rel_position=standard.focuser.RelativePosition(
                min=1, max=MAX_POSITION - MIN_POSITION, step=1
            ),
            fmax=properties.NumberVector(
                "FOCUS_MAX",
                perm=const.Permissions.READ_ONLY,
                elements=dict(
                    max=properties.Number(
                        "FOCUS_MAX_VALUE",
                        default=MAX_POSITION,
                        min=MIN_POSITION,
                        max=MAX_POSITION,
                        step=1,
                    )
                ),
            ),
            speed=properties.NumberVector(
                "SPEED",
                elements=dict(
                    speed=properties.Number(
                        "SPEED_VALUE",
                        default=100,
                        min=MIN_SPEED,
                        max=MAX_SPEED,
                        step=1,
                    )
                ),
            ),
        ),
    )

    @on(general.connection.connect, Write)
    async def connect(self, event):
        event.prevent_default = True
        value = event.new_value
        connected = value == const.SwitchState.ON
        self.general.connection.state_ = const.State.BUSY

        if connected:
            try:
                self.focuser.connect()
                pos = None
                for _ in range(30):
                    await asyncio.sleep(1)
                    pos = self.focuser.get_position()
                    if pos is not None:
                        self.position.position.position.reset_value(pos)
                        break
                if pos is None:
                    raise Exception("Did not get focuser position")
                self.general.connection.state_ = const.State.OK
            except Exception as e:
                self.general.connection.state_ = const.State.ALERT
                connected = False
                logger.error(e)

        self.general.connection.connect.bool_value = connected
        self.position.enabled = connected
        self.general.info.enabled = connected

    @on(position.position.position, Write)
    def reposition(self, event):
        event.prevent_default = True
        value = event.new_value
        self.focuser.set_position(value)

    @on(position.speed.speed, Change)
    def change_speed(self, event):
        self.focuser.set_speed(self.position.speed.speed.value)

    @on(position.rel_position.position, Write)
    def step(self, event):
        value = event.new_value
        current_position = self.position.position.position.value
        direction = 1 if self.position.motion.outward.bool_value else -1
        target = round(current_position + direction * value)
        relative = self.position.rel_position

        if target < self.MIN_POSITION or target > self.MAX_POSITION:
            relative.state_ = const.State.ALERT
            return

        if target == round(current_position) and self.focuser.get_status() == "idle":
            if relative.state_ != const.State.OK:
                relative.state_ = const.State.OK
            return

        relative.state_ = const.State.BUSY
        self.focuser.set_position(target)

    def device_updated(self):
        status = self.focuser.get_status()
        position = self.focuser.get_position()
        absolute = self.position.position

        if status == "move":
            if absolute.state_ != const.State.BUSY:
                absolute.state_ = const.State.BUSY
            absolute.position.value = position
        elif status == "idle":
            absolute.position.value = position
            if absolute.state_ != const.State.OK:
                absolute.state_ = const.State.OK
            relative = self.position.rel_position
            if relative.state_ != const.State.OK:
                relative.state_ = const.State.OK
