import logging
import time

from indi.device import Driver, non_blocking, properties
from indi.device.pool import default_pool
from indi.message import const
from indi.message import DelProperty
from indi.device.properties.const import DriverInterface
from indi.device.properties import standard
from indi.device.events import on, Write, Change

from .hardware.HomeAssistantLight import HomeAssistantLight

import settings
import os
import json

logger = logging.getLogger(__name__)


@default_pool.register
class Flattener(Driver):
    name = "Flattener"

    general = properties.Group(
        "GENERAL",
        vectors=dict(
            connection=standard.common.Connection(),
            driver_info=standard.common.DriverInfo(
                interface=(DriverInterface.LIGHTBOX,)
            ),
            info=properties.TextVector(
                "INFO",
                enabled=False,
                perm=const.Permissions.READ_ONLY,
                elements=dict(
                    manufacturer=properties.Text(
                        "MANUFACTURER", default="Wiktor Latanowicz"
                    ),
                    model=properties.Text(
                        "LIGHTBOX_MODEL", default="Lightbox"
                    ),
                ),
            ),
        ),
    )

    main_control = properties.Group(
        "MAIN_CONTROL",
        enabled=False,
        vectors=dict(
                light_control=properties.SwitchVector(
                    "FLAT_LIGHT_CONTROL",
                    rule=const.SwitchRule.ONE_OF_MANY,
                    elements=dict(
                        on=properties.Switch(
                            "FLAT_LIGHT_ON",
                            default=const.SwitchState.OFF,
                        ),
                        off=properties.Switch(
                            "FLAT_LIGHT_OFF",
                            default=const.SwitchState.ON,
                        ),
                    )
                ),
            ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.backend = HomeAssistantLight(
            ha_host=settings.HA_HOST,
            ha_token=settings.HA_TOKEN,
            ha_entity=settings.HA_ENTITY,
            on_update=self.on_update,
        )

    @on(general.connection.connect, Write)
    @non_blocking
    def connect(self, event):
        value = event.new_value
        connected = value == const.SwitchState.ON
        self.general.connection.state_ = const.State.BUSY

        if connected:
            self.main_control.light_control.state_ = const.State.BUSY
            self.backend.connect()

        self.general.connection.connect.bool_value = connected
        self.general.info.enabled = connected
        self.main_control.enabled = connected
        self.general.connection.state_ = const.State.OK

    @on(main_control.light_control.on, Write)
    @on(main_control.light_control.off, Write)
    @non_blocking
    def toggle(self, event):
        event.prevent_default = True
        if event.element.name == self.main_control.light_control.on.name:
            state = event.new_value == const.SwitchState.ON
        else:
            state = not event.new_value == const.SwitchState.ON
        self.main_control.light_control.state_ = const.State.BUSY
        try:
            self.backend.set_state(state)
        except Exception as ex:
            logger.exception("Error setting switch state in HA")
            self.main_control.light_control.state_ = const.State.ALERT

    def on_update(self):
        state = self.backend.current_state

        if state == "on":
            self.main_control.light_control.on.bool_value = True
            self.main_control.light_control.state_ = const.State.OK
        elif state == "off":
            self.main_control.light_control.off.bool_value = True
            self.main_control.light_control.state_ = const.State.OK
        else:
            self.main_control.light_control.state_ = const.State.ALERT
