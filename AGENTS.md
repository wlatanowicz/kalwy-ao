# kalwy-ao

INDI drivers for the Kalwy observatory, launched by `indiserver` on Astroberry. Install steps live in `README.md`. This file is for agents changing the code.

## Shape

Two uv scripts (`#!/usr/bin/env -S uv run --script`, Python `>=3.12`) speak INDI XML on stdin/stdout through `indi.transport.server.TTY`. Dependencies are the PEP 723 block at the top of each script: `indipy>=0.4.0b1`, `pyserial-asyncio`, `requests`, `django-environ`. Keep those two blocks identical when adding a dependency. `requirements.txt` is not what the scripts install. There is no `pyproject.toml` and no test suite. `devices/` has no `__init__.py` (implicit namespace package); import `devices.Focuser` and `devices.Flattener` directly.

## Live entry points

- `tty-focuser.py` imports `devices.Focuser.Focuser` (`name = "NodeFocuser"`), then calls `default_pool.init(router)`.
- `tty-lightbox.py` does the same for `devices.Flattener.Flattener` (`name = "Flattener"`, INDI interface `LIGHTBOX`).
- `indi_kalwy.xml` registers both with absolute paths under `/home/astroberry/kalwy-ao/`. Leave those paths absolute.
- `server.py` is a leftover standalone TCP server (`from devices import *`, unused `aiohttp` snippet). It is not in the XML and is not a production entry point.

## Driver pattern

A device is an indipy `Driver` subclass decorated with `@default_pool.register`. The entry script must import that module before `default_pool.init`; the import is what registers the class. Properties are class-level `properties.Group` trees. Behavior is `@on(element, Write)` and `@on(element, Change)` handlers. A new driver needs its own uv script, and an XML `<device>` if Ekos should see it. When the indipy API is unclear, read the installed package (`indi.device`, `indi.transport.server.tty`) instead of guessing.

## Focuser

`devices/Focuser.py` uses `devices/hardware/NodeSerial.py`, which opens `settings.FOCUSER_PORT` (`/dev/ttyAMA2`) at 9600 baud. `FOCUSER_IP` is only the read-only `INFO.IP_ADDRESS` text; the driver does not connect over the network.

Commands are one JSON object per write, with no trailing newline on the Pi side: `{"position": n}`, `{"speed": n}`, `{"reset": n}`. The board answers with newline-terminated `{"status": {"position", "direction", "status"}}`, where `status` is `idle` or `move`. `NodeSerial` ignores `ack` and `error` lines and calls `onupdate` only when the status dict changes. Connect waits up to 30 seconds for the first position.

## Firmware

`contrib/nodefocuser/` is MicroPython (`machine`, `uos`), not CPython. `boot.py` starts WebREPL and `focuser.py`. The Pi driver does not flash the board. Do not rewrite this tree with CPython-only APIs, and do not run it under uv.

Position limits `0`–`64500` are duplicated in `Focuser.MIN_POSITION` / `MAX_POSITION` and `Device.MIN_POSITION` / `MAX_POSITION`. Change both together. Firmware speed is clamped to `10`–`300` (default `250`). The INDI speed property defaults to `100` and does not clamp. The firmware accepts `{"park": true}`; the Pi driver never sends it.

## Lightbox

`devices/Flattener.py` uses `devices/hardware/HomeAssistantLight.py`: `POST /api/services/switch/turn_on|turn_off` and `GET /api/states/{entity}`, Bearer token, 2s timeout, poll every 60s. Host, token, and entity come from `settings.py`. `HA_TOKEN` is read from `.env` at import time, so the focuser process needs `.env` too. `HA_ENTITY` is `switch.astro_flattner` — that is the live Home Assistant entity id, spelling included. Do not rename it to match the Python class.

## Constraints

- Identifiers, comments, logs, and docs stay in English.
- Do not commit `.env` or print `HA_TOKEN`.
- Do not start the drivers or the firmware against the observatory UART or Home Assistant unless asked. Connect and light commands move real hardware.
- `LOG_LEVEL` controls the console handler (default `INFO`). The INDI log handler in both tty scripts stays commented out so INDI XML remains the only stdout.
