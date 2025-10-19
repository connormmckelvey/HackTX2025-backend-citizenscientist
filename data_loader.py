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
- constellation_name: string (legacy single constellation)
- constellation_names: list of strings (new multiple constellations format)

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
    brightness_rating, constellation_name, constellation_names
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
                "constellation_names": entry.get("constellation_names", []),
            })

        df = pd.DataFrame.from_records(records)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    elif mode == "db":
        # Load from Supabase database
        try:
            import os
            from supabase import create_client, Client

            # Get Supabase credentials from environment variables
            url = 'https://ldwfbxlhovfjzklkylfg.supabase.co'
            key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxkd2ZieGxob3ZmanprbGt5bGZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA4MTA2NDAsImV4cCI6MjA3NjM4NjY0MH0.vPj2qJYpz8IplrPWLbrXcZljIcsAk6e1eUBjcwQgLgI'

            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables required")

            supabase: Client = create_client(url, key)

            # Fetch all submissions from Supabase
            response = supabase.table('photos').select('*').execute()
            data = response.data

            if not data:
                # Return empty DataFrame with correct structure if no data
                return pd.DataFrame(columns=["id", "photo_url", "latitude", "longitude", "timestamp", "brightness_rating", "constellation_name", "constellation_names"])

            records = []
            for entry in data:
                records.append({
                    "id": entry.get("id"),
                    "photo_url": entry.get("photo_url"),
                    "latitude": float(entry.get("lat")),
                    "longitude": float(entry.get("long")),
                    "timestamp": _parse_timestamp_utc(entry.get("created_at")),
                    "brightness_rating": int(entry.get("brightness_level")),
                    "constellation_name": "",  # Not available in Supabase schema
                    "constellation_names": [],  # Not available in Supabase schema
                })

            df = pd.DataFrame.from_records(records)
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df

        except ImportError:
            raise ImportError("Supabase client not installed. Install with: pip install supabase")
        except Exception as e:
            raise RuntimeError(f"Failed to load from Supabase: {str(e)}")

    else:
        raise ValueError(f"Unknown mode: {mode}")
