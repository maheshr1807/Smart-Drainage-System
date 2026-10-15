
import json
import csv
import os
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# MQTT broker used by your ESP32
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "smartsewer/sensors"

CSV_FILE = "smart_sewer_dataset_v2.csv"

FIELDS = [
    "timestamp",
    "zone1",
    "zone2",
    "zone3",
    "flow",
    "rain",
    "gas_raw_adc",
    "gas_label",
    "worker_safety",
    "blockageRisk",
    "suspectedArea",
    "overflowRisk",
    "overallStatus",
]


def prepare_csv():
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()


def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connection result:", reason_code)
    if reason_code == 0:
        client.subscribe(TOPIC)
        print("Subscribed to:", TOPIC)
    else:
        print("Connection failed.")


def on_message(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)

        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            **{field: data.get(field, "") for field in FIELDS if field != "timestamp"},
        }

        with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writerow(row)

        print("Saved:", row)

    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print("Invalid JSON message:", error)
    except (OSError, csv.Error) as error:
        print("CSV save error:", error)


prepare_csv()

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"SmartSewerPython_{int(time.time())}",
)
client.on_connect = on_connect
client.on_message = on_message
client.reconnect_delay_set(min_delay=1, max_delay=30)

print(f"Connecting to {BROKER}:{PORT} ...")
print("Waiting for messages on:", TOPIC)

client.connect(BROKER, PORT, keepalive=60)
client.loop_forever()
