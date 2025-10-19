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
import json
import os
import tempfile
from urltoconstallation import setConstellation

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
            <p style="font-size: 1rem; color: #E6E2D3; margin: 8px 0 0 0; padding: 0; text-align: left; opacity: 0.9;">SkyLore is using your citizen science data to help us understand light pollution trends</p>
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
# Sidebar: allow toggling between data sources
st.sidebar.header("SkyLore")

# Data source selection
data_source = st.sidebar.radio(
    "Data Source",
    options=["Mock Data", "Supabase Database"],
    index=0,  # Default to mock data
    help="Choose data source for visualizations"
)

use_db = data_source == "Supabase Database"
config = DEFAULT_CONFIG.copy()
config["mode"] = "db" if use_db else "mock"

# Show current data source status
if use_db:
    st.sidebar.success("📊 Connected to Supabase Database")
else:
    st.sidebar.info("🧪 Using Mock Data (Testing Mode)")

# Load data
with st.spinner("Loading data..."):
    try:
        df = load_data(config)

        # Show data source info
        if use_db:
            st.sidebar.metric("Database Records", len(df) if not df.empty else 0)
        else:
            st.sidebar.metric("Mock Records", len(df) if not df.empty else 0)

    except ImportError as e:
        st.error(f"❌ Missing dependency: {e}")
        st.info("💡 To use database mode, install required packages: `pip install supabase`")
        st.stop()
    except ValueError as e:
        st.error(f"❌ Configuration error: {e}")
        st.info("💡 Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")
        st.stop()
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        st.info("💡 Check your database connection and try again")
        st.stop()

# Sidebar filters
st.sidebar.header("Filters")
# Minimum brightness slider
min_brightness = st.sidebar.slider("Minimum brightness rating", min_value=1, max_value=5, value=1)

# Constellation text filter (works with multiple constellations per entry)
const_filter = st.sidebar.text_input("Filter by constellation (substring, case-insensitive)")

# Date range
# Ensure timestamps are datetime and handle empty/invalid gracefully
if not df.empty and "timestamp" in df.columns:
    timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
else:
    timestamps = pd.Series([], dtype="datetime64[ns]")

if not timestamps.empty and timestamps.notna().any():
    min_date = timestamps.min().date()
    max_date = timestamps.max().date()
else:
    today = pd.Timestamp("today").date()
    min_date = today
    max_date = today

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

# Constellation filter (case-insensitive substring match) - handles both single and multiple constellations
if const_filter:
    def matches_constellation(row):
        # Handle both single constellation_name and constellation_names list
        if 'constellation_names' in row and isinstance(row['constellation_names'], list):
            # Multiple constellations - check if filter matches any of them
            return any(const_filter.lower() in str(const_name).lower() for const_name in row['constellation_names'] if const_name)
        elif 'constellation_name' in row and row['constellation_name']:
            # Single constellation - check if filter matches
            return const_filter.lower() in str(row['constellation_name']).lower()
        return False

    filtered = filtered[filtered.apply(matches_constellation, axis=1)]

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

st.sidebar.write(f"Sky photos in selected area: {len(area_filtered)}")

st.sidebar.write(f"Total sky photos: {len(filtered)}")

# Main layout
col1, col2 = st.columns([2,1])

