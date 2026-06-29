import json
import csv
import os
from datetime import datetime
import paho.mqtt.client as mqtt

# MQTT CONFIGURATION

BROKER = "localhost"
PORT = 1883
TOPIC = "car/telemetry/horn"

# FILES

CSV_FILE = "events_log.csv"
RAW_PACKET_LOG = "raw_packets.log"

# GEOFENCE (Polygon Vertices)
# Replace these coordinates with your actual ones

SILENCE_ZONES = {
    "Hospital Zone": [
        (22.323400, 73.136500),
        (22.323600, 73.136500),
        (22.323600, 73.136800),
        (22.323400, 73.136800)
    ]
}

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
            "horn",
            "inside_geofence",
            "zone",
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

        horn = bool(data.get("horn", False))

        car_id = data.get("car_id", "CAR_001")

        edge_timestamp = data.get(
            "timestamp",
            "Not Available"
        )

        server_timestamp = datetime.now().isoformat()

        inside, zone = check_geofence(lat, lon)

        # Notification Logic

        if inside:

            if horn:

                message = (
                    f"Vehicle honked inside {zone}."
                )

            else:

                message = (
                    f"Vehicle entered {zone}."
                )

        else:

            message = "Vehicle outside silence zone."

        notification = {

            "car_id": car_id,

            "edge_timestamp": edge_timestamp,

            "server_timestamp": server_timestamp,

            "latitude": round(lat, 6),

            "longitude": round(lon, 6),

            "horn": horn,

            "inside_geofence": inside,

            "zone": zone,

            "message": message

        }

        print("\n" + "=" * 60)

        print(json.dumps(notification, indent=4))

        print("=" * 60)

        # Save to CSV

        with open(CSV_FILE, "a", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([

                edge_timestamp,

                server_timestamp,

                car_id,

                lat,

                lon,

                horn,

                inside,

                zone,

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