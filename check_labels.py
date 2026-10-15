
import pandas as pd

df = pd.read_csv("smart_sewer_dataset_v2.csv")

print("\n=== BLOCKAGE LABEL CHECK ===")
print(
    df.groupby("blockage_label")["blockageRisk"]
      .agg(["count", "min", "mean", "max"])
      .round(2)
)

print("\n=== OVERFLOW LABEL CHECK ===")
print(
    df.groupby("overflow_label")["overflowRisk"]
      .agg(["count", "min", "mean", "max"])
      .round(2)
)

print("\n=== GAS LABEL CHECK ===")
print(
    df.groupby("gas_label")["gas_raw_adc"]
      .agg(["count", "min", "mean", "max"])
      .round(2)
)

print("\n=== OVERALL STATUS COUNTS ===")
print(df["overallStatus"].value_counts())

print("\n=== SCENARIO VS OVERALL STATUS ===")
print(pd.crosstab(df["scenario"], df["overallStatus"]))