with col1:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Scatter Map", "Heat Map", "Upload", "Cultural Constellations", "About SkyLore"])

    with tab1:
        st.subheader("Sky Photo Submissions Scatter Map")
        scat_fig = scatter_map(filtered, center_lat=center_lat, center_lon=center_lon, radius_km=radius_km)
        st.plotly_chart(scat_fig, use_container_width=True, config={'displayModeBar': True})

    with tab2:
        st.subheader("Geospatial Heatmap")
        heat_fig = heatmap_map(filtered, center_lat=center_lat, center_lon=center_lon, radius_km=radius_km)
        st.plotly_chart(heat_fig, use_container_width=True, config={'displayModeBar': True})

    with tab3:
        st.subheader("Upload Sky Photo Data")

        st.markdown("""
        ### Contribute to Light Pollution Research

        Help us build a comprehensive database of sky conditions by uploading your own sky photos with location and brightness data.
        """)

        # Create form for individual photo upload
        with st.form("photo_upload_form"):
            st.markdown("#### Upload Individual Sky Photo")

            # File uploader
            uploaded_file = st.file_uploader(
                "Choose a sky photo",
                type=["jpg", "jpeg", "png"],
                help="Upload a clear photo of the night sky"
            )

            # Location inputs
            st.markdown("##### Location Information")
            col_lat, col_lon = st.columns(2)

            with col_lat:
                latitude = st.number_input(
                    "Latitude",
                    min_value=-90.0,
                    max_value=90.0,
                    value=40.7128,
                    step=0.0001,
                    format="%.6f",
                    help="Latitude where the photo was taken (e.g., 40.7128)"
                )

            with col_lon:
                longitude = st.number_input(
                    "Longitude",
                    min_value=-180.0,
                    max_value=180.0,
                    value=-74.0060,
                    step=0.0001,
                    format="%.6f",
                    help="Longitude where the photo was taken (e.g., -74.0060)"
                )

            # Brightness rating
            st.markdown("##### Brightness Assessment")
            brightness_rating = st.slider(
                "Sky Brightness Rating",
                min_value=1,
                max_value=5,
                value=3,
                help="Rate the sky brightness: 1 (Very Dark) to 5 (Very Bright/Light Polluted)"
            )


            # Submit button
            submitted = st.form_submit_button("📤 Submit Photo Data", type="primary")

            if submitted:
                if uploaded_file is not None:
                    # Basic validation
                    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                        st.success("✅ Photo data submitted successfully!")
                        st.markdown(f"""
                        **Submission Summary:**
                        - **Location:** {latitude:.6f}, {longitude:.6f}
                        - **Brightness Rating:** {brightness_rating}/5
                        - **File:** {uploaded_file.name}
                        """)

                        # Analyze uploaded photo to detect constellations (single upload only)
                        with st.spinner("🔭 Analyzing photo to identify constellations..."):
                            try:
                                # Persist uploaded file to a temporary path
                                suffix = os.path.splitext(uploaded_file.name)[-1] or ".jpg"
                                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                                    tmp_file.write(uploaded_file.getbuffer())
                                    temp_path = tmp_file.name

                                # Call Astrometry.net workflow to detect constellations
                                detected_constellations = setConstellation(temp_path) or []

                                if detected_constellations:
                                    st.success("⭐ Detected constellations:")
                                    for cname in detected_constellations:
                                        st.markdown(f"- {cname}")
                                else:
                                    st.warning("No constellations could be confidently identified.")

                            except Exception as e:
                                st.error(f"Constellation detection failed: {e}")
                            finally:
                                try:
                                    if os.path.exists(temp_path):
                                        os.remove(temp_path)
                                except Exception:
                                    pass

                        # Persist the new submission depending on data source
                        try:
                            from datetime import datetime

                            # Save uploaded image to a persistent local uploads/ folder
                            uploads_dir = os.path.join(os.getcwd(), "uploads")
                            os.makedirs(uploads_dir, exist_ok=True)
                            saved_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
                            saved_path = os.path.join(uploads_dir, saved_filename)
                            with open(saved_path, "wb") as out_f:
                                out_f.write(uploaded_file.getbuffer())

                            # Normalize record
                            new_record = {
                                "id": f"U-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
                                "photo_url": saved_path,  # local path usable by st.image
                                "latitude": float(latitude),
                                "longitude": float(longitude),
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "brightness_rating": int(brightness_rating),
                                "constellation_name": detected_constellations[0] if detected_constellations else "",
                                "constellation_names": detected_constellations,
                            }

                            if use_db:
                                # Insert into Supabase 'photos' table
                                try:
                                    from supabase import create_client
                                    supabase_url = os.environ.get("SUPABASE_URL")
                                    supabase_key = os.environ.get("SUPABASE_ANON_KEY")
                                    if not supabase_url or not supabase_key:
                                        raise ValueError("Missing SUPABASE_URL/SUPABASE_ANON_KEY env variables")
                                    sb = create_client(supabase_url, supabase_key)
                                    insert_payload = {
                                        "id": new_record["id"],
                                        "created_at": new_record["timestamp"],
                                        "photo_url": new_record["photo_url"],
                                        "brightness_level": new_record["brightness_rating"],
                                        "lat": new_record["latitude"],
                                        "long": new_record["longitude"],
                                        # user_id intentionally omitted
                                    }
                                    sb.table("photos").insert(insert_payload).execute()
                                    st.success("📥 Saved to Supabase database")
                                except Exception as db_e:
                                    st.error(f"Failed to save to database: {db_e}")
                            else:
                                # Append to mock_data.json
                                try:
                                    mock_path = DEFAULT_CONFIG.get("mock_path", "mock_data.json")
                                    # Read existing
                                    existing = []
                                    if os.path.exists(mock_path):
                                        with open(mock_path, "r", encoding="utf-8") as f:
                                            existing = json.load(f)
                                            if not isinstance(existing, list):
                                                existing = []
                                    existing.append(new_record)
                                    with open(mock_path, "w", encoding="utf-8") as f:
                                        json.dump(existing, f, ensure_ascii=False, indent=2, default=str)
                                    st.success("🧪 Added to mock JSON data")
                                except Exception as jf_e:
                                    st.error(f"Failed to append to mock JSON: {jf_e}")

                            # Optionally refresh the app to show new data
                            st.info("Refreshing to include your submission in visualizations...")
                            st.rerun()
                        except Exception as persist_e:
                            st.error(f"Failed to persist submission: {persist_e}")

                    else:
                        st.error("❌ Invalid coordinates. Please check latitude (-90 to 90) and longitude (-180 to 180).")
                else:
                    st.error("❌ Please upload a photo file before submitting.")
        with tab5:
            st.markdown("""### What is SkyLore?

The HackTX 2025 theme, **"Celestial,"** immediately intrigued us. During the opening ceremony’s tribute to Indigenous peoples, a question sparked our imagination:  
*Did every ancient culture see the sky differently? Why do we only use the Roman constellations today?*

As we brainstormed, we discovered that one of our teammates had Indigenous roots — and from that connection, **SkyLore** was born. We wanted to go beyond building just an educational app. Our goal became to **combine cultural learning with citizen science** — allowing people to explore how different civilizations viewed the stars while contributing real data to modern research.

By inviting users to photograph the night sky and share their observations, SkyLore transforms cultural curiosity into meaningful impact. Each submission adds to a growing, public dataset that visualizes global **light pollution trends**, helping scientists, educators, and communities understand how our skies are changing.

As users learn about lost constellations and the stories behind them, they also become **citizen scientists**, helping preserve the beauty and knowledge of the night sky for generations to come.

---

### Components of SkyLore

### 1. Mobile App

Our mobile app allows users to explore the night sky interactively:

- **Compass-Based Navigation:** Look around using your device’s compass to explore different parts of the sky.  
- **Photo Capture & Collection:** Take photos of constellations and add them to your personal collection.  
- **Upload to Supabase:** Share your photos with the SkyLore community by uploading them to our **Supabase database**, contributing to the public dataset.

---

### 2. Streamlit App

Our Streamlit web app provides a rich interface for analyzing and visualizing collected data:

- **Constellation Library:** Browse a growing collection of constellations from different cultures.  
- **Light Pollution Heat Map:** Visualize light pollution across the globe, with filters for **date**, **constellation name**, and other parameters.  
- **Zone-Based Graphs:** Select a geographic zone to see how light pollution is changing over time.  
- **Data Insights:** Understand trends and impacts of light pollution on visibility of the night sky.
- **Photo Submissions:** Users can upload their night sky photos directly.  
- **Machine Learning Analysis:** Uploaded photos are sent to a **machine learning API** that identifies constellations and objects in the image.  
- **Community Contributions:** All submissions help improve the public dataset, supporting research, education, and conservation efforts.

---

### Impact

SkyLore bridges **cultural learning and citizen science**. By participating, users not only rediscover lost constellations but also contribute valuable data to track and reduce the effects of light pollution. Together, we preserve the stories of the sky and help future generations enjoy the beauty of a clear, starry night.

---
""")
        # CSV upload section
        st.markdown("---")
        st.markdown("#### Bulk Upload")

        st.markdown("""
        For researchers or users with multiple photos, you can upload a CSV file with the following columns:
        - `latitude`, `longitude`, `brightness_rating`, `timestamp`,`photo_url`
        """)

        csv_file = st.file_uploader("Upload CSV file", type="csv")

        if csv_file is not None:
            try:
                import io
                csv_data = pd.read_csv(io.StringIO(csv_file.getvalue().decode('utf-8')))
                st.success(f"✅ CSV file loaded successfully! Found {len(csv_data)} entries.")

                # Show preview of CSV data
                st.markdown("##### CSV Preview:")
                st.dataframe(csv_data.head(), use_container_width=True)

                if st.button("Send Data For Review"):
                    st.info("Data would be review and added to the database.")

            except Exception as e:
                st.error(f"❌ Error reading CSV file: {str(e)}")

        # Information about data usage
        st.markdown("---")
        st.markdown("""
        #### Data Usage & Privacy

        **What happens to your data:**
        - Photos and location data are used for light pollution research
        - Data is aggregated and anonymized for scientific analysis
        - Individual photos may be featured in research publications
        - All data contributes to our understanding of light pollution patterns

        **Privacy:** Location data is stored but never shared with third parties without consent.
        """)

    with tab4:
        st.markdown("""
        ### Constellations Across Cultures

        Learning about different cultures through their constellations reveals how people across time and place have looked to the same stars and found unique stories, values, and ways of understanding the world. It connects astronomy with humanity, showing that the night sky is both a shared canvas and a reflection of diverse perspectives.
        """)

        # Load cultural constellations data
        def load_cultural_data():
            try:
                with open("cultural_constellations.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert new structure to expected format for easier access
                    cultures_dict = {}
                    cultures_list = []

                    for culture_obj in data.get("constellation_data", []):
                        culture_name = culture_obj.get("name", "")
                        cultures_list.append(culture_name)

                        # Convert constellation structure to expected format
                        constellations_formatted = []
                        for const in culture_obj.get("constellations", []):
                            constellations_formatted.append({
                                "name": const.get("local_name", ""),
                                "description": const.get("description", ""),
                                "common_name": const.get("common_name", "")
                            })

                        cultures_dict[culture_name] = {
                            "name": culture_name,
                            "snippet": culture_obj.get("snippet", ""),
                            "constellations": constellations_formatted
                        }

                    return {
                        "cultures": cultures_list,
                        **cultures_dict
                    }
            except (FileNotFoundError, json.JSONDecodeError):
                # Fallback to basic structure if file doesn't exist or is malformed
                return {
                    "cultures": ["Ojibwe", "Cree", "Iroquois"],
                    "Ojibwe": {
                        "name": "Ojibwe",
                        "snippet": "Ojibwe star lore features animals and hunters from their local environment.",
                        "constellations": [
                            {"name": "Fisher", "description": "A great hunter constellation"}
                        ]
                    }
                }
            
        cultural_data = load_cultural_data()

        # Check if a specific constellation was clicked from the Info tab
        selected_constellation = st.session_state.get('selected_constellation', '')
        selected_culture_tab = st.session_state.get('selected_culture_tab', '')

        # Find which culture contains the selected constellation
        target_culture = None
        if selected_constellation and selected_culture_tab == "Cultural Constellations":
            for culture_name, culture_info in cultural_data.items():
                if isinstance(culture_info, dict) and 'constellations' in culture_info:
                    for const in culture_info['constellations']:
                        # Check both local_name and common_name
                        if (const.get('name', '').lower() == selected_constellation.lower() or
                            const.get('common_name', '').lower() == selected_constellation.lower()):
                            target_culture = culture_name
                            break
                    if target_culture:
                        break

        # Culture selector with optional pre-selection
        culture_options = cultural_data["cultures"]
        default_index = 0
        if target_culture and target_culture in culture_options:
            default_index = culture_options.index(target_culture)

        culture = st.selectbox(
            "Choose a cultural tradition:",
            culture_options,
            index=default_index,
            help="Select a culture to learn about their constellation traditions"
        )

        # Display information based on selected culture
        if culture in cultural_data:
            culture_info = cultural_data[culture]

            # Display culture name and snippet
            st.markdown(f"#### {culture_info.get('name', culture)}")
            if 'snippet' in culture_info:
                st.markdown(f"*{culture_info['snippet']}*")

            # Display constellations if available
            if 'constellations' in culture_info and culture_info['constellations']:
                st.markdown("##### Key Constellations:")

                # Check if we should highlight a specific constellation
                highlight_constellation = None
                if selected_constellation and selected_culture_tab == "Cultural Constellations":
                    highlight_constellation = selected_constellation

                for i, constellation in enumerate(culture_info['constellations'], 1):
                    const_name = constellation.get('name', 'Unknown')
                    const_desc = constellation.get('description', 'No description available')

                    # Highlight the selected constellation
                    if highlight_constellation and (const_name.lower() == highlight_constellation.lower() or
                                                  constellation.get('common_name', '').lower() == highlight_constellation.lower()):
                        st.markdown(f"**⭐ {i}. {const_name}** ← *Selected from data*")
                        if constellation.get('common_name'):
                            st.markdown(f"   *Also known as: {constellation['common_name']}*")
                        st.markdown(f"   {const_desc}")
                        st.markdown("")  # Add spacing
                    else:
                        st.markdown(f"**{i}. {const_name}**")
                        if constellation.get('common_name'):
                            st.markdown(f"   *Also known as: {constellation['common_name']}*")
                        st.markdown(f"   {const_desc}")
                        st.markdown("")  # Add spacing

                # Clear the session state after using it
                if selected_constellation:
                    st.session_state.selected_constellation = ''
                    st.session_state.selected_culture_tab = ''



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
        st.markdown(f"**Total Photos (after filters):** {len(filtered)}  ")
        st.markdown(f"**Sky photos in selected area:** {len(area_filtered)}  ")
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

                    # Handle both single and multiple constellations for display
                    def format_constellations(row):
                        # Try multiple constellations first (new format)
                        if 'constellation_names' in row:
                            constellations = row['constellation_names']
                            if constellations and len(constellations) > 0:
                                # Filter out empty strings and join
                                valid_constellations = [c for c in constellations if c and str(c).strip()]
                                if valid_constellations:
                                    return ', '.join(valid_constellations)

                        # Fall back to single constellation (legacy format)
                        if 'constellation_name' in row and row['constellation_name']:
                            constellation = row['constellation_name']
                            if constellation and str(constellation).strip():
                                return str(constellation).strip()

                        return 'Unknown'

                    # Make constellation name clickable if it exists in cultural data
                    constellation_display = format_constellations(row)
                    if constellation_display and constellation_display != 'Unknown':
                        # Check if this constellation exists in any cultural database
                        constellation_clickable = False
                        for culture_name, culture_info in cultural_data.items():
                            if isinstance(culture_info, dict) and 'constellations' in culture_info:
                                for const in culture_info['constellations']:
                                    # Check both local_name and common_name
                                    if (const.get('name', '').lower() == constellation_display.lower() or
                                        const.get('common_name', '').lower() == constellation_display.lower()):
                                        constellation_clickable = True
                                        break
                                if constellation_clickable:
                                    break

                        if constellation_clickable:
                            # Create clickable constellation link using columns for better styling
                            col_const, col_link = st.columns([3, 1])
                            with col_const:
                                st.markdown(f"**Constellation:** {constellation_display}")
                            with col_link:
                                if st.button("🔗 Learn", key=f"const_{row['id']}_{constellation_display}", help="Click to learn about this constellation"):
                                    # Store the selected constellation in session state
                                    st.session_state.selected_constellation = constellation_display
                                    st.session_state.selected_culture_tab = "Cultural Constellations"
                                    st.rerun()
                        else:
                            st.markdown(f"**Constellation:** {constellation_display}  ")
                    else:
                        st.markdown(f"**Constellation:** {constellation_display}  ")
                    st.markdown(f"**Brightness:** {row['brightness_rating']}  ")
                    st.markdown(f"**Timestamp:** {row['timestamp']}  ")
                    st.markdown(f"**Location:** {row['latitude']}, {row['longitude']}  ")
            st.markdown("---")
        st.markdown("Tips:\n- Use the map tabs to switch between scatter and heatmap views.\n- Adjust the area selection to focus on a region.\n- If you switch to DB mode, implement loading in `data_loader.py`.")

st.markdown("---")
st.markdown("Built for testing with mock JSON. Switch to DB mode by editing `DEFAULT_CONFIG` in `app.py` and implementing DB loading in `data_loader.py`.")
st.markdown("HackTX2025 Celestial | SkyLore Project")