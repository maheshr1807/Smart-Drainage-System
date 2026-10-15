
import pandas as pd

file_name = "smart_sewer_dataset_v2.csv"

df = pd.read_csv(file_name)

print("\n===== DATASET INFORMATION =====")
print("Number of rows and columns:", df.shape)

print("\n===== COLUMN NAMES =====")
print(df.columns.tolist())

print("\n===== FIRST 5 ROWS =====")
print(df.head().to_string(index=False))

print("\n===== MISSING VALUES =====")
print(df.isnull().sum().to_string())

print("\n===== DATA TYPES =====")
print(df.dtypes.to_string())

print("\n===== LABEL COUNTS =====")
for column in [
    "blockage_label",
    "overflow_label",
    "gas_label",
    "scenario"
]:
    if column in df.columns:
        print(f"\n{column}:")
        print(df[column].value_counts(dropna=False).to_string())
