from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

try:
    from .ml_pipeline import (
        build_feature_frame,
        latest_feature_row,
        load_dataset,
        prepare_dataframe,
    )
except ImportError:
    from ml_pipeline import (
        build_feature_frame,
        latest_feature_row,
        load_dataset,
        prepare_dataframe,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict next greenhouse light and relay state."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data") / "greenhouse_training_data.csv",
        help="Path to logged dataset used for the latest row.",
    )
    parser.add_argument(
        "--models",
        type=Path,
        default=Path("models"),
        help="Directory containing trained model artifacts.",
    )
    return parser.parse_args()


def align_columns(
    input_frame: pd.DataFrame, expected_columns: list[str]
) -> pd.DataFrame:
    aligned = input_frame.copy()
    for column_name in expected_columns:
        if column_name not in aligned.columns:
            aligned[column_name] = pd.NA

    return aligned[expected_columns]


def main() -> None:
    args = parse_args()

    feature_columns_path = args.models / "feature_columns.json"
    regression_model_path = args.models / "light_forecast_model.joblib"
    classification_model_path = args.models / "relay_light_model.joblib"

    if not feature_columns_path.exists() or not regression_model_path.exists():
        raise FileNotFoundError("Model artifacts missing. Run train_models.py first.")

    with feature_columns_path.open("r", encoding="utf-8") as feature_file:
        expected_columns = json.load(feature_file)

    reg_model = joblib.load(regression_model_path)
    cls_model = (
        joblib.load(classification_model_path)
        if classification_model_path.exists()
        else None
    )

    raw_frame = load_dataset(args.data)
    clean_frame = prepare_dataframe(raw_frame)
    feature_frame = build_feature_frame(clean_frame)
    latest_features = latest_feature_row(feature_frame)
    latest_features = align_columns(latest_features, expected_columns)

    next_light_lux = float(reg_model.predict(latest_features)[0])
    result = {"predicted_light_lux": round(next_light_lux, 3)}

    if cls_model is not None:
        predicted_relay = int(cls_model.predict(latest_features)[0])
        result["predicted_relay_light"] = predicted_relay

        try:
            probability = float(cls_model.predict_proba(latest_features)[0][1])
            result["predicted_relay_light_probability_on"] = round(probability, 4)
        except Exception:
            pass

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
