# HackTX2025-backend-citizenscientist
# Light Pollution Explorer
A lightweight Streamlit app to visualize citizen-science light pollution submissions.

Features
- Load mock submissions from JSON for testing
- Geospatial heatmap and scatter map (Plotly + Mapbox/OpenStreetMap)
- Time-series of average ratings
- Filters by date, rating, and tags

Files
- `app.py` - main Streamlit app
- `data_loader.py` - loads data from `mock_data.json` (or DB in future)
- `visualizations.py` - Plotly plotting helpers
- `mock_data.json` - example mock submissions
- `requirements.txt` - Python dependencies

Running locally
1. Create a virtualenv and install dependencies (PowerShell):

```powershell
python -m venv .venv; .\\.venv\\Scripts\\Activate.ps1; pip install -r requirements.txt
```

2. Run the app:

```powershell
streamlit run app.py
```

Notes
- The app uses the mock JSON by default. To switch to a real DB, implement DB loading in `data_loader.py` (the function signature is `load_data(config)`), and change `DEFAULT_CONFIG` in `app.py` to `{'mode': 'db', 'db_config': {...}}`.
- Mapbox token is optional; the app defaults to OpenStreetMap tiles. If you want higher-quality tiles, set a Mapbox token and pass it to plotting functions.

Contact
- This repo is a prototype for quick testing and demo. Improvements and contributions welcome.


