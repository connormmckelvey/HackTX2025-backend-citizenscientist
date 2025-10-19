"""
Streamlit app to visualize light pollution submissions.

Run with:
    streamlit run app.py

Features:
- Load data from mock JSON (configurable)
- Simple sidebar filters: date range, rating, tags
- Map visualizations and time-series
"""
from typing import List, Optional
import streamlit as st
import pandas as pd

from data_loader import load_data
from visualizations import scatter_map, heatmap_map, time_series


DEFAULT_CONFIG = {
    "mode": "mock",
    "mock_path": "mock_data.json",
}


st.set_page_config(layout="wide", page_title="SkyLore - Brighten Our Stars, Discover the Stories Above")

# Create columns for title and logo
col1, col2 = st.columns([4, 1])

with col1:
    # Title and subtitle with custom styling
    st.markdown("""
        <div style="padding: 20px 0; display: flex; flex-direction: column; justify-content: center; height: 100%;">
            <h1 style="font-size: 2.5rem; margin: 0; padding: 0; line-height: 1.2; text-align: left;">Brighten Our Stars, Discover the Stories Above</h1>
            <p style="font-size: 1rem; color: #E6E2D3; margin: 8px 0 0 0; padding: 0; text-align: left; opacity: 0.9;">SkyLoreUsing your citizen science data to help us understand light pollution trends</p>
        </div>
    """, unsafe_allow_html=True)

with col2:
    # Logo positioned properly in column
    st.markdown("""
        <div style="padding: 0px 0; display: flex; justify-content: center; align-items: center;">
    """, unsafe_allow_html=True)
    st.image("logo.png", width=120)
    st.markdown("</div>", unsafe_allow_html=True)

# Config
# Sidebar: allow toggling mock data vs DB (DB not implemented yet)
use_mock = st.sidebar.checkbox("Use mock data", value=True)
config = DEFAULT_CONFIG.copy()
config["mode"] = "mock" if use_mock else "db"

# Load data
with st.spinner("Loading data..."):
    df = load_data(config)

# Sidebar filters
st.sidebar.header("Filters")
# Minimum brightness slider
min_brightness = st.sidebar.slider("Minimum brightness rating", min_value=1, max_value=5, value=1)

# Constellation text filter
const_filter = st.sidebar.text_input("Filter by constellation (substring, case-insensitive)")

# Date range
if not df.empty:
    min_date = df["timestamp"].min().date()
    max_date = df["timestamp"].max().date()
else:
    min_date = None
    max_date = None

date_range = st.sidebar.date_input("Date range", value=(min_date, max_date))

st.sidebar.markdown("---")
mean_lat = float(df["latitude"].mean()) if not df.empty else 0.0
mean_lon = float(df["longitude"].mean()) if not df.empty else 0.0

center_lat = st.sidebar.number_input("Center latitude", value=mean_lat, format="%.6f")
center_lon = st.sidebar.number_input("Center longitude", value=mean_lon, format="%.6f")
# Switch radius to miles
radius_mi = st.sidebar.slider("Radius (miles)", min_value=1, max_value=1000, value=500)
radius_km = radius_mi * 1.60934

# Apply filters
filtered = df.copy()
if date_range and len(date_range) == 2 and date_range[0] is not None and date_range[1] is not None:
    # Create start/end as Timestamps (date_input returns date objects)
    start = pd.to_datetime(pd.Timestamp(date_range[0]))
    end = pd.to_datetime(pd.Timestamp(date_range[1])) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    # If the DataFrame timestamps are timezone-aware, localize the start/end timestamps
    # created from the date_input to the same timezone. This prevents comparing tz-naive
    # and tz-aware datetimes which raises a TypeError in pandas.
    tz = None
    if not filtered.empty:
        try:
            tz = getattr(filtered["timestamp"].dt, "tz", None)
        except Exception:
            tz = None

    if tz is not None:
        # tz may be a tzinfo-like object; pandas accepts it for tz_localize
        if start.tzinfo is None:
            try:
                start = pd.Timestamp(start).tz_localize(tz)
            except Exception:
                # fallback to explicit UTC localization if tz_localize fails
                start = pd.Timestamp(start).tz_localize("UTC")
        else:
            start = pd.Timestamp(start).tz_convert(tz)

        if end.tzinfo is None:
            try:
                end = pd.Timestamp(end).tz_localize(tz)
            except Exception:
                end = pd.Timestamp(end).tz_localize("UTC")
        else:
            end = pd.Timestamp(end).tz_convert(tz)

    filtered = filtered[(filtered["timestamp"] >= start) & (filtered["timestamp"] <= end)]

