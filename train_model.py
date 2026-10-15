
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score

# 1. Load the dataset
df = pd.read_csv("smart_sewer_dataset_v2.csv")

# 2. Select only raw sensor readings as inputs.
# Do not include risk scores or prediction labels as features.
features = [
    "zone1",
    "zone2",
    "zone3",
    "flow",
    "rain",
    "gas_raw_adc",
]

X = df[features]

# 3. Train a separate classifier for each target
targets = [
    "blockage_label",
    "overflow_label",
    "gas_label",
]

models = {}

for target in targets:
    print("\n" + "=" * 55)
    print("Training model for:", target)

    y = df[target]

    # Keep examples of each class in both sets
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=150,
        random_state=42,
        class_weight="balanced",
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    print("Test accuracy:", round(
        accuracy_score(y_test, predictions) * 100, 2
    ), "%")

    print("\nClassification report:")
    print(classification_report(
        y_test,
        predictions,
        zero_division=0,
    ))

    models[target] = model

# 4. Save models and their input-column order
bundle = {
    "features": features,
    "models": models,
}

joblib.dump(bundle, "smart_sewer_models.pkl")

print("\nTraining completed.")
print("Saved model: smart_sewer_models.pkl")
