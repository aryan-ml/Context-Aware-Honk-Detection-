<div align="center">

# 🚗 Context-Aware Honk Detection & Violation Enforcement System

### Real-Time Horn Monitoring × Geofenced Silence Zones × Visual Justification

**A research-grade embedded IoT + Computer Vision pipeline that detects vehicle horn activation inside restricted silence zones (hospitals, schools, courts) and determines whether the honk was contextually justified — using real-time GPS geofencing, in-circuit current sensing, and YOLO-based object detection.**

---

<!-- 
📸 HERO IMAGE PLACEHOLDER
Add a high-level system photo or banner here, e.g.:
![System Banner](assets/banner.png)
-->

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![ESP32](https://img.shields.io/badge/ESP32-Firmware-E7352C?style=for-the-badge&logo=espressif&logoColor=white)](https://www.espressif.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge&logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org/)
[![YOLO](https://img.shields.io/badge/YOLOv11-Detection-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)](https://docs.ultralytics.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

</div>

---

## 📋 Table of Contents

- [The Problem](#-the-problem)
- [Our Solution](#-our-solution)
- [System Architecture](#-system-architecture)
- [Hardware Components](#-hardware-components)
- [Software Stack](#-software-stack)
- [How It Works — End to End](#-how-it-works--end-to-end)
- [Geofencing Deep Dive](#-geofencing-deep-dive)
- [Horn Detection — Electrical Approach](#-horn-detection--electrical-approach)
- [Computer Vision — Honk Justification](#-computer-vision--honk-justification)
- [Data Pipeline & Logging](#-data-pipeline--logging)
- [Getting Started](#-getting-started)
- [Project Structure](#-project-structure)
- [Configuration Reference](#-configuration-reference)
- [Sample Output](#-sample-output)
- [Future Roadmap](#-future-roadmap)
- [Contributing](#-contributing)

---

## 🚨 The Problem

Noise pollution from unnecessary vehicle honking is a **serious public health issue**, especially around:

- 🏥 **Hospitals** — patients need silence for recovery
- 🏫 **Schools** — children deserve distraction-free learning
- ⚖️ **Courts** — legal proceedings require silence
- 🛕 **Religious Places** — sacred spaces demand quiet

Despite "No Honking" signs, enforcement is nearly **impossible** with traditional methods. Traffic police can't be everywhere, and CCTV footage alone cannot determine *which specific vehicle* honked or *whether the honk was justified* (e.g., a pedestrian suddenly stepped onto the road).

> **There is no existing system that can simultaneously identify a specific vehicle's horn activation, verify its GPS location within a restricted zone, and determine whether the honk was contextually justified.**

---

## 💡 Our Solution

**Honk** is a full-stack IoT + CV system that solves all three problems at once:

| Capability | How |
|---|---|
| **🎯 Horn Detection** | ACS712 current sensor tapped into the vehicle's horn circuit — detects the exact moment the horn is pressed by measuring current draw |
| **📍 Location Tracking** | NEO-6M GPS module provides real-time latitude/longitude with HDOP-based quality filtering |
| **🔲 Geofence Monitoring** | Ray-casting algorithm checks if the vehicle is inside any defined silence zone polygon |
| **🧠 Justification via CV** | YOLOv11 object detection on a forward-facing camera feed — if a pedestrian/obstacle is detected, the honk is classified as **justified**; otherwise, it's a **violation** |
| **📡 Real-Time Telemetry** | ESP32 publishes JSON packets over MQTT every second; Python subscriber processes, logs, and classifies events |

### The Core Idea

```
Horn pressed inside silence zone?
├── YES → Was there a pedestrian/obstacle in front?
│   ├── YES → ✅ Justified (safety honk)
│   └── NO  → ❌ Unjustified (violation — penalize)
└── NO  → ℹ️ Normal driving (log only)
```

---

## 🏗 System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        VEHICLE (Edge)                            │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐    │
│  │  NEO-6M GPS │    │  ACS712      │    │  12V Car Battery │    │
│  │  Module      │    │  Current     │    │       │          │    │
│  │  (UART2)     │    │  Sensor      │    │  Buck Converter  │    │
│  └──────┬──────┘    └──────┬───────┘    │  (12V → 5V)      │    │
│         │                  │            └──────┬───────────┘    │
│         │ RX=16,TX=17      │ GPIO 34           │ VIN            │
│         └──────────┬───────┴───────────────────┘               │
│                    │                                             │
│              ┌─────┴─────┐                                      │
│              │   ESP32    │                                      │
│              │ DevKit V1  │                                      │
│              └─────┬──────┘                                     │
│                    │ WiFi                                        │
└────────────────────┼────────────────────────────────────────────┘
                     │ MQTT (car/telemetry/horn)
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SERVER (Laptop / RPi)                          │
│                                                                  │
│  ┌────────────┐    ┌──────────────────┐    ┌─────────────────┐  │
│  │ Mosquitto  │───▶│  subscriber.py   │───▶│  events_log.csv │  │
│  │ MQTT Broker│    │  (Python 3.12+)  │    │  raw_packets.log│  │
│  └────────────┘    └────────┬─────────┘    └─────────────────┘  │
│                             │                                    │
│                    ┌────────┴─────────┐                         │
│                    │  YOLOv11 Thread  │                         │
│                    │  (camera.py /    │                         │
│                    │   detection_loop)│                         │
│                    └────────┬─────────┘                         │
│                             │                                    │
│                    ┌────────┴─────────┐                         │
│                    │  Phone Camera    │                         │
│                    │  (DroidCam/IP)   │                         │
│                    └──────────────────┘                         │
└──────────────────────────────────────────────────────────────────┘
```

<!-- 
📸 ARCHITECTURE DIAGRAM PLACEHOLDER
Add a clean architecture diagram image here:
![Architecture](assets/architecture.png)
-->

---

## 🔧 Hardware Components

| Component | Role | Specs |
|---|---|---|
| **ESP32 DevKit V1** | Microcontroller — WiFi, MQTT publishing, sensor reading | Dual-core, 240 MHz, built-in WiFi |
| **NEO-6M GPS Module** | Real-time location tracking | UART @ 9600 baud, connected to GPIO 16 (RX) & 17 (TX) |
| **ACS712 Current Sensor** | Horn detection via current draw on horn circuit | Analog output to GPIO 34, threshold-based detection |
| **Buck Converter** | Steps down car battery voltage for ESP32 | 12V DC (car battery) → 5V DC (ESP32 VIN) |
| **Phone Camera** | Forward-facing video feed for CV inference | IP camera stream via DroidCam (HTTP MJPEG) |

### Wiring Overview

```
  12V Car Battery
       │
       ├──► Buck Converter ──► 5V ──► ESP32 VIN
       │
       └──► Horn Circuit ──► ACS712 OUT ──► ESP32 GPIO 34
  
  NEO-6M GPS TX ──► ESP32 GPIO 16 (RX2)
  NEO-6M GPS RX ──► ESP32 GPIO 17 (TX2)
```

<!-- 
📸 HARDWARE PHOTOS PLACEHOLDER
Add photos of your actual wired-up circuit here:
![Circuit Photo](assets/circuit_photo.jpg)
![Wiring Diagram](assets/wiring_diagram.png)
-->

---

## 💻 Software Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Firmware** | Arduino C++ (ESP32) | Sensor reading, GPS parsing, MQTT publish |
| **Communication** | MQTT (Mosquitto) | Lightweight pub/sub telemetry transport |
| **Subscriber** | Python 3.12+ | Geofencing, event classification, CSV logging |
| **GPS Parsing** | TinyGPS++ | NMEA sentence decoding on ESP32 |
| **Serialization** | ArduinoJson / Python `json` | Structured JSON telemetry packets |
| **Object Detection** | YOLOv11n (Ultralytics) | Pedestrian/obstacle detection for honk justification |
| **Video** | OpenCV | Camera stream capture and frame display |

---

## ⚙ How It Works — End to End

### Step 1: Edge Sensing (ESP32)

Every **1 second**, the ESP32:

1. **Reads GPS** — parses NMEA sentences from NEO-6M via TinyGPS++
2. **Filters quality** — skips if HDOP > 6.0 or no valid fix
3. **Averages position** — maintains a ring buffer of 5 GPS fixes and computes the centroid (smooths jitter)
4. **Reads horn** — samples the ACS712 analog output (GPIO 34); if ADC < threshold → horn is active
5. **Publishes JSON** — sends a structured packet over MQTT to `car/telemetry/horn`

**Sample MQTT Payload:**
```json
{
  "timestamp": 318958,
  "car_id": "CAR_001",
  "lat": 22.323350,
  "lon": 73.136290,
  "horn": true,
  "hdop": 1.6,
  "satellites": 4,
  "adc": 0,
  "gps_age": 612,
  "gps_valid": true
}
```

### Step 2: Server Processing (subscriber.py)

On each incoming MQTT message:

1. **Validates GPS** — drops packets with `gps_valid=false`, HDOP > 6, or satellites < 4
2. **Checks geofence** — ray-casting algorithm against polygon-defined silence zones
3. **Debounces state** — requires 3 consecutive inside/outside readings to flip geofence state (prevents GPS jitter false positives)
4. **Classifies event** — `ENTER`, `EXIT`, `HONK`, or `NORMAL`
5. **Queries CV thread** — if it's a `HONK` event, checks whether a person was detected within the last 2 seconds → justified or violation
6. **Logs everything** — appends to `events_log.csv` and `raw_packets.log`

### Step 3: Computer Vision (YOLOv11 Thread)

A background thread continuously:

1. **Captures frames** from the IP camera stream
2. **Runs YOLOv11n** inference for person detection (class 0)
3. **Updates a shared timestamp** (`last_person_seen`) whenever a person is detected with confidence ≥ 0.5
4. The MQTT callback **reads this timestamp** to determine justification

---

## 🗺 Geofencing Deep Dive

### Polygon-Based Silence Zones

Silence zones are defined as **polygons** (list of lat/lon vertices) in `subscriber.py`. The system supports multiple zones:

```python
SILENCE_ZONES = {
    "Hospital Zone": [
        (22.3237, 73.1361),
        (22.3236, 73.1357),
        (22.3238, 73.1357),
        (22.3238, 73.1360)
    ],
    # Add more zones as needed...
}
```

### Ray-Casting Algorithm

To determine if a GPS point is inside a polygon, we use the **ray-casting algorithm**:

- Cast a horizontal ray from the point to infinity
- Count how many polygon edges the ray crosses
- **Odd crossings** → inside; **Even crossings** → outside

### Debounced State Machine

GPS signals are noisy. A single reading might flicker between inside/outside near a zone boundary. The system uses a **debounce counter** (default: 3) — the geofence state only flips after 3 consecutive identical readings.

```
Reading:   IN  IN  OUT  IN  IN  IN  →  State flips to INSIDE (3 consecutive IN)
Reading:   OUT OUT OUT  IN  OUT OUT →  State flips to OUTSIDE (3 consecutive OUT)
```

### Distance Calculation

Every packet also computes the **signed distance to the nearest zone boundary** (in meters):
- **Negative** = inside the zone (e.g., `-12.5m` means 12.5m inside)
- **Positive** = outside the zone

---

## ⚡ Horn Detection — Electrical Approach

### Why Current Sensing?

Unlike microphone-based approaches (which pick up ambient noise and can't attribute a honk to a specific vehicle), this system taps **directly into the vehicle's horn circuit** using an **ACS712 current sensor**.

### How It Works

```
Car Battery (12V) ──► Horn Relay ──► ACS712 ──► Horn
                                        │
                                   Analog Out ──► ESP32 GPIO 34
```

1. When the horn button is pressed, current flows through the ACS712
2. The ACS712 outputs an analog voltage proportional to the current
3. The ESP32 reads the ADC value on GPIO 34
4. If the ADC drops below the calibrated threshold (`HORN_THRESHOLD = 2690`), the horn is flagged as **active**

> ⚠️ **Calibration Required**: The `HORN_THRESHOLD` value must be calibrated for each specific vehicle. Use the `ACS_DeskCheck_MinVal.ino` sketch to observe ADC readings with the horn on/off and set the threshold accordingly.

### Desk Check Sketch

`Arduino_ide/ACS_DeskCheck_MinVal.ino` is a minimal sketch that continuously prints ADC values to Serial Monitor — use it to find the right threshold before deploying the full firmware.

---

## 🎥 Computer Vision — Honk Justification

> [!WARNING]
> **Work in Progress** — The CV justification pipeline is functional but experimental. Current limitations include single-class detection (person only), reliance on a phone camera stream, and a fixed 2-second detection window. Active research is ongoing to expand object classes, improve inference latency, and move toward a dedicated on-vehicle camera.

### The Logic

Not every honk inside a silence zone is a violation. If a pedestrian steps in front of the vehicle, the driver **must** honk for safety. The CV pipeline determines this:

| Scenario | Detection | Verdict |
|---|---|---|
| Horn ON + Inside Zone + Person Detected | ✅ Person in frame | **Justified** (safety honk) |
| Horn ON + Inside Zone + No Person | ❌ Nothing in frame | **Unjustified** (violation) |
| Horn ON + Outside Zone | — | **Normal** (not in restricted area) |

### YOLOv11n Pipeline

- **Model**: `yolo11n.pt` (nano variant — fast inference, suitable for real-time)
- **Target Classes**: `[0]` (person only, from COCO dataset)
- **Confidence Threshold**: `0.5`
- **Detection Window**: `2.0 seconds` — if a person was seen within the last 2 seconds of a honk event, the honk is justified

### Camera Setup

The system currently uses a **phone camera** (via DroidCam) streaming over HTTP:

```
Phone (DroidCam) ──► HTTP MJPEG stream ──► OpenCV VideoCapture ──► YOLO
```

> 💡 **Planned improvements**: Replace phone camera with a dedicated forward-facing camera (e.g., Raspberry Pi Camera Module) mounted on the dashboard. Expand target classes to include vehicles, animals, and other road obstacles for more comprehensive justification.

<!-- 
📸 CV DETECTION SCREENSHOTS PLACEHOLDER
Add screenshots showing YOLO detections:
![Person Detected](assets/yolo_person_detected.png)
![No Person](assets/yolo_no_detection.png)
-->

---

## 📊 Data Pipeline & Logging

### Events Log (`events_log.csv`)

Every valid GPS packet produces a CSV row with the following columns:

| Column | Description |
|---|---|
| `edge_timestamp` | Timestamp from the ESP32 (`millis()`) |
| `server_timestamp` | ISO timestamp when the server received the packet |
| `car_id` | Vehicle identifier (e.g., `CAR_001`) |
| `latitude` / `longitude` | GPS coordinates |
| `hdop` | Horizontal dilution of precision |
| `satellites` | Number of visible satellites |
| `adc` | Raw ADC reading from the current sensor |
| `gps_age` | Age of the GPS fix in milliseconds |
| `gps_valid` | Whether the GPS fix was valid |
| `horn` | `True` if the horn was active |
| `inside_geofence` | `True` if the vehicle was inside a silence zone |
| `zone` | Name of the nearest silence zone |
| `event_type` | `ENTER` / `EXIT` / `HONK` / `NORMAL` |
| `justified` | `True` / `False` / `None` (only set on HONK events) |
| `distance_to_zone` | Signed distance to nearest zone boundary (meters) |
| `packet_count` | Running packet counter |
| `message` | Human-readable event description |
| `raw_packet` | Original JSON payload |

### Raw Packets Log (`raw_packets.log`)

Every incoming MQTT packet (including those filtered by GPS quality) is saved with a timestamp:

```
2026-07-17T23:13:47.726400 | {"timestamp":318958,"car_id":"CAR_001","lat":22.32335007,...}
```

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.12 or higher |
| **uv** | Python package manager ([install](https://docs.astral.sh/uv/)) |
| **Mosquitto** | MQTT broker ([install](https://mosquitto.org/download/)) |
| **Arduino IDE** | For flashing ESP32 firmware |
| **ESP32 Board** | With WiFi capability |
| **NEO-6M GPS** | Connected via UART2 |
| **ACS712** | Connected to GPIO 34 |
| **Phone/Camera** | Running DroidCam or similar IP camera app |

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Honk.git
cd Honk
```

### 2. Install Python Dependencies

```bash
uv sync
```

### 3. Start the MQTT Broker

```bash
# Start Mosquitto (if not already running as a service)
mosquitto -d
```

### 4. Flash the ESP32

1. Open `Arduino_ide/ACS_NEO_ESP32.ino` in Arduino IDE
2. **Edit configuration** at the top of the sketch:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   const char* mqtt_ip = "YOUR_LAPTOP_IP";  // run: hostname -I | cut -d ' ' -f 1
   ```
3. Install required libraries: `WiFi`, `PubSubClient`, `TinyGPSPlus`, `ArduinoJson`
4. Select your ESP32 board and port, then upload

### 5. Configure Silence Zones

Edit the `SILENCE_ZONES` dictionary in `subscriber.py` with your actual zone coordinates:

```python
SILENCE_ZONES = {
    "Hospital Zone": [
        (lat1, lon1),
        (lat2, lon2),
        (lat3, lon3),
        (lat4, lon4)
    ]
}
```

> 💡 Use [Google Maps](https://www.google.com/maps) — right-click any point to copy its coordinates.

### 6. Start the Camera Stream

Open DroidCam on your phone and update `CAMERA_URL` in `subscriber.py`:

```python
CAMERA_URL = "http://<PHONE_IP>:4747/video"
```

### 7. Run the Subscriber

```bash
uv run subscriber.py
```

### 8. Debug / Monitor

```bash
# In a separate terminal — see raw MQTT packets
mosquitto_sub -h localhost -t "car/telemetry/horn"
```

---

## 📁 Project Structure

```
Honk/
├── Arduino_ide/
│   ├── ACS_NEO_ESP32.ino          # Main ESP32 firmware (GPS + Horn + MQTT)
│   ├── ACS_DeskCheck_MinVal.ino   # Calibration sketch for horn threshold
│   └── Mqtt_Gps_arduino.ino       # Earlier GPS-only prototype (reference)
│
├── subscriber.py                   # MQTT subscriber — geofence + events + YOLO
├── camera.py                       # Standalone YOLO camera test script
├── yolo11n.pt                      # YOLOv11 nano model weights
│
├── events_log.csv                  # Structured event log (auto-generated)
├── raw_packets.log                 # Raw MQTT packet dump (auto-generated)
│
├── pyproject.toml                  # Python dependencies (uv)
├── uv.lock                         # Locked dependency versions
├── .python-version                 # Python version pin
└── README.md                       # You are here
```

---

## ⚙ Configuration Reference

### ESP32 Firmware (`ACS_NEO_ESP32.ino`)

| Parameter | Default | Description |
|---|---|---|
| `ssid` | — | WiFi network name |
| `password` | — | WiFi password |
| `mqtt_ip` | — | IP address of the MQTT broker |
| `HDOP_THRESHOLD` | `6.0` | Max acceptable HDOP; fixes above this are skipped |
| `GPS_WINDOW_SIZE` | `5` | Ring buffer size for GPS centroid averaging |
| `HORN_THRESHOLD` | `2690` | ADC threshold for horn detection (calibrate per vehicle) |
| `publishInterval` | `1000` | Telemetry publish interval in milliseconds |
| `CAR_ID` | `"CAR_001"` | Unique vehicle identifier |

### Python Subscriber (`subscriber.py`)

| Parameter | Default | Description |
|---|---|---|
| `BROKER` | `"localhost"` | MQTT broker address |
| `PORT` | `1883` | MQTT broker port |
| `DEBOUNCE_COUNT` | `3` | Consecutive readings needed to flip geofence state |
| `MAX_HDOP` | `6.0` | Maximum acceptable HDOP for GPS quality |
| `MIN_SATELLITES` | `4` | Minimum satellites for a valid fix |
| `CAMERA_URL` | `"http://..."` | IP camera stream URL |
| `CONFIDENCE_THRESHOLD` | `0.5` | YOLO detection confidence threshold |
| `DETECTION_WINDOW` | `2.0` | Seconds — person seen within this window = justified |
| `TARGET_CLASSES` | `[0]` | YOLO class IDs to detect (0 = person) |

---

## 📟 Sample Output

### Console Output (State Transitions & Honk Events)

```
Connected to MQTT Broker
Waiting for telemetry...

Camera connected.

============================================================
{
    "car_id": "CAR_001",
    "edge_timestamp": 425103,
    "server_timestamp": "2026-07-17T23:15:32.481920",
    "latitude": 22.323741,
    "longitude": 73.135891,
    "horn": false,
    "inside_geofence": true,
    "zone": "Testing Zone",
    "event_type": "ENTER",
    "justified": null,
    "distance_to_zone": -3.72,
    "packet_count": 127,
    "message": "Vehicle entered Testing Zone."
}
============================================================

============================================================
{
    "car_id": "CAR_001",
    "edge_timestamp": 431209,
    "server_timestamp": "2026-07-17T23:15:38.592103",
    "latitude": 22.323762,
    "longitude": 73.135842,
    "horn": true,
    "inside_geofence": true,
    "zone": "Testing Zone",
    "event_type": "HONK",
    "justified": false,
    "distance_to_zone": -8.15,
    "packet_count": 133,
    "message": "Honk unjustified inside Testing Zone."
}
============================================================
```

### CSV Row Example

```csv
edge_timestamp,server_timestamp,car_id,latitude,longitude,...,event_type,justified,...,message
425103,2026-07-17T23:15:32,CAR_001,22.323741,73.135891,...,HONK,False,...,"Honk unjustified inside Testing Zone."
```

---

## 🗺 Future Roadmap

- [ ] **Dedicated Dashboard** — Web-based real-time map visualization of vehicle positions and violation events
- [ ] **Multi-Vehicle Support** — Scale to track multiple vehicles simultaneously with unique `car_id` identifiers
- [ ] **Raspberry Pi Camera** — Replace phone camera with a dedicated Pi Camera module mounted on the dashboard
- [ ] **Extended YOLO Classes** — Detect vehicles, animals, and other obstacles beyond just pedestrians
- [ ] **Alert System** — Push notifications / SMS alerts to authorities when a violation occurs
- [ ] **Edge Inference** — Run YOLO directly on a Coral TPU / Jetson Nano inside the vehicle
- [ ] **Historical Analytics** — Pandas-based analysis of `events_log.csv` to identify repeat offenders and hotspots
- [ ] **OTA Firmware Updates** — Over-the-air updates for ESP32 firmware via MQTT commands
- [ ] **Horn Threshold Auto-Calibration** — Automatic calibration of the ADC threshold during an initial setup phase

---

<div align="center">

**Built with ⚡ ESP32 • 📡 MQTT • 🧠 YOLOv11 • 🐍 Python**

*Making silence zones actually silent.*

</div>
