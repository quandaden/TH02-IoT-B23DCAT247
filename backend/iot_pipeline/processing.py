from __future__ import annotations

import numpy as np
import pandas as pd


SENSOR_COLUMNS = ("temperature", "humidity", "distance_cm")


def iqr_outlier_mask(series: pd.Series) -> pd.Series:
    values = series.dropna()
    result = pd.Series(False, index=series.index, dtype=bool)
    if len(values) < 4:
        return result

    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1
    if not np.isfinite(iqr) or iqr == 0:
        return result

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return ((series < lower) | (series > upper)).fillna(False)


def _normalize(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if not np.isfinite(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _process_device(
    frame: pd.DataFrame, frequency: str, rolling_window: int
) -> pd.DataFrame:
    device_id = str(frame["device_id"].iloc[0])
    ordered = frame.copy()
    ordered["_time"] = pd.to_datetime(ordered["_time"], utc=True)
    ordered = ordered.sort_values("_time").drop_duplicates(
        subset=["_time", "sequence"], keep="last"
    )
    ordered = ordered.set_index("_time")

    aggregations: dict[str, str] = {
        column: "mean" for column in SENSOR_COLUMNS if column in ordered.columns
    }
    for column, operation in {
        "rssi": "mean",
        "latency_ms": "mean",
        "sequence": "max",
        "uptime_s": "max",
        "gap_count": "sum",
    }.items():
        if column in ordered.columns:
            aggregations[column] = operation

    sampled = ordered.resample(frequency).agg(aggregations)
    sampled["device_id"] = device_id
    sampled["is_outlier"] = False

    for column in SENSOR_COLUMNS:
        if column not in sampled.columns:
            continue
        raw = sampled[column].astype(float)
        filled = raw.interpolate(method="time", limit=2, limit_direction="both")
        outlier = iqr_outlier_mask(filled)
        clean = filled.mask(outlier).interpolate(
            method="time", limit_direction="both"
        )

        sampled[f"{column}_raw"] = raw
        sampled[f"{column}_missing"] = raw.isna()
        sampled[f"{column}_outlier"] = outlier
        sampled[f"{column}_clean"] = clean
        sampled[f"{column}_rolling_mean"] = clean.rolling(
            window=rolling_window, min_periods=1
        ).mean()
        sampled[f"{column}_delta"] = clean.diff().fillna(0.0)
        sampled[f"{column}_normalized"] = _normalize(clean)
        sampled["is_outlier"] = sampled["is_outlier"] | outlier
        sampled = sampled.drop(columns=[column])

    return sampled.reset_index()


def preprocess_frame(
    frame: pd.DataFrame, frequency: str = "10s", rolling_window: int = 3
) -> pd.DataFrame:
    required = {"_time", "device_id", "sequence", *SENSOR_COLUMNS}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Raw data is missing columns: {sorted(missing)}")
    if frame.empty:
        return frame.copy()

    processed = [
        _process_device(group, frequency, rolling_window)
        for _, group in frame.groupby("device_id", sort=True)
    ]
    return pd.concat(processed, ignore_index=True).sort_values(
        ["device_id", "_time"]
    )

