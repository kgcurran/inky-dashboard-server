This is the backend server repository for my E-paper dashboard project, [Inky Dashboard](https://github.com/jaeheonshim/inky-dashboard). It's a Flask webserver that pulls events from iCal feeds and tasks from the Todoist API, and exposes them as a CBOR payload, an HTML dashboard, or a pre-rendered 800×480 PNG that the Pico W powering the Inky Frame can fetch directly, as my frame is currently grabbing other images also

## How to use

Create a file named `calendar_settings.py` in the src directory. Below is a template for you to use when specifying settings in the file.

```py
from zoneinfo import ZoneInfo

# In ([ICS_URL], [color]) format where [color] is an int corresponding to one of the 7 inky frame colors
# BLACK     0
# WHITE     1
# GREEN     2
# BLUE      3
# RED       4
# YELLOW    5
# ORANGE    6

calendars = [
    ("https://example.com/example_calendar.ics", 6),
]

# Your current timezone
timezone = ZoneInfo("America/New_York")

# Todoist API key
todoist_api_key = "[insert Todoist API key here]"
```

## Endpoints

| Endpoint | Description |
| --- | --- |
| `GET /` | CBOR-encoded payload `{"hd", "cal", "tsk"}` for clients that render the dashboard themselves. |
| `GET /dashboard.html` | HTML dashboard (live preview in a browser, 800×480). Also served at `/home`. |
| `GET /dashboard.png` | 800×480 PNG of the dashboard rendered with Pillow. Returns `ETag` and `Cache-Control: no-cache`. Send `If-None-Match: <etag>` to get a `304 Not Modified` when nothing has changed. |
| `GET /dashboard.png?palette=inky` | Same image, quantized to the Inky Frame's 7-color palette with Floyd–Steinberg dithering. Smaller file (≈5 KB), ready to blit on-device without further processing. |
| `GET /calendar.png` | Calendar-only PNG (no task panel) for an Inky Frame mounted in portrait orientation. Rendered as 480×800 then rotated 90° counter-clockwise into an 800×480 buffer so the Pico can blit it without further processing. Same ETag / `If-None-Match` / `?palette=inky` behavior as `/dashboard.png`. |
| `GET /dashboard.version` | JSON `{"version": "<md5>"}` — a cheap hash of the rendered payload. Pass `?palette=inky` to get the same hash that `/dashboard.png?palette=inky` uses. Useful for clients whose HTTP libraries don't easily handle ETag round-trips. |

The version hash covers the header, task list, calendar payload, and the requested palette, so any change in displayed content produces a new version.

## Pulling the image from the Inky Frame

A minimal MicroPython fetch loop on the Pico W. Compare the cached version against `/dashboard.version` first; only download the PNG when something has actually changed.

```python
import urequests

SERVER = "http://192.168.1.50:5000"
VERSION_FILE = "dashboard.version"
IMAGE_FILE = "dashboard.png"


def read_version():
    try:
        with open(VERSION_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def write_file(path, data, mode="w"):
    with open(path, mode) as f:
        f.write(data)


def refresh_dashboard():
    last = read_version()
    r = urequests.get(SERVER + "/dashboard.version?palette=inky")
    current = r.json()["version"]
    r.close()
    if current == last:
        return False  # nothing to do

    img = urequests.get(SERVER + "/dashboard.png?palette=inky")
    write_file(IMAGE_FILE, img.content, mode="wb")
    img.close()
    write_file(VERSION_FILE, current)
    return True


if refresh_dashboard():
    # Hand the file off to your Inky Frame display routine.
    pass
```

If your HTTP client supports it, you can skip the version endpoint and use `If-None-Match` directly against `/dashboard.png?palette=inky`; the server returns `304 Not Modified` (headers only, ~150 bytes) when the dashboard hasn't changed.

## Running on a Raspberry Pi

### Install

```sh
git clone https://github.com/jaeheonshim/inky-dashboard-server.git
cd inky-dashboard-server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then create `src/calendar_settings.py` as described above.

Smoke-test it:

```sh
.venv/bin/python src/server.py
```

Open `http://<pi-ip>:5000/dashboard.html` from another machine on your LAN to confirm the dashboard renders.

### Run as a background service (systemd)

Use a production WSGI server rather than Flask's dev server. Install `gunicorn` once:

```sh
.venv/bin/pip install gunicorn
```

Create `/etc/systemd/system/inky-dashboard.service` (replace `pi` with your username and the project path if different):

```ini
[Unit]
Description=Inky Dashboard server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/inky-dashboard-server/src
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/pi/inky-dashboard-server/.venv/bin/gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --timeout 60 \
    server:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now inky-dashboard.service
```

Useful operations:

```sh
sudo systemctl status inky-dashboard      # running?
sudo journalctl -u inky-dashboard -f      # tail logs
sudo systemctl restart inky-dashboard     # after editing code or settings
```

The service will start automatically on boot and restart itself if it crashes. Point the Pico W at `http://<pi-ip>:5000/dashboard.png?palette=inky`.
