"""
data_loader.py

Load data from a mock JSON file (for testing) or from a future database.
Provides a single entry function `load_data(config)` which returns a pandas DataFrame.

Config is a simple dict with keys:
- mode: 'mock' or 'db'
- mock_path: path to JSON file
- db_config: dict for DB connection (reserved for future)

The SkyLore data schema (mock JSON entries) should contain:
- id: string
- photo_url: string
- latitude: float
- longitude: float
- timestamp: ISO8601 string
- brightness_rating: int (1-5)
- constellation_name: string

Timestamps are parsed as timezone-aware UTC timestamps to avoid tz-naive vs tz-aware
comparison issues when filtering in the app.
"""
from typing import Dict
import pandas as pd
import json


def _parse_timestamp_utc(ts: str) -> pd.Timestamp:
    """Parse ISO8601 timestamp and return a tz-aware UTC pandas.Timestamp."""
    # Let pandas parse and then convert/localize to UTC
    ts_parsed = pd.to_datetime(ts)
    if ts_parsed.tzinfo is None:
        # treat naive timestamps as UTC
        ts_parsed = ts_parsed.tz_localize("UTC")
    else:
        ts_parsed = ts_parsed.tz_convert("UTC")
    return ts_parsed


def load_data(config: Dict) -> pd.DataFrame:
    """Load submissions into a DataFrame with SkyLore schema.

    Returns DataFrame with columns: id, photo_url, latitude, longitude, timestamp (UTC tz-aware),
    brightness_rating, constellation_name
    """
    mode = config.get("mode", "mock")

    if mode == "mock":
        path = config.get("mock_path", "mock_data.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = []
        for entry in data:
            records.append({
                "id": entry.get("id"),
                "photo_url": entry.get("photo_url"),
                "latitude": float(entry.get("latitude")),
                "longitude": float(entry.get("longitude")),
                "timestamp": _parse_timestamp_utc(entry.get("timestamp")),
                "brightness_rating": int(entry.get("brightness_rating")),
                "constellation_name": entry.get("constellation_name", ""),
            })

        df = pd.DataFrame.from_records(records)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    elif mode == "db":
        # Placeholder for future DB loading (e.g., Supabase/Postgres). Implement DB access here
        # and return a DataFrame with the same columns as above.
        raise NotImplementedError("Database mode not implemented yet. Use mock mode for testing.")

    else:
        raise ValueError(f"Unknown mode: {mode}")
