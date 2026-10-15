
import csv
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

PROJECT = Path(__file__).resolve().parent
CSV_FILE = PROJECT / "smart_sewer_dataset_v2.csv"

COLUMNS = [
    "timestamp", "sample_id",
    "zone1", "zone2", "zone3",
    "flow", "rain", "gas_raw_adc",
    "blockage_label", "overflow_label", "gas_label"
]

parser = argparse.ArgumentParser()
parser.add_argument("--rows", type=int, default=1000,
                    help="Number of new readings to capture")
parser.add_argument("--scenario", default="unspecified",
                    help="Scenario name, e.g. high_water")
args = parser.parse_args()

if args.rows < 1:
    raise SystemExit("--rows must be greater than zero")

new_file = not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0
next_id = 1

if not new_file:
    with CSV_FILE.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS + ["scenario"]:
            raise SystemExit(
                "CSV header does not match this script. "
                "Back up the file or choose a new CSV filename."
            )
        for row in reader:
            try:
                next_id = max(next_id, int(row["sample_id"]) + 1)
            except (ValueError, TypeError):
                pass

columns_with_scenario = COLUMNS + ["scenario"]

command = ["wokwi-cli", str(PROJECT), "--timeout", "21600000"]

count = 0
print("Starting Wokwi CLI...")
print(f"Saving to: {CSV_FILE}")
print(f"Scenario: {args.scenario}")

try:
    with CSV_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if new_file:
            writer.writerow(columns_with_scenario)
            f.flush()

        process = subprocess.Popen(
            command,
            cwd=PROJECT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )

        try:
            for line in process.stdout:
                # CLI output may contain prefixes before the serial text.
                position = line.find("DATASET,")
                if position == -1:
                    continue

                parts = line[position:].strip().split(",")
                if len(parts) != 10:
                    continue

                try:
                    values = [float(x.strip()) for x in parts[1:]]
                except ValueError:
                    continue

                timestamp = datetime.now().astimezone().isoformat(
                    timespec="seconds"
                )

                writer.writerow([
                    timestamp, next_id + count, *values, args.scenario
                ])
                f.flush()
                count += 1

                if count % 25 == 0 or count == args.rows:
                    print(f"Captured {count}/{args.rows}")

                if count >= args.rows:
                    break

        except KeyboardInterrupt:
            print("\nCapture stopped. Saved rows are preserved.")

        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

except FileNotFoundError:
    raise SystemExit(
        "wokwi-cli not found. Check that Wokwi CLI is installed "
        "and available in PATH."
    )

print(f"Finished: added {count} new readings.")
print(f"CSV file: {CSV_FILE}")
