
import csv
import hashlib
import json
import os
import time
from datetime import datetime

import joblib
import pandas as pd
import paho.mqtt.client as mqtt

# ============================================================
# 1. MQTT CONFIGURATION
# ============================================================

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "smartsewer/sensors"

# Keep live predictions separate from the training dataset
CSV_FILE = "smart_sewer_live_predictions.csv"
MODEL_FILE = "smart_sewer_models.pkl"

# Ignore identical sensor values received within this interval
DUPLICATE_WINDOW_SECONDS = 2

# ============================================================
# 2. LOAD TRAINED MODELS
# ============================================================

if not os.path.exists(MODEL_FILE):
    raise FileNotFoundError(
        f"Model file not found: {MODEL_FILE}. "
        "Run train_model.py first."
    )

bundle = joblib.load(MODEL_FILE)

features = bundle["features"]
models = bundle["models"]

required_models = {
    "blockage_label",
    "overflow_label",
    "gas_label",
}

if not required_models.issubset(models.keys()):
    raise ValueError(
        f"Expected models {required_models}, "
        f"but found {set(models.keys())}"
    )

print("Trained models loaded successfully.")
print("Required sensor fields:", features)

# ============================================================
# 3. CSV COLUMNS
# ============================================================

FIELDS = [
    "timestamp",
    "zone1",
    "zone2",
    "zone3",
    "flow",
    "rain",
    "gas_raw_adc",
    "predicted_blockage",
    "predicted_overflow",
    "predicted_gas",
    "blockage_confidence",
    "overflow_confidence",
    "gas_confidence",
]

# Duplicate tracking — one subscriber process
last_message_hash = None
last_message_time = 0.0

# ============================================================
# 4. CREATE CSV IF NEEDED
# ============================================================

def prepare_csv():
    if (
        not os.path.exists(CSV_FILE)
        or os.path.getsize(CSV_FILE) == 0
    ):
        with open(
            CSV_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=FIELDS
            )
            writer.writeheader()

        print("Created CSV:", CSV_FILE)
    else:
        print("Using existing CSV:", CSV_FILE)


# ============================================================
# 5. MQTT CONNECTION CALLBACK
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connection result:", reason_code)

    if reason_code == 0:
        client.subscribe(TOPIC)
        print("Subscribed to:", TOPIC)
        print("Waiting for sensor readings...")
    else:
        print("MQTT connection failed:", reason_code)


# ============================================================
# 6. PROCESS INCOMING SENSOR DATA
# ============================================================

def on_message(client, userdata, message):
    global last_message_hash, last_message_time

    try:
        # Decode MQTT JSON
        data = json.loads(
            message.payload.decode("utf-8")
        )

        # Validate required sensor fields
        missing = [
            field
            for field in features
            if field not in data or data[field] in (None, "")
        ]

        if missing:
            print("Missing sensor fields:", missing)
            print("Received message:", data)
            return

        # Convert sensor readings to numeric values
        sensor_values = {
            field: float(data[field])
            for field in features
        }

        # ----------------------------------------------------
        # DUPLICATE FILTER
        # ----------------------------------------------------

        
        # Ignore identical sensor readings received within 10 seconds
        
        # Check whether the sensor values have changed
        fingerprint = json.dumps(sensor_values, sort_keys=True)

        message_hash = hashlib.sha256(
            fingerprint.encode("utf-8")
        ).hexdigest()

        if message_hash == last_message_hash:
            print("Sensor readings unchanged. Waiting for new data...")
            return

        # Save the new fingerprint
        last_message_hash = message_hash
        last_message_time = time.time()



        # ----------------------------------------------------
        # PREPARE INPUT FOR THE ML MODELS
        # ----------------------------------------------------

        current_sensor = pd.DataFrame(
            [sensor_values],
            columns=features
        )

        # ----------------------------------------------------
        # RUN BLOCKAGE, OVERFLOW AND GAS PREDICTIONS
        # ----------------------------------------------------

        predictions = {}

        for target, model in models.items():
            prediction = model.predict(
                current_sensor
            )[0]

            probabilities = model.predict_proba(
                current_sensor
            )[0]

            predictions[target] = prediction

            predictions[target + "_confidence"] = round(
                float(max(probabilities)) * 100,
                2
            )

        # ----------------------------------------------------
        # PREPARE OUTPUT ROW
        # ----------------------------------------------------

        row = {
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            **sensor_values,
            "predicted_blockage": predictions[
                "blockage_label"
            ],
            "predicted_overflow": predictions[
                "overflow_label"
            ],
            "predicted_gas": predictions[
                "gas_label"
            ],
            "blockage_confidence": predictions[
                "blockage_label_confidence"
            ],
            "overflow_confidence": predictions[
                "overflow_label_confidence"
            ],
            "gas_confidence": predictions[
                "gas_label_confidence"
            ],
        }

        # ----------------------------------------------------
        # SAVE PREDICTIONS TO LIVE CSV
        # ----------------------------------------------------

        with open(
            CSV_FILE,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=FIELDS
            )
            writer.writerow(row)

        # ----------------------------------------------------
        # DISPLAY RESULTS
        # ----------------------------------------------------

        print("\n=== LIVE SENSOR ML PREDICTION ===")

        for field in features:
            print(
                f"{field}: {sensor_values[field]}"
            )

        print(
            "Predicted blockage:",
            row["predicted_blockage"]
        )
        print(
            "Blockage confidence:",
            row["blockage_confidence"],
            "%"
        )

        print(
            "Predicted overflow:",
            row["predicted_overflow"]
        )
        print(
            "Overflow confidence:",
            row["overflow_confidence"],
            "%"
        )

        print(
            "Predicted gas:",
            row["predicted_gas"]
        )
        print(
            "Gas confidence:",
            row["gas_confidence"],
            "%"
        )

        print("Saved to:", CSV_FILE)

    except (
        UnicodeDecodeError,
        json.JSONDecodeError
    ) as error:
        print("Invalid MQTT JSON:", error)

    except (
        KeyError,
        TypeError,
        ValueError
    ) as error:
        print("Invalid sensor data or model output:", error)

    except Exception as error:
        print("Prediction or CSV error:", error)


# ============================================================
# 7. START THE MQTT SUBSCRIBER
# ============================================================

prepare_csv()

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"SmartSewerML_{int(time.time())}",
)

client.on_connect = on_connect
client.on_message = on_message

client.reconnect_delay_set(
    min_delay=1,
    max_delay=30
)

print(f"\nConnecting to {BROKER}:{PORT} ...")
print("MQTT topic:", TOPIC)
print("Output file:", CSV_FILE)

try:
    client.connect(
        BROKER,
        PORT,
        keepalive=60
    )

    client.loop_forever()

except KeyboardInterrupt:
    print("\nSubscriber stopped by user.")

except Exception as error:
    print("MQTT connection error:", error)

finally:
    client.disconnect()
    print("MQTT subscriber disconnected.")
