import logging
import time

from indi.device import Driver, non_blocking, properties
from indi.device.pool import default_pool
from indi.message import const
from indi.device.properties.const import DriverInterface
from indi.device.properties import standard

import settings
from .hardware.NodeMCU import NodeMCU

logger = logging.getLogger(__name__)


@default_pool.register
class NodeFocuser(Driver):
    name = "NODE_FOCUSER"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.focuser = NodeMCU(settings.FOCUSER_IP)

    general = properties.Group(
        "GENERAL",
        vectors=dict(
            connection=standard.common.Connection(),
            driver_info = standard.common.DriverInfo(interface=(DriverInterface.FOCUSER,)),
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
    general.connection.connect.onwrite = "connect"

    position = properties.Group(
        "POSITION",
        enabled=False,
        vectors=dict(
            position=standard.focuser.AbsolutePosition(min=0, max=5000, step=1),
            motion=standard.focuser.FocusMotion(),
            rel_position=standard.focuser.RelativePosition(),
            fmax=standard.focuser.FocusMax(),
        ),
    )
    position.position.position.onwrite = "reposition"
    position.rel_position.position.onwrite = "step"

    @non_blocking
    def connect(self, sender, value):
        connected = value == const.SwitchState.ON
        self.general.connection.state_ = const.State.BUSY

        if connected:
            try:
                self.position.position.position.reset_value(self.focuser.get_position())
                self.general.connection.state_ = const.State.OK
            except Exception as e:
                self.general.connection.state_ = const.State.ALERT
                connected = False
                logger.error(e)

        self.general.connection.connect.bool_value = connected
        self.position.enabled = connected
        self.general.info.enabled = connected


    @non_blocking
    def reposition(self, sender, value):
        self._move(value)


    @non_blocking
    def step(self, sender, value):
        self.position.rel_position.position.state_ = const.State.BUSY
        current_position = self.position.position.position.value
        direction = 1 if self.position.motion.outward.bool_value else -1
        new_value = current_position + direction * value
        self._move(new_value)
        self.position.rel_position.position.state_ = const.State.OK


    def _move(self, target):
        self.position.position.state_ = const.State.BUSY
        try:
            self.focuser.set_position(target, wait=False)
            while (
                abs(float(self.position.position.position.value) - float(target)) > 0.01
            ):
                time.sleep(1)
                self.position.position.position.value = self.focuser.get_position()

            self.position.position.state_ = const.State.OK
        except Exception as e:
            self.position.position.state_ = const.State.ALERT
            logger.error(e)
