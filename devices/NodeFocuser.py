import logging
import time

from indi.device import Driver, non_blocking, properties
from indi.device.pool import default_pool
from indi.message import const
from indi.message import DelProperty
from indi.device.properties.const import DriverInterface
from indi.device.properties import standard
from indi.device.events import on, Write, Change

import settings
import os
import json

if os.environ.get("SIM", None):
    from .hardware.NodeSim import NodeSim as NodeHardware
else:
    from .hardware.NodeSerial import NodeSerial as NodeHardware

logger = logging.getLogger(__name__)


@default_pool.register
class NodeFocuser(Driver):
    name = "NODE_FOCUSER"
    NUM_BOOKMARKS = 10

    MANUAL_MOVES = (10, 50, 100, 500, 1000)
    MIN_POSITION = 0
    MAX_POSITION = 64500

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.focuser = NodeHardware(settings.FOCUSER_PORT, onupdate=self.device_updated)
        self.BOOKMARKS = {}

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
            rel_position=standard.focuser.RelativePosition(),
            fmax=standard.focuser.FocusMax(),
            speed=properties.NumberVector(
                "SPEED",
                elements=dict(
                    speed=properties.Number(
                        "SPEED_VALUE",
                        default=100,
                    )
                ),
            ),
        ),
    )

    bookmarks = properties.Group(
        "BOOKMARKS",
        enabled=False,
        vectors={
            **{
                f"save{i}": properties.TextVector(
                    f"SAVE_BOOKMARK_{i}",
                    elements={
                        f"bookmark{i}": properties.Text(
                            f"SAVE_BOOKMARK_{i}",
                        )
                    },
                )
                for i in range(NUM_BOOKMARKS)
            },
            **dict(
                restore=properties.SwitchVector(
                    "RESTORE_BOOKMARK",
                    rule=const.SwitchRule.AT_MOST_ONE,
                    elements={
                        f"bookmark{i}": properties.Switch(
                            f"RESTORE_BOOKMARK_{i}",
                            default=const.SwitchState.OFF,
                        )
                        for i in range(NUM_BOOKMARKS)
                    },
                ),
            ),
        },
    )

    manual = properties.Group(
        "MANUAL_FOCUS",
        enabled=False,
        vectors=dict(
            inward=properties.SwitchVector(
                "MANUAL_INWARD",
                rule=const.SwitchRule.AT_MOST_ONE,
                elements={
                    f"inward{m}": properties.Switch(
                        f"MANUAL_INWARD_{m}",
                        default=const.SwitchState.OFF,
                    )
                    for m in MANUAL_MOVES
                },
            ),
            outward=properties.SwitchVector(
                "MANUAL_OUTWARD",
                rule=const.SwitchRule.AT_MOST_ONE,
                elements={
                    f"outward{m}": properties.Switch(
                        f"MANUAL_OUTWARD_{m}",
                        default=const.SwitchState.OFF,
                    )
                    for m in MANUAL_MOVES
                },
            ),
        ),
    )

    @on(general.connection.connect, Write)
    @non_blocking
    def connect(self, event):
        value = event.new_value
        connected = value == const.SwitchState.ON
        self.general.connection.state_ = const.State.BUSY

        if connected:
            try:
                self.focuser.connect()
                pos = None
                for _ in range(30):
                    time.sleep(1)
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
        self.bookmarks.enabled = connected
        self.manual.enabled = connected
        self.load_bookmarks()

    def device_updated(self):
        self.position.position.position.state_ = (
            const.State.OK if self.focuser.get_status() == "idle" else const.State.BUSY
        )
        self.position.position.position.value = self.focuser.get_position()


    @on(position.position.position, Write)
    def reposition(self, event):
        value = event.new_value
        self.focuser.set_position(value)

    @on(position.speed.speed, Change)
    def change_speed(self, event):
        self.focuser.set_speed(self.position.speed.speed.value)

    @on(position.rel_position.position, Write)
    def step(self, event):
        value = event.new_value
        self.position.rel_position.position.state_ = const.State.BUSY
        current_position = self.position.position.position.value
        direction = 1 if self.position.motion.outward.bool_value else -1
        new_value = current_position + direction * value

        self.focuser.set_position(new_value)

        self.position.rel_position.position.state_ = const.State.OK

    def _save_file_path(self):
        return os.path.join(os.path.dirname(__file__), "BOOKMARKS.json")

    def save_bookmarks(self):
        with open(self._save_file_path(), "w") as f:
            f.write(json.dumps(self.BOOKMARKS))

    def load_bookmarks(self):
        try:
            with open(self._save_file_path(), "r") as f:
                self.BOOKMARKS = {int(k): v for k, v in json.loads(f.read()).items()}
        except Exception as e:
            print(e)
            pass
        self.refresh_bookmarks()

    def refresh_bookmarks(self):
        for i in range(self.NUM_BOOKMARKS):
            save, restore = self._get_bookmark_elements(i)
            bookmark = self._get_bookmark(i)
            save.value = bookmark["label"]
            restore._definition.label = f'{bookmark["label"]} @ {bookmark["position"]}'

        delmsg = DelProperty(device=self.name, name="RESTORE_BOOKMARK")
        self.send_message(delmsg)
        defmsg = self.bookmarks.restore.to_def_message()
        self.send_message(defmsg)

    def _get_bookmark_elements(self, idx):
        save = getattr(getattr(self.bookmarks, f"save{idx}"), f"bookmark{idx}")
        restore = getattr(self.bookmarks.restore, f"bookmark{idx}")
        return save, restore

    def _get_bookmark(self, idx):
        empty = {
            "label": "Unnamed",
            "position": 0,
        }
        return self.BOOKMARKS.get(idx, empty)

    def save_bookmark_eventhandler(self, event):
        value = event.new_value
        sender = event.element
        idx = int(sender.name.rsplit("_", 1)[-1])
        self.BOOKMARKS[idx] = {
            "label": value,
            "position": self.position.position.position.value,
        }
        self.save_bookmarks()
        self.refresh_bookmarks()

    def restore_bookmark_eventhandler(self, event):
        value = event.new_value
        sender = event.element
        if value == const.SwitchState.ON:
            idx = int(sender.name.rsplit("_", 1)[-1])
            bookmark = self._get_bookmark(idx)
            self.focuser.set_position(bookmark["position"])

            for i in range(self.NUM_BOOKMARKS):
                if i != idx:
                    save, restore = self._get_bookmark_elements(i)
                    restore.value = const.SwitchState.OFF

    def manual_move_eventhandler(self, event):
        sender = event.element
        _, direction, step_size = sender.name.split("_")
        step_size = int(step_size)

        current_position = self.position.position.position.value
        direction = 1 if direction == "OUTWARD" else -1
        new_value = current_position + direction * step_size

        self.focuser.set_position(new_value)

        for d in ("inward", "outward"):
            for m in self.MANUAL_MOVES:
                getattr(
                    getattr(self.manual, d), f"{d}{m}"
                ).value = const.SwitchState.OFF

    for m in MANUAL_MOVES:
        on(getattr(manual.inward, f"inward{m}"), Write)(manual_move_eventhandler)
        on(getattr(manual.outward, f"outward{m}"), Write)(manual_move_eventhandler)

    for i in range(NUM_BOOKMARKS):
        on(getattr(getattr(bookmarks, f"save{i}"), f"bookmark{i}"), Write)(save_bookmark_eventhandler)
        on(getattr(bookmarks.restore, f"bookmark{i}"), Write)(restore_bookmark_eventhandler)
