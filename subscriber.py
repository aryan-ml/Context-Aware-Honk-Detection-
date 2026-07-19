import json
import csv
import os
import math
import traceback
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt
from ultralytics import YOLO
import cv2

# MQTT CONFIGURATION

BROKER = "localhost"    
PORT = 1883
TOPIC = "car/telemetry/horn"

# FILES

CSV_FILE = "events_log.csv"
RAW_PACKET_LOG = "raw_packets.log"

# GEOFENCE DEBOUNCE

DEBOUNCE_COUNT = 3   # consecutive inside/outside readings to flip state
MAX_HDOP = 6.0
MIN_SATELLITES = 4

# CAMERA / YOLO

CAMERA_URL = "http://10.181.118.4:4747/video"
YOLO_MODEL = "yolo11n.pt"
TARGET_CLASSES = [0]          # person only
CONFIDENCE_THRESHOLD = 0.5
DETECTION_WINDOW = 2.0        # seconds — person seen within this window counts

# GEOFENCE (Polygon Vertices)
# Replace these coordinates with your actual ones

SILENCE_ZONES = {
    "Testing Zone": [
        (22.323735183458012, 73.13614802280819),
        (22.323661934390508, 73.1357714020674),
        (22.32381135064534,  73.135729903297),
        (22.323875035180556, 73.13609098373645)
    ]
}

# State

inside_history = []
last_known_state = None  # "inside", "outside", or None
last_zone = None
last_horn = False
last_justified = None
packet_count = 0
last_person_seen = 0.0
detection_lock = threading.Lock()

# Create CSV if it doesn't exist

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "edge_timestamp",
            "server_timestamp",
            "car_id",
            "latitude",
            "longitude",
            "hdop",
            "satellites",
            "adc",
            "gps_age",
            "gps_valid",
            "horn",
            "inside_geofence",
            "zone",
            "event_type",
            "justified",
            "distance_to_zone",
            "packet_count",
            "message",
            "raw_packet"
        ])

# Ray Casting Algorithm

def point_in_polygon(lat, lon, polygon):

    inside = False

    j = len(polygon) - 1

    for i in range(len(polygon)):

        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]

        intersect = (
            (lon_i > lon) != (lon_j > lon)
        ) and (
            lat <
            (lat_j - lat_i) * (lon - lon_i) /
            (lon_j - lon_i + 1e-12)
            + lat_i
        )

        if intersect:
            inside = not inside

        j = i

    return inside


def check_geofence(lat, lon):

    for zone_name, polygon in SILENCE_ZONES.items():

        if point_in_polygon(lat, lon, polygon):
            return True, zone_name

    return False, None


def point_to_polygon_distance(lat, lon, polygon):
    R = 6371000
    mid_lat = sum(p[0] for p in polygon) / len(polygon)
    lat_to_m = math.radians(1) * R
    lon_to_m = lat_to_m * math.cos(math.radians(mid_lat))

    inside = point_in_polygon(lat, lon, polygon)

    min_dist_sq = float("inf")
    n = len(polygon)
    for i in range(n):
        lat1, lon1 = polygon[i]
        lat2, lon2 = polygon[(i + 1) % n]

        x1, y1 = lon1 * lon_to_m, lat1 * lat_to_m
        x2, y2 = lon2 * lon_to_m, lat2 * lat_to_m
        px, py = lon * lon_to_m, lat * lat_to_m

        dx, dy = x2 - x1, y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq == 0:
            d_sq = (px - x1) * (px - x1) + (py - y1) * (py - y1)
        else:
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            d_sq = (px - proj_x) * (px - proj_x) + (py - proj_y) * (py - proj_y)

        min_dist_sq = min(min_dist_sq, d_sq)

    dist = math.sqrt(min_dist_sq)
    return -dist if inside else dist


def update_debounced_state(inside):
    global inside_history, last_known_state

    inside_history.append(inside)
    if len(inside_history) > DEBOUNCE_COUNT:
        inside_history.pop(0)

    if len(inside_history) < DEBOUNCE_COUNT:
        return last_known_state

    if all(inside_history):
        new_state = "inside"
    elif not any(inside_history):
        new_state = "outside"
    else:
        return last_known_state

    if new_state != last_known_state:
        last_known_state = new_state

    return last_known_state


# DETECTION LOOP

def detection_loop():
    global last_person_seen

    model = YOLO(YOLO_MODEL)

    while True:
        cap = cv2.VideoCapture(CAMERA_URL)
        if not cap.isOpened():
            print("Failed to connect to camera. Retrying in 1s...")
            time.sleep(1)
            continue

        print("Camera connected.")
        prev = time.time()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Failed to read frame. Reconnecting in 1s...")
                    time.sleep(1)
                    break

                curr = time.time()
                dt = curr - prev
                fps = 1.0 / dt if dt > 0 else 0.0
                prev = curr

                results = model(frame, verbose=False, classes=TARGET_CLASSES)
                for box in results[0].boxes:
                    if (
                        int(box.cls[0]) in TARGET_CLASSES
                        and float(box.conf[0]) >= CONFIDENCE_THRESHOLD
                    ):
                        with detection_lock:
                            last_person_seen = time.time()
                        break

                annotated = results[0].plot()
                cv2.putText(
                    annotated, f"FPS: {fps:.1f}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
                )
                cv2.imshow("Detection", annotated)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    return
        finally:
            cap.release()
            cv2.destroyAllWindows()


