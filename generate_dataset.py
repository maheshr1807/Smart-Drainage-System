
import csv
import random
from datetime import datetime, timedelta

random.seed(42)

FILE_NAME = "smart_sewer_dataset_v2.csv"
TOTAL_ROWS = 10000

columns = [
    "timestamp", "sample_id", "zone1", "zone2", "zone3",
    "flow", "rain", "gas_raw_adc", "blockageRisk",
    "overflowRisk", "blockage_label", "overflow_label",
    "gas_label", "worker_safety", "suspectedArea",
    "overallStatus", "scenario"
]

scenarios = [
    "NORMAL", "HEAVY_RAIN", "RISING_WATER",
    "PARTIAL_BLOCKAGE", "SEVERE_BLOCKAGE",
    "OVERFLOW_RISK", "GAS_HAZARD",
    "COMBINED_EMERGENCY"
]

start = datetime(2026, 1, 1)

with open(FILE_NAME, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(columns)

    for i in range(TOTAL_ROWS):
        scenario = random.choice(scenarios)

        # Default normal readings
        zone1 = random.uniform(10, 40)
        zone2 = random.uniform(10, 40)
        zone3 = random.uniform(10, 40)
        flow = random.uniform(2, 8)
        rain = random.uniform(0, 25)
        gas = random.randint(100, 900)
        blockage = random.randint(0, 20)
        overflow = random.randint(0, 20)

        if scenario == "HEAVY_RAIN":
            rain = random.uniform(65, 100)
            zone1, zone2, zone3 = [
                random.uniform(40, 80) for _ in range(3)
            ]
            overflow = random.randint(40, 80)

        elif scenario == "RISING_WATER":
            zone1 = random.uniform(55, 85)
            zone2 = random.uniform(60, 95)
            zone3 = random.uniform(50, 90)
            overflow = random.randint(45, 85)

        elif scenario == "PARTIAL_BLOCKAGE":
            zone1 = random.uniform(35, 70)
            zone2 = random.uniform(55, 90)
            zone3 = random.uniform(25, 65)
            flow = random.uniform(0.2, 3)
            blockage = random.randint(40, 70)

        elif scenario == "SEVERE_BLOCKAGE":
            zone1 = random.uniform(70, 98)
            zone2 = random.uniform(80, 100)
            zone3 = random.uniform(40, 85)
            flow = random.uniform(0, 1.5)
            blockage = random.randint(75, 100)
            overflow = random.randint(55, 95)

        elif scenario == "OVERFLOW_RISK":
            zone1, zone2, zone3 = [
                random.uniform(82, 100) for _ in range(3)
            ]
            rain = random.uniform(30, 100)
            overflow = random.randint(80, 100)

        elif scenario == "GAS_HAZARD":
            gas = random.randint(1800, 4095)

        elif scenario == "COMBINED_EMERGENCY":
            zone1, zone2, zone3 = [
                random.uniform(80, 100) for _ in range(3)
            ]
            rain = random.uniform(55, 100)
            gas = random.randint(2000, 4095)
            blockage = random.randint(70, 100)
            overflow = random.randint(80, 100)

        zone1 = round(zone1, 1)
        zone2 = round(zone2, 1)
        zone3 = round(zone3, 1)
        flow = round(flow, 2)
        rain = round(rain, 1)

        blockage = max(0, min(100, blockage))
        overflow = max(0, min(100, overflow))

        blockage_label = (
            "HIGH" if blockage >= 70
            else "MEDIUM" if blockage >= 40
            else "LOW"
        )

        overflow_label = (
            "HIGH" if overflow >= 80 or max(zone1, zone2, zone3) >= 90
            else "MEDIUM" if overflow >= 50 or max(zone1, zone2, zone3) >= 70
            else "LOW"
        )

        gas_label = "GAS DETECTED" if gas >= 1500 else "GAS SAFE"
        worker_safety = (
            "DO NOT ENTER"
            if gas_label == "GAS DETECTED"
            else "ASSESS OTHER HAZARDS"
        )

        overall = (
            "CRITICAL"
            if gas_label == "GAS DETECTED"
            or overflow_label == "HIGH"
            or blockage_label == "HIGH"
            else "WARNING"
            if overflow_label == "MEDIUM"
            or blockage_label == "MEDIUM"
            else "NORMAL"
        )

        differences = [
            abs(zone1 - zone2),
            abs(zone2 - zone3),
            abs(zone1 - zone3)
        ]
        suspected_area = [
            "BETWEEN Z1-Z2",
            "BETWEEN Z2-Z3",
            "BETWEEN Z1-Z3"
        ][differences.index(max(differences))]

        timestamp = (
            start + timedelta(seconds=i * 10)
        ).isoformat(timespec="seconds")

        writer.writerow([
            timestamp, f"SS-{i + 1:05d}",
            zone1, zone2, zone3, flow, rain, gas,
            blockage, overflow, blockage_label,
            overflow_label, gas_label, worker_safety,
            suspected_area, overall, scenario
        ])

print(f"Success! Created {TOTAL_ROWS} dataset rows.")
print(f"File: {FILE_NAME}")
