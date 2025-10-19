"""
visualizations.py

Plotting functions using plotly.express for SkyLore.
Earthy tones palette is applied to maps and time-series.
"""
from typing import Optional
import pandas as pd
import plotly.express as px


# Earthy palette (muted greens, browns, golds, deep orange)
EARTHY_CONTINUOUS = ["#5B8C5A", "#8F6B3E", "#C69C6D", "#D9822B"]
EARTHY_DISCRETE = ["#5B8C5A", "#8F6B3E", "#C69C6D", "#D9822B", "#A67C52"]

# Vibrant palette for heat maps (dark blue to yellow gradient)
VIBRANT_CONTINUOUS = ["#003366", "#0066CC", "#0099FF", "#33CCFF", "#66FFCC", "#CCFF99", "#FFFF66"]


def scatter_map(df: pd.DataFrame, mapbox_token: Optional[str] = None, center_lat: Optional[float] = None, center_lon: Optional[float] = None, radius_km: Optional[float] = None) -> px.scatter_mapbox:
    """Return a scatter map of submissions using brightness_rating for color/size.

    Hover includes id, constellation_name, photo_url, and timestamp.
    """
    if df.empty:
        return px.scatter_mapbox()

    # Create constellation_info column for hover display (handles both single and multiple constellations)
    def format_constellation_info(row):
        if 'constellation_names' in row and isinstance(row['constellation_names'], list) and row['constellation_names']:
            return ', '.join(row['constellation_names'])
        elif 'constellation_name' in row and row['constellation_name']:
            return row['constellation_name']
        return 'Unknown'

    df = df.copy()
    df['constellation_info'] = df.apply(format_constellation_info, axis=1)

    # Add fixed size column for consistent point sizing
    df = df.copy()
    df['point_size'] = 12  # Fixed size for all points

    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        color="brightness_rating",
        size="point_size",  # Use fixed size column
        # use custom_data so we can craft a clean hovertemplate - handle both single and multiple constellations
        custom_data=["id", "constellation_info", "timestamp", "photo_url"],
        color_continuous_scale=VIBRANT_CONTINUOUS,
        size_max=12,
        zoom=3,
        height=600,
        labels={"brightness_rating": "Brightness"},
    )
    if mapbox_token:
        fig.update_layout(mapbox=dict(accesstoken=mapbox_token, style="streets"))
    else:
        fig.update_layout(mapbox_style="open-street-map")

    # Adjust colorbar: more compact, better text contrast
    fig.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        paper_bgcolor="#2B1F14",
            coloraxis_colorbar=dict(
                len=0.9,          # shorter height to avoid map controls
                thickness=10,     # slightly thicker bar
                title=dict(
                    text="Brightness",
                    side="top"
                ),
                ticks="outside",
                ticktext=["1", "2", "3", "4", "5"],
                tickvals=[1, 2, 3, 4, 5],
                tickmode="array",
                bgcolor="rgba(43,31,20,0.9)",  # dark brown background for dark theme
                title_font_color="#E6E2D3",
                tickfont_color="#E6E2D3",
                yanchor="middle",  # center vertically
                y=0.5,           # position within container
                xanchor="right",  # align to right
                x=1.0,           # rightmost position
                outlinewidth=1,   # add a thin outline
                outlinecolor="rgba(0,0,0,0.2)"
            ),
            coloraxis=dict(
                cmin=1,          # force minimum value to 1
                cmax=5,          # force maximum value to 5
            )
    )

    # Improve hover popup: show a compact, styled tooltip with useful fields
    hovertemplate = (
        "ID: %{customdata[0]}<br>"
        "Constellation: %{customdata[1]}<br>"
        "Brightness: %{marker.color}<br>"
        "Timestamp: %{customdata[2]}<br>"
        "URL: %{customdata[3]}<extra></extra>"
    )
    # Apply hover and marker styling per trace to avoid property-path issues
    for tr in fig.data:
        try:
            if getattr(tr, "type", None) == "scattermapbox":
                # hover
                tr.hovertemplate = hovertemplate
                tr.hoverlabel = dict(bgcolor="#FFFFFF", bordercolor="#888888", font=dict(color="#000000"))
                # marker styling (attempt direct attribute assignment first)
                if hasattr(tr, "marker"):
                    try:
                        tr.marker.opacity = 0.85
                        # some Plotly versions expose marker.line as nested object
                        if hasattr(tr.marker, "line"):
                            tr.marker.line.width = 1
                            tr.marker.line.color = "rgba(0,0,0,0.15)"
                        else:
                            # fallback to update with nested dict
                            tr.update(marker=dict(opacity=0.85, line=dict(width=1, color="rgba(0,0,0,0.15)")))
                    except Exception:
                        tr.update(marker=dict(opacity=0.85, line=dict(width=1, color="rgba(0,0,0,0.15)")))
        except Exception:
            # if anything goes wrong for a trace, skip it (avoid breaking the whole figure)
            continue
    # If a center point was provided, add a highlighted marker trace (no legend)
    if center_lat is not None and center_lon is not None:
        try:
            fig.add_scattermapbox(lat=[center_lat], lon=[center_lon], mode="markers+text",
                                  marker=dict(size=10, color="#D22B2B", opacity=0.9),
                                  text=["Center"], textposition="top right",
                                  hoverinfo="skip", showlegend=False)

            # Add a circle trace if radius_km is provided
            if radius_km is not None:
                # Create circle points around center
                import numpy as np
                center_point = (center_lat, center_lon)
                radius_degrees = radius_km / 111  # Rough conversion: 1 degree ≈ 111 km

                # Generate circle points
                theta = np.linspace(0, 2*np.pi, 100)
                circle_lats = center_lat + (radius_degrees * np.cos(theta))
                circle_lons = center_lon + (radius_degrees * np.sin(theta) / np.cos(np.radians(center_lat)))

                # Add filled circle (polygon)
                fig.add_scattermapbox(
                    lat=np.concatenate([circle_lats, [circle_lats[0]]]),
                    lon=np.concatenate([circle_lons, [circle_lons[0]]]),
                    mode="lines",
                    fill="toself",
                    line=dict(color="#D22B2B", width=2),
                    fillcolor="rgba(210, 43, 43, 0.2)",
                    hoverinfo="skip",
                    showlegend=False,
                    name="Radius Area"
                )
        except Exception:
            pass
    return fig