# MQTT CALLBACKS

def on_connect(client, userdata, flags, rc):

    if rc == 0:
        print("Connected to MQTT Broker")
        client.subscribe(TOPIC)
    else:
        print("Connection Failed:", rc)


def on_message(client, userdata, msg):

    try:

        payload = msg.payload.decode()

        # Save raw packet
        with open(RAW_PACKET_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {payload}\n")

        data = json.loads(payload)

        lat = data.get("lat")
        lon = data.get("lon")

        if lat is None or lon is None:
            print("Invalid GPS data")
            return

        hdop = data.get("hdop")
        satellites = data.get("satellites")
        adc = data.get("adc")
        gps_age = data.get("gps_age")
        gps_valid = data.get("gps_valid")

        # Reject bad GPS
        if gps_valid is not True:
            return
        if (hdop is not None and hdop > MAX_HDOP) or (satellites is not None and satellites < MIN_SATELLITES):
            return

        horn = bool(data.get("horn", False))

        car_id = data.get("car_id", "CAR_001")

        edge_timestamp = data.get(
            "timestamp",
            "Not Available"
        )

        server_timestamp = datetime.now().isoformat()

        inside, zone = check_geofence(lat, lon)

        global last_zone, last_horn, last_justified, packet_count, last_person_seen
        packet_count += 1

        previous_state = last_known_state
        state = update_debounced_state(inside)

        # Distance to nearest zone boundary (negative = inside)
        nearest_zone_name = None
        nearest_dist = float("inf")
        for zname, polygon in SILENCE_ZONES.items():
            dist = point_to_polygon_distance(lat, lon, polygon)
            if abs(dist) < abs(nearest_dist):
                nearest_dist = dist
                nearest_zone_name = zname

        distance_to_zone = round(nearest_dist, 2)

        # Event type
        if horn and inside:
            event_type = "HONK"
        elif state == "inside" and previous_state != "inside":
            event_type = "ENTER"
        elif state != "inside" and previous_state == "inside":
            event_type = "EXIT"
        else:
            event_type = "NORMAL"

        # Justification (only meaningful on HONK)
        if event_type == "HONK":
            with detection_lock:
                justified = (time.time() - last_person_seen) <= DETECTION_WINDOW
        else:
            justified = None

        # Track last zone for exit messages
        if state == "inside" and zone is not None:
            last_zone = zone

        if inside:

            if horn:
                if justified:
                    message = f"Honk justified inside {nearest_zone_name}."
                else:
                    message = f"Honk unjustified inside {nearest_zone_name}."
            else:
                if event_type == "ENTER":
                    message = f"Vehicle entered {nearest_zone_name}."
                else:
                    message = f"Vehicle inside {nearest_zone_name}."

            is_inside = True

        else:

            if previous_state == "inside":
                message = f"Vehicle exited {last_zone}."
            else:
                message = "Vehicle outside silence zone."

            is_inside = False

        state_changed = previous_state != state
        horn_activated = horn and not last_horn
        justification_changed = justified != last_justified
        last_horn = horn
        last_justified = justified

        notification = {

            "car_id": car_id,

            "edge_timestamp": edge_timestamp,

            "server_timestamp": server_timestamp,

            "latitude": round(lat, 6),

            "longitude": round(lon, 6),

            "hdop": hdop,

            "satellites": satellites,

            "horn": horn,

            "inside_geofence": is_inside,

            "zone": nearest_zone_name if nearest_zone_name else "None",

            "event_type": event_type,

            "justified": justified,

            "distance_to_zone": distance_to_zone,

            "packet_count": packet_count,

            "message": message

        }

        if state_changed or horn_activated or justification_changed:
            print("\n" + "=" * 60)
            print(json.dumps(notification, indent=4))
            print("=" * 60)

        with open(CSV_FILE, "a", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([

                edge_timestamp,

                server_timestamp,

                car_id,

                lat,

                lon,

                hdop,

                satellites,

                adc,

                gps_age,

                gps_valid,

                horn,

                is_inside,

                nearest_zone_name if nearest_zone_name else "None",

                event_type,

                justified,

                distance_to_zone,

                packet_count,

                message,

                payload

            ])

    except Exception:

        traceback.print_exc()


# MAIN

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

print("Waiting for telemetry...\n")

detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()

try:
    client.loop_forever()
except KeyboardInterrupt:
    pass
finally:
    client.disconnect()
