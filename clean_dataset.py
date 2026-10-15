
import pandas as pd
from pathlib import Path
import shutil

folder = Path(r"C:\Users\asus\Downloads\Drainage System (1)")

file_path = folder / "smart_sewer_live_predictions.csv"
backup_path = folder / "smart_sewer_live_predictions_before_sensor_dedup.csv"

# Read original data
df = pd.read_csv(file_path)

# Back up the original file
shutil.copy2(file_path, backup_path)

# Identify readings using sensor values only, excluding timestamp
sensor_columns = [
    "zone1",
    "zone2",
    "zone3",
    "flow",
    "rain",
    "gas_raw_adc",
]

original_rows = len(df)

# Keep the latest row for each unique sensor combination
df = df.drop_duplicates(
    subset=sensor_columns,
    keep="last"
)

removed_rows = original_rows - len(df)

# Update the original CSV
df.to_csv(file_path, index=False)

print("Original rows:", original_rows)
print("Duplicate sensor combinations removed:", removed_rows)
print("Rows remaining:", len(df))
print("Updated:", file_path)
print("Backup:", backup_path)
