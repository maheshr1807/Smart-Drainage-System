
import pandas as pd
import joblib

bundle = joblib.load("smart_sewer_models.pkl")

# Example sensor readings; replace these with actual live readings later.
current_sensor = pd.DataFrame([{
    "zone1": 85.0,
    "zone2": 96.0,
    "zone3": 65.5,
    "flow": 0.50,
    "rain": 20.0,
    "gas_raw_adc": 800,
}])

# Ensure the input columns match the training order
current_sensor = current_sensor[bundle["features"]]

print("\n=== SMART SEWER ML PREDICTIONS ===")

for target, model in bundle["models"].items():
    prediction = model.predict(current_sensor)[0]
    probabilities = model.predict_proba(current_sensor)[0]
    confidence = max(probabilities) * 100

    print(f"{target}: {prediction}")
    print(f"Model confidence: {confidence:.1f}%")
    print("-" * 35)
