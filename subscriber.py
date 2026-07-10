import json
import csv
import os
import math
from datetime import datetime
import paho.mqtt.client as mqtt

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
packet_count = 0

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

        global last_zone, last_horn, packet_count
        packet_count += 1

        previous_state = last_known_state
        state = update_debounced_state(inside)

        if state == "inside" and zone is not None:
            last_zone = zone

        if state == "inside":

            if horn:
                message = f"Vehicle honked inside {last_zone}."
            else:
                message = f"Vehicle entered {last_zone}."

            is_inside = True

        else:

            if previous_state == "inside":
                message = f"Vehicle exited {last_zone}."
            else:
                message = "Vehicle outside silence zone."

            is_inside = False

        state_changed = previous_state != state
        horn_activated = horn and not last_horn
        last_horn = horn

        # Event type
        if horn and is_inside:
            event_type = "HONK"
        elif state == "inside" and previous_state != "inside":
            event_type = "ENTER"
        elif state != "inside" and previous_state == "inside":
            event_type = "EXIT"
        else:
            event_type = "NORMAL"

        # Distance to nearest zone boundary (negative = inside)
        nearest_zone_name = None
        nearest_dist = float("inf")
        for zname, polygon in SILENCE_ZONES.items():
            dist = point_to_polygon_distance(lat, lon, polygon)
            if abs(dist) < abs(nearest_dist):
                nearest_dist = dist
                nearest_zone_name = zname

        distance_to_zone = round(nearest_dist, 2)

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

            "distance_to_zone": distance_to_zone,

            "packet_count": packet_count,

            "message": message

        }

        if state_changed or horn_activated:
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

                distance_to_zone,

                packet_count,

                message,

                payload

            ])

    except Exception as e:

        print(e)


# MAIN

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

print("Waiting for telemetry...\n")

client.loop_forever()
