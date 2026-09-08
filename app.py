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
    compute_fiscal_impact,
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
fiscal = compute_fiscal_impact(incidents_df)

st.title("🛡️ Goat Island Preserve: Live GeoAI Dumping & Hazard Monitor")
st.caption(f"📍 Dallas County District 3 | Lower Trinity River Basin | Auto-updated: **{update_timestamp}**")

total_metric_tons = incidents_df['mass_metric_tons'].sum()
total_tires = incidents_df['calc_tires'].sum()
total_volume = incidents_df['vol_m3'].sum()

col1, col2, col3, col4, col5 = st.columns(5)

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
        value=f"{len(forecast_res)} Predicted Zones",
        delta="Next 14–30 Days (Elevated)",
        delta_color="inverse"
    )

with col5:
    st.metric(
        label="Est. Cleanup Liability",
        value=f"${fiscal['total_taxpayer_cost']:,.0f}",
        delta=f"+${fiscal['potential_fine_recovery']:,.0f} Fine Recov.",
        delta_color="normal"
    )

st.markdown("---")

map_col, panel_col = st.columns([3, 1])

with panel_col:
    st.subheader("⚙️ Map Filters")
    show_historical = st.checkbox("Show Quantified Piles", value=True)
    show_future = st.checkbox("Show Forecasted Future Zone", value=True)
    show_heatmap = st.checkbox("Render Spatial Density Heatmap", value=False)
    
    st.markdown("---")
    st.markdown(f"### 🎯 Forecasted Zones ({len(forecast_res)})")
    for i, spot in enumerate(forecast_res, 1):
        st.warning(
            f"**Zone {i}: {spot['corridor']}**\n\n"
            f"• Confidence: **{spot['confidence']*100:.0f}%**\n"
            f"• Radius: ~{spot['radius_meters']}m\n"
            f"• Trigger: {spot['driving_cause']}"
        )
        
    st.markdown("### 🚨 Recommended Intervention")
    st.info("Rotate solar ALPR cameras between identified corridors based on confidence priority.")

