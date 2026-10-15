
import csv

filename = "smart_sewer_dataset_v2.csv"

with open(filename, "r", newline="", encoding="utf-8-sig") as f:
    reader = csv.reader(f)

    header = next(reader)
    print("Header field count:", len(header))
    print("Header:", header)

    for i, row in zip(range(5), reader):
        print(f"\nRow {i + 1} field count:", len(row))
        for column, value in zip(header, row):
            print(f"{column} = {value}")
