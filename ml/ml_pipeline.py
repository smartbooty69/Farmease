from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

BASE_NUMERIC_COLUMNS = [
    "temp_c",
    "humidity_pct",
    "soil_adc",
    "light_lux",
    "threshold_temp_on",
    "threshold_soil_dry",
    "threshold_light_lux",
]

BASE_BINARY_COLUMNS = [
    "flame_detected",
    "ir_detected",
    "relay_fan",
    "relay_pump",
    "relay_light",
    "relay_buzzer",
    "automation_on",
]


def load_dataset(csv_path: str | Path) -> pd.DataFrame:
    file_path = Path(csv_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset not found: {file_path}")

    data_frame = pd.read_csv(file_path)
    if data_frame.empty:
        raise ValueError("Dataset is empty. Collect more sensor data before training.")

    return data_frame


def _to_numeric(data_frame: pd.DataFrame, columns: Iterable[str]) -> None:
    for column_name in columns:
        if column_name in data_frame.columns:
            data_frame[column_name] = pd.to_numeric(data_frame[column_name], errors="coerce")


def prepare_dataframe(raw_data_frame: pd.DataFrame) -> pd.DataFrame:
    data_frame = raw_data_frame.copy()

    if "timestamp" not in data_frame.columns:
        raise ValueError("Dataset must include a 'timestamp' column.")

    data_frame["timestamp"] = pd.to_datetime(data_frame["timestamp"], errors="coerce")
    data_frame = data_frame.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    _to_numeric(data_frame, BASE_NUMERIC_COLUMNS)
    _to_numeric(data_frame, BASE_BINARY_COLUMNS)

    for column_name in BASE_BINARY_COLUMNS:
        if column_name in data_frame.columns:
            data_frame[column_name] = data_frame[column_name].clip(lower=0, upper=1)

    for column_name in BASE_NUMERIC_COLUMNS:
        if column_name in data_frame.columns:
            data_frame[column_name] = data_frame[column_name].replace([np.inf, -np.inf], np.nan)

    data_frame = data_frame.drop_duplicates(subset=["timestamp"], keep="last")
    data_frame = data_frame.reset_index(drop=True)

    return data_frame


def build_feature_frame(data_frame: pd.DataFrame) -> pd.DataFrame:
    engineered_frame = data_frame.copy()

    if "timestamp" not in engineered_frame.columns:
        raise ValueError("Expected 'timestamp' column for feature engineering.")

    second_of_day = (
        engineered_frame["timestamp"].dt.hour * 3600
        + engineered_frame["timestamp"].dt.minute * 60
        + engineered_frame["timestamp"].dt.second
    )
    engineered_frame["time_sin"] = np.sin(2 * np.pi * second_of_day / 86400.0)
    engineered_frame["time_cos"] = np.cos(2 * np.pi * second_of_day / 86400.0)

    signal_columns = [
        "temp_c",
        "humidity_pct",
        "soil_adc",
        "light_lux",
        "relay_light",
        "automation_on",
    ]

    for signal_name in signal_columns:
        if signal_name not in engineered_frame.columns:
            continue

        for lag_value in (1, 2, 3, 5):
            engineered_frame[f"{signal_name}_lag_{lag_value}"] = engineered_frame[signal_name].shift(lag_value)

        engineered_frame[f"{signal_name}_delta_1"] = engineered_frame[signal_name].diff(1)

    if "light_lux" in engineered_frame.columns:
        for rolling_window in (3, 5, 10):
            rolling_stats = engineered_frame["light_lux"].rolling(window=rolling_window)
            engineered_frame[f"light_roll_mean_{rolling_window}"] = rolling_stats.mean()
            engineered_frame[f"light_roll_std_{rolling_window}"] = rolling_stats.std()

        if "threshold_light_lux" in engineered_frame.columns:
            engineered_frame["light_margin"] = (
                engineered_frame["light_lux"] - engineered_frame["threshold_light_lux"]
            )

    if "temp_c" in engineered_frame.columns and "threshold_temp_on" in engineered_frame.columns:
        engineered_frame["temp_margin"] = engineered_frame["temp_c"] - engineered_frame["threshold_temp_on"]

    if "soil_adc" in engineered_frame.columns and "threshold_soil_dry" in engineered_frame.columns:
        engineered_frame["soil_margin"] = engineered_frame["soil_adc"] - engineered_frame["threshold_soil_dry"]

    return engineered_frame


def make_supervised_data(
    feature_frame: pd.DataFrame,
    horizon_steps: int = 1,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    if horizon_steps < 1:
        raise ValueError("horizon_steps must be >= 1")

    if "light_lux" not in feature_frame.columns or "relay_light" not in feature_frame.columns:
        raise ValueError("Dataset requires 'light_lux' and 'relay_light' columns for targets.")

    target_light = feature_frame["light_lux"].shift(-horizon_steps)
    target_relay = feature_frame["relay_light"].shift(-horizon_steps)

    target_mask = target_light.notna() & target_relay.notna()

    drop_columns = ["timestamp"]
    supervised_features = feature_frame.loc[target_mask].drop(columns=drop_columns, errors="ignore")
    target_light = target_light.loc[target_mask]
    target_relay = target_relay.loc[target_mask]

    return supervised_features, target_light, target_relay


def latest_feature_row(feature_frame: pd.DataFrame) -> pd.DataFrame:
    if feature_frame.empty:
        raise ValueError("No feature rows available.")

    latest_row = feature_frame.tail(1).drop(columns=["timestamp"], errors="ignore")
    return latest_row