with map_col:
    m = folium.Map(location=[32.628, -96.645], zoom_start=14, tiles="OpenStreetMap")
    
    # 1. Dedicated Goat Island Preserve County Parcel (Riparian River Corridor)
    folium.Polygon(
        locations=[
            [32.6420, -96.6350],
            [32.6320, -96.6230],
            [32.6120, -96.6380],
            [32.6100, -96.6530],
            [32.6200, -96.6570],
            [32.6290, -96.6490],
            [32.6380, -96.6450]
        ],
        color="#1E8449",
        weight=2.5,
        fill=True,
        fill_color="#2ECC71",
        fill_opacity=0.12,
        tooltip="Dallas County Open Space: Goat Island Preserve (Core ~637 Acres)"
    ).add_to(m)

    # 2. Inter-Jurisdictional Ingress & Buffer Zone (City of Hutchins / County Road Interface)
    folium.Rectangle(
        bounds=[[32.615, -96.668], [32.642, -96.648]],
        color="#8E44AD",
        weight=1.5,
        dash_array="5, 5",
        fill=True,
        fill_color="#9B59B6",
        fill_opacity=0.04,
        tooltip="Buffer: Post Oak Rd & Fulghum Ingress Corridor (Hutchins / County Transition)"
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
        for spot in forecast_res:
            popup_html = f"""
            <div style="font-family: Arial; width: 220px;">
                <h5 style="color: #D35400; margin: 0 0 4px 0;">🎯 {spot['corridor']}</h5>
                <b>Risk Horizon:</b> {spot['forecast_window']}<br>
                <b>Confidence:</b> {spot['confidence']*100:.0f}%<br>
                <b>Trigger:</b> {spot['driving_cause']}<br>
                <b>Action:</b> Deploy ALPR Surveillance
            </div>
            """
            folium.Circle(
                location=[spot['pred_lat'], spot['pred_lon']],
                radius=spot['radius_meters'],
                color="#D35400",
                weight=3,
                dash_array="6, 6",
                fill=True,
                fill_color="#E67E22",
                fill_opacity=0.35,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"🎯 Predicted Zone: {spot['corridor']} ({spot['confidence']*100:.0f}%)"
            ).add_to(m)
            folium.Marker(
                location=[spot['pred_lat'], spot['pred_lon']],
                icon=folium.Icon(color="orange", icon="crosshairs", prefix="fa"),
                popup=folium.Popup(popup_html, max_width=250)
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
    
    st.markdown("#### 📊 Statistical Waste Profile & Operational Insights")
    
    stat_col1, stat_col2 = st.columns(2)
    
    with stat_col1:
        st.caption("**Mass Distribution by Debris Classification (Metric Tons)**")
        mass_by_type = incidents_df.groupby('debris_type')['mass_metric_tons'].sum().reset_index()
        mass_by_type.columns = ['Debris Class', 'Total Mass (Tons)']
        st.bar_chart(mass_by_type, x='Debris Class', y='Total Mass (Tons)', color="#C0392B")

    with stat_col2:
        st.caption("**Dumping Incident Frequency by Day of Week**")
        incidents_df['Day_Name'] = pd.Categorical(
            incidents_df['created_date'].dt.day_name(),
            categories=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
            ordered=True
        )
        day_counts = incidents_df['Day_Name'].value_counts().sort_index().reset_index()
        day_counts.columns = ['Day of Week', 'Incidents Logged']
        st.line_chart(day_counts, x='Day of Week', y='Incidents Logged', color="#2980B9")

    st.markdown("---")
    
    csv_data = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⚖️ Export Environmental Marshal Case Dossier (CSV)",
        data=csv_data,
        file_name="DallasCounty_GoatIsland_Violations_Dossier.csv",
        mime="text/csv",
        help="Formatted evidence packet ready for Dallas County District Attorney citation filings"
    )

    st.dataframe(display_df.style.format({
        'Footprint (m²)': '{:.1f}',
        'Est. Vol (m³)': '{:.1f}',
        'Mass (Metric Tons)': '{:.2f}',
        'Latitude': '{:.4f}',
        'Longitude': '{:.4f}'
    }), use_container_width=True)



with st.expander("🛠️ Municipal Remediation & Policy Action Plan (Dallas County / City of Hutchins)"):
    st.markdown("""
    ### Phase 1: Immediate Target Hardening & Physical Access Control
    * **Crash-Rated Perimeter Gates:** Install heavy-duty steel pipe swing gates at the paved-to-unpaved transition of **Post Oak Rd** and the **Fulghum Rd spur**, keyed with Knox-Boxes for first responders and park personnel.
    * **Earthen Berms & Riprap Barrier:** Construct $4\text{ ft}$ continuous earthen berms and line vulnerable drainage swales with $3\text{ ft}$ limestone riprap boulders to eliminate four-wheel-drive bypass tracks onto the levee margins.

    ### Phase 2: Prosecutable Surveillance Infrastructure
    * **Solar ALPR Corridors:** Deploy mobile solar automated license plate reader (ALPR) trailers at the Post Oak Road entrance funnel.
    * **Automated Webhook Dispatch:** Program ALPR detections of heavy multi-axle commercial vehicles entering the preserve turnaround after sunset (park curfew) to trigger instant notifications for Dallas County Sheriff / Marshal dispatch.
    * **Evidentiary Standard:** Align image capture timestamps with **Texas Health & Safety Code § 365.012** parameters to provide the Dallas County District Attorney with admissible evidence for Class A misdemeanor prosecution.

    ### Phase 3: Cross-Jurisdictional Interlocal Agreement (ILA)
    * **Close the Enforcement Gap:** Formalize an Interlocal Agreement between **Dallas County Commissioner District 3** and the **City of Hutchins**.
    * **Unified Right-of-Way Jurisdiction:** Empower Dallas County Environmental Marshals to cite commercial haulers on municipal road segments feeding directly into county preserve gates.
    * **Reinvestment Escrow:** Direct all recovered Chapter 365 fines (up to $10,000 per commercial offense) into a dedicated Goat Island Preserve ecological remediation and surveillance fund.

    ### Phase 4: Upstream Commercial Hauler Regulation
    * **Mandatory Disposal Manifest Audits:** Enforce state waste tracking manifests for independent commercial contractors, roofers, and tire repair operations along the I-45 / Fulghum industrial corridor.
    * **Tipping Fee Subsidy / Spot Checks:** Rebalance the local economic incentive by matching spot-check enforcement with voucher programs for the McCommas Bluff Landfill to divert debris from sensitive bottomland hardwood floodplains.
    """)

with st.expander("📚 Methodology, Data Provenance & Statutory Framework"):
    st.markdown("""
    ### 1. Primary Data Streams & Sensor Provenance
    * **USGS Hydrological Ingestion:** Real-time streamflow and gage height retrieved via the [USGS Water Services REST API](https://waterservices.usgs.gov/) from **Station #08062500 (Trinity River near Rosser, TX)**. Stage elevations above $18.0\text{ ft}$ trigger uphill spatial displacement routines to model impassable alluvium.
    * **Municipal Code Violations & GIS Inventories:** Spatial dump coordinates and baseline material classes calibrated using [Dallas OpenData](https://dallasopendata.com/) (*311 Service Requests: Illegal Dumping*) filtered for Lower Trinity Basin riparian buffers and Dallas County Open Space preserve borders.
    * **Cartographic Basemaps & Infrastructure:** Road network vector topologies and parcel transitions derived from **OpenStreetMap Contributors (OSM)** and **NCTCOG** (North Central Texas Council of Governments) regional GIS datasets.

    ### 2. Waste Volumetric & Mass Quantification Factors
    Volumetric conversions use field-derived compaction ratios and the **EPA Waste Reduction Model (WARM v15)** standards:
    * **Scrap Tires:** $0.024\text{ metric tons/unit}$ (~$22.5\text{ lbs/tire}$) per EPA scrap tire recovery factors.
    * **Construction & Demolition (C&D) Rubble:** Bulk bulk-density factor of $0.45\text{ metric tons/m}^3$.
    * **Bulk Furniture / MSW:** Density factor of $0.24\text{ metric tons/m}^3$ across delineated surface footprints.

    ### 3. Fiscal Remediation & Statutory Liability Baselines
    * **Remediation Cost Model:** Calibrated against average municipal abatement contracting schedules: **$450.00/ton** (C&D Hazmat sorting), **$385.00/ton** (Mixed Municipal Solid Waste), **$4.75/unit** (Tire environmental recycling surcharge), plus heavy machinery mobilization.
    * **Enforcement & Fine Recovery:** Modeled pursuant to **Texas Health & Safety Code Chapter 365 (Texas Litter Abatement Act)**, categorizing unpermitted commercial dumping exceeding $200\text{ lbs}$ (or $5\text{ gallons}$) as a Class A Misdemeanor with corporate criminal penalties up to **$10,000 per violation**.

    ### 4. Predictive Machine Learning Architecture
    * **Spatial Clustering:** Density-Based Spatial Clustering of Applications with Noise (**DBSCAN**) using haversine geodesic distance ($250\text{m}$ spatial search neighborhood, $\text{MinPts}=2$).
    * **Temporal Hawkes Process:** Self-exciting point process with exponential recency decay ($\\beta = 0.05$, corresponding to an empirical half-life of $\\sim 14\text{ days}$) dynamically weighted against hydrologic stage saturation.
    """)
