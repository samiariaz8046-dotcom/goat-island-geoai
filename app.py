"""
app.py
Interactive Streamlit Cloud Dashboard for Goat Island Preserve.
"""

import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import pandas as pd
from datetime import datetime

from pipeline_engine import (
    fetch_usgs_river_stage,
    fetch_dumping_incidents,
    quantify_waste_inventory,
    forecast_future_hotspots,
    PRESERVE_BBOX
)

st.set_page_config(
    page_title="Goat Island | AI Illegal Dumping & Inundation Monitor",
    page_icon="🛡️",
    layout="wide"
)

@st.cache_data(ttl=900)
def execute_live_pipeline():
    stage = fetch_usgs_river_stage()
    raw_incidents = fetch_dumping_incidents()
    quantified_df = quantify_waste_inventory(raw_incidents)
    forecast = forecast_future_hotspots(quantified_df, stage)
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return stage, quantified_df, forecast, last_updated

river_stage, incidents_df, forecast_res, update_timestamp = execute_live_pipeline()

st.title("🛡️ Goat Island Preserve: Live GeoAI Dumping & Hazard Monitor")
st.caption(f"📍 Dallas County District 3 | Lower Trinity River Basin | Auto-updated: **{update_timestamp}**")

total_metric_tons = incidents_df['mass_metric_tons'].sum()
total_tires = incidents_df['calc_tires'].sum()
total_volume = incidents_df['vol_m3'].sum()

col1, col2, col3, col4 = st.columns(4)

with col1:
    stage_delta = "Flood Warning" if river_stage > 20.0 else ("Caution: Saturated" if river_stage > 16.0 else "Normal Stage")
    st.metric(
        label="USGS Trinity River Stage",
        value=f"{river_stage:.1f} ft",
        delta=stage_delta,
        delta_color="inverse" if river_stage > 16.0 else "normal"
    )

with col2:
    st.metric(
        label="Total Quantified Waste",
        value=f"{total_metric_tons:,.1f} Tons",
        delta=f"{total_volume:,.0f} m³ Volume"
    )

with col3:
    st.metric(
        label="Scrap Tires Logged",
        value=f"{total_tires:,} Units",
        delta="EPA WARM Factor"
    )

with col4:
    st.metric(
        label="Future Risk Status",
        value="Elevated",
        delta=f"{forecast_res['forecast_window']} ({forecast_res['confidence']*100:.0f}% Conf.)",
        delta_color="inverse"
    )

st.markdown("---")

map_col, panel_col = st.columns([3, 1])

with panel_col:
    st.subheader("⚙️ Map Filters")
    show_historical = st.checkbox("Show Quantified Piles", value=True)
    show_future = st.checkbox("Show Forecasted Future Zone", value=True)
    show_heatmap = st.checkbox("Render Spatial Density Heatmap", value=False)
    
    st.markdown("---")
    st.markdown("### 🎯 Future Forecast Details")
    st.warning(
        f"**Risk Horizon:** {forecast_res['forecast_window']}\n\n"
        f"**Model Confidence:** {forecast_res['confidence']*100:.0f}%\n\n"
        f"**Target Location:** Lat {forecast_res['pred_lat']:.4f}, Lon {forecast_res['pred_lon']:.4f}\n\n"
        f"**Search Radius:** ~{forecast_res['radius_meters']} meters\n\n"
        f"**Contagion Trigger:** {forecast_res['driving_cause']}"
    )
    
    st.markdown("### 🚨 Recommended Intervention")
    st.info("Deploy mobile solar ALPR camera trailer at the Post Oak Road access turnaround prior to flood stage shifts.")

