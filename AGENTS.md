# Honk

Vehicle honk detection + geofence monitoring + context-aware validation. ESP32 publishes GPS/horn telemetry over MQTT; Python subscriber validates geofence, logs events; downstream camera component uses YOLO to justify honks inside silence zones.

## Setup & run

```bash
uv sync                          # install numpy, paho-mqtt, pandas
uv run subscriber.py             # start subscriber (needs broker on localhost:1883)
mosquitto_sub -h localhost -t "car/telemetry/horn"   # debug ESP32 output
```

Subscriber auto-creates `events_log.csv` and `raw_packets.log` in CWD.

## Project layout

- `Arduino_ide/ACS_NEO_ESP32.ino` — main firmware (flash via Arduino IDE)
- `subscriber.py` — MQTT subscriber, ray-casting geofence, debounce, CSV logger
- `events_log.csv` / `raw_packets.log` — runtime data files

## ESP32 firmware

**Config at top of sketch** — edit before flashing:
- `ssid`, `password`, `mqtt_ip` (WiFi + broker)
- `HDOP_THRESHOLD` (default 6.0, skip fix above this)
- `GPS_WINDOW_SIZE` (default 5, ring buffer for centroid averaging)
- `HORN_THRESHOLD` (default 2690, TODO: calibrate on real vehicle)

**GPS**: UART2 (RX=16, TX=17) at 9600 baud. **ACS712**: GPIO 34.

**JSON payload fields** (preserve all):
`timestamp`, `car_id`, `lat`, `lon`, `horn`, `hdop`, `satellites`, `adc`, `gps_age`, `gps_valid`

- Ring buffer averages lat/lon before publishing. Buffer must fill before first publish.
- JSON must always include all fields above. Add new fields, never remove.
- `client.publish()` result is checked — serial prints "Published" or "Publish Failed".

## Subscriber

**Config constants** at top of `subscriber.py`:
- `DEBOUNCE_COUNT` (default 3, consecutive inside/outside readings to flip geofence state)
- `SILENCE_ZONES` (polygon vertices, hardcoded)

**Behavior**:
- Every packet → CSV row + raw_packets.log. Never remove existing CSV columns.
- Console print only on state transitions (outside↔inside) or horn ON (OFF→ON).
- Tracks `last_zone` so exit messages say `"Vehicle exited Hospital Zone."` not `None`.
- Geofence uses ray casting. Hardware/horn logic stays on ESP32; Python never calculates horn state.
- Bad GPS filtered by HDOP > 6 or satellites < 4 or `gps_valid` false (silent drop, no CSV row).
- CSV includes `event_type` (ENTER/EXIT/HONK/NORMAL), `distance_to_zone` (meters, negative = inside), `packet_count`.

## Conventions

- No tests, no CI, no lint/typecheck config.
- `uv sync` before running. Python >=3.12.
- ESP32 publishes, Python subscribes. Python never publishes.
- Small functions, early returns, minimal globals. No classes unless they simplify.
- Do not replace TinyGPS++. Horn detection independent from geofencing.

## Future: camera-based honk justification

Downstream component (e.g. Raspberry Pi + camera) validates honks inside silence zones:

```
[Horn inside zone] → capture forward-facing frame → YOLO inference → Justified? (object present)
```

- Honk is **justified** if YOLO detects a vehicle, pedestrian, or obstacle in front
- Honk is **unjustified** (violation) if nothing is detected
- The subscriber CSV provides the trigger (HONK event + timestamp + location) for frame lookup
- This component is **not yet implemented** — the subscriber CSV is your structured dataset to feed into it