def heatmap_map(df: pd.DataFrame, mapbox_token: Optional[str] = None, center_lat: Optional[float] = None, center_lon: Optional[float] = None, radius_km: Optional[float] = None) -> px.density_mapbox:
    """Return a true heatmap using density_mapbox with brightness-weighted z values."""
    if df.empty:
        return px.density_mapbox()

    # Create a proper brightness-weighted density map
    # We'll use the z parameter to represent brightness density

    # Calculate weighted z-values that represent brightness intensity
    # This creates a z-value that combines both density and brightness
    heatmap_df = df.copy()

    # For each point, create a z-value that represents brightness density
    # Higher brightness = higher contribution to local density
    heatmap_df['brightness_weight'] = heatmap_df['brightness_rating'] ** 2  # Square for more dramatic effect

    fig = px.density_mapbox(
        heatmap_df,
        lat="latitude",
        lon="longitude",
        z="brightness_weight",  # Use brightness-weighted values
        radius=30,  # Good balance of smoothness and detail
        center=dict(lat=df["latitude"].mean(), lon=df["longitude"].mean()),
        zoom=3,
        height=600,
        color_continuous_scale=VIBRANT_CONTINUOUS,
        hover_data={"brightness_weight": False},  # Hide confusing hover values
        labels={"brightness_weight": "Brightness"},
    )
    if mapbox_token:
        fig.update_layout(mapbox=dict(accesstoken=mapbox_token, style="streets"))
    else:
        fig.update_layout(mapbox_style="open-street-map")

    # Adjust colorbar: more compact, better text contrast
    fig.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        paper_bgcolor="#2B1F14",
        coloraxis_colorbar=dict(
            len=0.9,          # match scatter map height
            thickness=10,     # match scatter map thickness
            title=dict(
                text="Brightness",
                side="top"
            ),
            ticks="outside",
            ticktext=["1", "2", "3", "4", "5"],
            tickvals=[1, 6, 11, 16, 25],  # Position ticks at meaningful points in the 1-25 range
            tickmode="array",
            bgcolor="rgba(43,31,20,0.9)",  # dark brown background for dark theme
            title_font_color="#E6E2D3",
            tickfont_color="#E6E2D3",
            yanchor="middle",  # center vertically
            y=0.5,           # match scatter map position
            xanchor="right",  # align to right
            x=1.0,           # rightmost position
            outlinewidth=1,   # add a thin outline
            outlinecolor="rgba(0,0,0,0.2)"
        ),
        coloraxis=dict(
            cmin=1,          # minimum brightness weight (1^2)
            cmax=25,         # maximum brightness weight (5^2)
        )
    )
    # If a center point was provided, add a highlighted marker trace and circle
    if center_lat is not None and center_lon is not None:
        try:
            fig.add_scattermapbox(lat=[center_lat], lon=[center_lon], mode="markers+text",
                                  marker=dict(size=10, color="#D22B2B", opacity=0.9),
                                  text=["Center"], textposition="top right",
                                  hoverinfo="skip", showlegend=False)

            # Add a circle trace if radius_km is provided
            if radius_km is not None:
                # Create circle points around center
                import numpy as np
                center_point = (center_lat, center_lon)
                radius_degrees = radius_km / 111  # Rough conversion: 1 degree ≈ 111 km

                # Generate circle points
                theta = np.linspace(0, 2*np.pi, 100)
                circle_lats = center_lat + (radius_degrees * np.cos(theta))
                circle_lons = center_lon + (radius_degrees * np.sin(theta) / np.cos(np.radians(center_lat)))

                # Add filled circle (polygon)
                fig.add_scattermapbox(
                    lat=np.concatenate([circle_lats, [circle_lats[0]]]),
                    lon=np.concatenate([circle_lons, [circle_lons[0]]]),
                    mode="lines",
                    fill="toself",
                    line=dict(color="#D22B2B", width=2),
                    fillcolor="rgba(210, 43, 43, 0.2)",
                    hoverinfo="skip",
                    showlegend=False,
                    name="Radius Area"
                )
        except Exception:
            pass
    return fig


def time_series(df: pd.DataFrame, freq: str = "D") -> px.line:
    """Return a time series of average brightness_rating over time.

    freq: 'D' daily, 'W' weekly, 'M' monthly
    """
    if df.empty:
        return px.line()

    ts = df.set_index("timestamp").resample(freq).brightness_rating.mean().reset_index()
    fig = px.line(ts, x="timestamp", y="brightness_rating", title="Average Brightness Over Time",
                  color_discrete_sequence=["#D9822B"])
    fig.update_layout(height=300, margin={"r":10,"t":30,"l":10,"b":10}, plot_bgcolor="#3A2C1D")
    fig.update_yaxes(title_text="Avg Brightness (1-5)")
    fig.update_traces(line=dict(shape="spline", smoothing=1.0), connectgaps=True)
    return fig


def recent_table(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Return recent submissions (suitable to display in Streamlit)."""
    cols = ["timestamp", "id", "brightness_rating", "constellation_name", "latitude", "longitude", "photo_url"]
    return df.sort_values("timestamp", ascending=False).head(n)[cols]