# Apply minimum brightness filter
filtered = filtered[filtered["brightness_rating"] >= min_brightness]

# Constellation filter (case-insensitive substring match)
if const_filter:
    filtered = filtered[filtered["constellation_name"].str.contains(const_filter, case=False, na=False)]

# Area filtering helper: haversine distance
def haversine_km(lat1, lon1, lat2, lon2):
    import numpy as np
    R = 6371.0
    lat1r = np.radians(lat1)
    lon1r = np.radians(lon1)
    lat2r = np.radians(lat2)
    lon2r = np.radians(lon2)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat/2.0)**2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

area_filtered = filtered.copy()
if not filtered.empty:
    import numpy as np
    dists = haversine_km(center_lat, center_lon, filtered["latitude"].to_numpy(), filtered["longitude"].to_numpy())
    area_filtered = filtered.iloc[np.where(dists <= radius_km)[0]]
else:
    area_filtered = filtered.copy()

st.sidebar.write(f"Submissions in selected area: {len(area_filtered)}")

st.sidebar.write(f"Total submissions: {len(filtered)}")

# Main layout
col1, col2 = st.columns([2,1])

with col1:
    tab1, tab2 = st.tabs(["Scatter Map", "Heat Map"])
    
    with tab1:
        st.subheader("Submissions Scatter Map")
        scat_fig = scatter_map(filtered, center_lat=center_lat, center_lon=center_lon, radius_km=radius_km)
        st.plotly_chart(scat_fig, use_container_width=True, config={'displayModeBar': True})
    
    with tab2:
        st.subheader("Geospatial Heatmap")
        heat_fig = heatmap_map(filtered, center_lat=center_lat, center_lon=center_lon, radius_km=radius_km)
        st.plotly_chart(heat_fig, use_container_width=True, config={'displayModeBar': True})

with col2:
    tab_trends, tab_info = st.tabs(["Trends", "Info"])

    with tab_trends:
        st.subheader("Time Series (Area Only)")
        freq = st.selectbox("Aggregation", options=["D","W","M"], index=0, format_func=lambda x: {"D":"Daily","W":"Weekly","M":"Monthly"}[x])
        ts_fig = time_series(area_filtered, freq=freq)
        st.plotly_chart(ts_fig, use_container_width=True)

    with tab_info:
        st.subheader("Area Info")
        st.markdown(f"**Radius:** {radius_mi} miles  ")
        st.markdown(f"**Total submissions (after filters):** {len(filtered)}  ")
        st.markdown(f"**Submissions in selected area:** {len(area_filtered)}  ")
        st.markdown("---")
        if area_filtered.empty:
            st.info("No submissions found in the selected area.")
        else:
            for idx, row in area_filtered.iterrows():
                cols = st.columns([1,3])
                with cols[0]:
                    if row.get("photo_url"):
                        st.image(row["photo_url"], width=120)
                with cols[1]:
                    st.markdown(f"**ID:** {row['id']}  ")
                    st.markdown(f"**Constellation:** {row['constellation_name']}  ")
                    st.markdown(f"**Brightness:** {row['brightness_rating']}  ")
                    st.markdown(f"**Timestamp:** {row['timestamp']}  ")
                    st.markdown(f"**Location:** {row['latitude']}, {row['longitude']}  ")
            st.markdown("---")
        st.markdown("Tips:\n- Use the map tabs to switch between scatter and heatmap views.\n- Adjust the area selection to focus on a region.\n- If you switch to DB mode, implement loading in `data_loader.py`.")

st.markdown("---")
st.markdown("Built for testing with mock JSON. Switch to DB mode by editing `DEFAULT_CONFIG` in `app.py` and implementing DB loading in `data_loader.py`.")
st.markdown("© 2024 SkyLore Project")