# Honk

Vehicle honk detection + geofencing over MQTT.

## Project structure

- `subscriber.py` — Python MQTT subscriber. Listens on `car/telemetry/horn`, runs ray-casting geofence check, logs to `events_log.csv` and `raw_packets.log`.
- `Arduino_ide/` — ESP32 firmware variants. `ACS_NEO_ESP32.ino` is the main active sketch (GPS + ACS712 current sensor on GPIO 34 for horn detection, publishes every 1s).

## Setup & run

```bash
uv sync          # install numpy, paho-mqtt, pandas
uv run subscriber.py   # requires MQTT broker on localhost:1883
```

- Python >=3.12 required (`.python-version`). Package manager is `uv`.
- Files `events_log.csv` and `raw_packets.log` are auto-created at startup in CWD.
- Geofence zones defined inline in `subscriber.py:SILENCE_ZONES`.

## Arduino

- Flash `Arduino_ide/ACS_NEO_ESP32.ino` via Arduino IDE.
- Edit `ssid`, `password`, `mqtt_ip` at the top of the sketch.
- GPS on UART2 (RX=16, TX=17) at 9600 baud. ACS712 on GPIO 34.

## Listen / debug

```bash
mosquitto_sub -h localhost -t "car/telemetry/horn"
```

## Conventions

- No tests, no CI, no lint/typecheck config.
- Subscriber writes to CWD — run from a consistent directory.
- `uv run subscriber.py` as a one-shot; daemonize or supervise externally.