with map_col:
    m = folium.Map(location=[32.628, -96.645], zoom_start=14, tiles="OpenStreetMap")
    
    # Boundary box for Goat Island Preserve
    folium.Rectangle(
        bounds=[[32.610, -96.662], [32.640, -96.628]],
        color="#1B365D",
        weight=2,
        dash_array="4, 4",
        fill=True,
        fill_color="#27AE60",
        fill_opacity=0.05,
        tooltip="Goat Island Preserve Boundary (637 Acres)"
    ).add_to(m)

    if show_heatmap:
        heat_data = [[row['latitude'], row['longitude'], row['mass_metric_tons']] for _, row in incidents_df.iterrows()]
        plugins.HeatMap(
            heat_data,
            radius=15,
            blur=12,
            min_opacity=0.3,
            gradient={0.4: '#F1C40F', 0.7: '#E67E22', 1.0: '#C0392B'}
        ).add_to(m)

    if show_historical:
        for _, row in incidents_df.iterrows():
            marker_radius = min(14, max(5, int(row['mass_metric_tons'] * 1.5)))
            popup_html = f"""
            <div style="font-family: Arial; width: 200px;">
                <h5 style="color: #C0392B; margin: 0 0 4px 0;">{row.get('incident_id', 'Active Hotspot')}</h5>
                <b>Material:</b> {row['debris_type']}<br>
                <b>Est. Mass:</b> {row['mass_metric_tons']:.2f} Metric Tons<br>
                <b>Est. Tires:</b> {row['calc_tires']} units<br>
                <b>Surface Area:</b> {row['footprint_area_m2']:.1f} m²<br>
                <b>Logged:</b> {row['created_date'].strftime('%Y-%m-%d')}
            </div>
            """
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=marker_radius,
                color="#C0392B",
                fill=True,
                fill_color="#E74C3C",
                fill_opacity=0.7,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{row['debris_type']} ({row['mass_metric_tons']:.1f} Tons)"
            ).add_to(m)

    if show_future:
        future_popup_html = f"""
        <div style="font-family: Arial; width: 230px;">
            <h5 style="color: #D35400; margin: 0 0 6px 0;">🎯 PREDICTED FUTURE HOTSPOT</h5>
            <b>Window:</b> {forecast_res['forecast_window']}<br>
            <b>Model Confidence:</b> {forecast_res['confidence']*100:.0f}%<br>
            <b>Ingress Point:</b> Post Oak Rd Access Spur<br>
            <b>Contagion Trigger:</b> Hawkes Recency Clustering
        </div>
        """
        # Add popup to the entire circle area
        folium.Circle(
            location=[forecast_res['pred_lat'], forecast_res['pred_lon']],
            radius=forecast_res['radius_meters'],
            color="#D35400",
            weight=3,
            dash_array="6, 6",
            fill=True,
            fill_color="#E67E22",
            fill_opacity=0.4,
            popup=folium.Popup(future_popup_html, max_width=260),
            tooltip="🎯 CLICK HERE: Predicted Future Hotspot Zone"
        ).add_to(m)
        
        folium.Marker(
            location=[forecast_res['pred_lat'], forecast_res['pred_lon']],
            icon=folium.Icon(color="orange", icon="crosshairs", prefix="fa"),
            popup=folium.Popup(future_popup_html, max_width=260),
            tooltip="🎯 Predicted Future Hotspot Centroid"
        ).add_to(m)

    st_folium(m, width=950, height=580)

with st.expander("📁 View Detailed Incident & Quantification Inventory"):
    display_df = incidents_df[[
        'created_date', 'debris_type', 'footprint_area_m2', 
        'vol_m3', 'calc_tires', 'mass_metric_tons', 'latitude', 'longitude'
    ]].copy()
    display_df.columns = [
        'Date Logged', 'Debris Class', 'Footprint (m²)', 
        'Est. Vol (m³)', 'Tires (Qty)', 'Mass (Metric Tons)', 'Latitude', 'Longitude'
    ]
    st.dataframe(display_df.style.format({
        'Footprint (m²)': '{:.1f}',
        'Est. Vol (m³)': '{:.1f}',
        'Mass (Metric Tons)': '{:.2f}',
        'Latitude': '{:.4f}',
        'Longitude': '{:.4f}'
    }), use_container_width=True)
