# kalwy-ao

INDI drivers for the Kalwy observatory, meant to run on Astroberry:

- `tty-focuser.py` — NodeFocuser over the second Raspberry Pi UART (`/dev/ttyAMA2`)
- `tty-lightbox.py` — flat-panel lightbox switched through Home Assistant

Both scripts are [uv](https://docs.astral.sh/uv/) scripts (`#!/usr/bin/env -S uv run --script`). On first start, uv downloads Python 3.12 and the dependencies. `indiserver` launches them as subprocesses.

## Install

Run the steps below as the `astroberry` user unless a command uses `sudo`.

### 1. Clone the repository

```bash
git clone git@github.com:wlatanowicz/kalwy-ao.git /home/astroberry/kalwy-ao
cd /home/astroberry/kalwy-ao
chmod +x tty-focuser.py tty-lightbox.py
```

### 2. Install uv and put it on the default PATH

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

The installer places the binary at `/home/astroberry/.local/bin/uv`. `indiserver` does not include `~/.local/bin` in `PATH`, and the driver shebang looks up `uv` via `/usr/bin/env`. Link it into `/bin`:

```bash
sudo ln -s /home/astroberry/.local/bin/uv /bin/uv
```

### 3. Create the Home Assistant token file

`settings.py` reads `HA_TOKEN` from `.env` in the repository root. Both drivers import that module, so the file is required even when only the focuser is started.

In Home Assistant, open your profile, then **Security** → **Long-lived access tokens** → **Create token**. Copy the token (it is shown once) into `.env`:

```bash
cat > /home/astroberry/kalwy-ao/.env << 'EOF'
HA_TOKEN=paste-the-long-lived-access-token-here
EOF
```

The Home Assistant URL and switch entity are set in `settings.py`:

- `HA_HOST` — `http://192.168.1.11:8123`
- `HA_ENTITY` — `switch.astro_flattner`

Change those if this observatory uses a different host or entity.

### 4. Enable the second UART

The focuser is wired to UART2, which appears as `/dev/ttyAMA2` (`FOCUSER_PORT` in `settings.py`). Add this block to `/boot/config.txt`:

```
[all]
enable_uart=1
dtoverlay=uart2
```

Reboot so the overlay is applied:

```bash
sudo reboot
```

After reboot, `/dev/ttyAMA2` should exist. The `astroberry` user needs access to it:

```bash
sudo usermod -aG dialout astroberry
```

Group membership applies on the next login.

### 5. Register the drivers with INDI

`indi_kalwy.xml` points Ekos and the INDI Web Manager at the two scripts. Copy it into the system driver directory:

```bash
sudo cp /home/astroberry/kalwy-ao/indi_kalwy.xml /usr/share/indi/
```

The file lists **kalwy focuser** and **kalwy lightbox**, and it expects the scripts at `/home/astroberry/kalwy-ao/`.

## Run

Start both drivers under INDI:

```bash
cd /home/astroberry/kalwy-ao
indiserver -v ./tty-focuser.py ./tty-lightbox.py
```

The first launch needs network access while uv installs Python 3.12 and the script dependencies. After the XML file is in `/usr/share/indi`, the same drivers can be started from Ekos or the INDI Web Manager.

## Focuser firmware

The board on the other end of the UART runs the MicroPython code in `contrib/nodefocuser/` (`boot.py` and `focuser.py`). It speaks newline-delimited JSON at 9600 baud. The Pi-side driver only opens the serial port; it does not flash the board.
