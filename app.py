"""
app.py
Goat Island GeoAI: Illegal Dumping Detection, Risk & Management Decision-Support System
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
    calculate_decision_scores,
    generate_candidate_monitoring_zones
)

st.set_page_config(
    page_title="Goat Island GeoAI | Decision-Support System",
    page_icon="🛡️",
    layout="wide"
)

# 1. Research Prototype Disclaimer Banner
st.title("🛡️ Goat Island GeoAI: Illegal Dumping Detection, Risk & Management Decision-Support System")
st.warning(
    "⚠️ **Research Prototype:** Demonstration data are used for unverified incident attributes. "
    "Outputs are intended for methodology demonstration and research evaluation, not official Dallas County records "
    "or statutory enforcement determinations."
)

@st.cache_data(ttl=900)
def load_data_pipeline():
    stage = fetch_usgs_river_stage()
    raw = fetch_dumping_incidents()
    quantified = quantify_waste_inventory(raw)
    scored = calculate_decision_scores(quantified, stage)
    zones = generate_candidate_monitoring_zones(scored)
    return stage, scored, zones, datetime.now().strftime("%Y-%m-%d %H:%M:%S")

river_stage, df, candidate_zones, updated_time = load_data_pipeline()

# 2. Decision-First Operational Top Metrics
col1, col2, col3, col4, col5 = st.columns(5)

total_sites = len(df)
critical_sites = len(df[df['management_priority'] == 'CRITICAL'])
unverified_sites = len(df[df['evidence_status'].isin(['Reported', 'Remotely Detected'])])
near_drainage = len(df[df['consequence_score'] >= 70])
est_mass_low = df['mass_min_tons'].sum()
est_mass_high = df['mass_max_tons'].sum()

with col1:
    st.metric(label="Total Documented Sites", value=f"{total_sites} Sites", delta="Demonstration Set")
with col2:
    st.metric(label="High/Critical Priority", value=f"{critical_sites} Sites", delta="Action Required", delta_color="inverse")
with col3:
    st.metric(label="Estimated Total Mass", value=f"{est_mass_low:.0f}–{est_mass_high:.0f} t", delta="Bounded Range")
with col4:
    st.metric(label="Pending Field Check", value=f"{unverified_sites} Sites", delta="Unverified Evidence", delta_color="off")
with col5:
    st.metric(label="Near Drainage/River", value=f"{near_drainage} Sites", delta="Environmental Risk", delta_color="inverse")

st.markdown("---")

# 3. Interactive Map & Side Controls
map_col, filter_col = st.columns([3, 1])

with filter_col:
    st.subheader("⚙️ Map Layers")
    layer_incidents = st.checkbox("Incident Evidence Points", value=True)
    layer_zones = st.checkbox("Candidate Monitoring Zones", value=True)
    layer_heatmap = st.checkbox("Spatial Density Surface", value=False)
    
    st.markdown("---")
    st.subheader("🎯 Monitoring Candidate Zones")
    for z in candidate_zones:
        st.info(
            f"**{z['name']}**\n\n"
            f"• **Risk Score:** {z['risk_score']}/100\n"
            f"• **Recent Sites within 250m:** {z['recent_incidents']}\n"
            f"• **Road Accessibility:** {z['road_access']}\n"
            f"• **Concealment:** {z['concealment']}\n"
            f"• **Consequence:** {z['consequence']}\n"
            f"• **Status:** {z['status']}"
        )

with map_col:
    m = folium.Map(location=[32.628, -96.645], zoom_start=14, tiles="OpenStreetMap")
    
    # Delineate Core Preserve Parcel
    folium.Polygon(
        locations=[
            [32.6420, -96.6350], [32.6320, -96.6230], [32.6120, -96.6380],
            [32.6100, -96.6530], [32.6200, -96.6570], [32.6290, -96.6490], [32.6380, -96.6450]
        ],
        color="#1E8449",
        weight=2,
        fill=True,
        fill_color="#2ECC71",
        fill_opacity=0.08,
        tooltip="Dallas County Open Space: Goat Island Preserve (~637 Acres)"
    ).add_to(m)

    # Ingress Buffer Corridor
    folium.Rectangle(
        bounds=[[32.615, -96.668], [32.642, -96.648]],
        color="#8E44AD",
        weight=1.5,
        dash_array="4, 4",
        fill=True,
        fill_color="#9B59B6",
        fill_opacity=0.04,
        tooltip="Post Oak Rd Ingress Buffer (County / Municipal Interface)"
    ).add_to(m)

    # Incident Markers with Evidence Status Color-Coding
    priority_colors = {
        'CRITICAL': '#C0392B',
        'HIGH': '#E67E22',
        'MODERATE': '#F1C40F',
        'MONITOR': '#2980B9'
    }
    
    if layer_incidents:
        for _, r in df.iterrows():
            popup_html = f"""
            <div style="font-family: Arial; width: 230px;">
                <h5 style="margin: 0 0 4px 0; color: #1B365D;">Site {r['incident_id']}</h5>
                <b>Evidence Status:</b> {r['evidence_status']}<br>
                <b>Debris Class:</b> {r['debris_type']}<br>
                <b>Est. Quantity:</b> {r['calc_tires']} tires<br>
                <b>Footprint:</b> ~{r['footprint_m2']:.0f} m²<br>
                <b>Est. Mass:</b> {r['mass_min_tons']}–{r['mass_max_tons']} t<br>
                <hr style="margin: 4px 0;">
                <b>Susceptibility Score:</b> {r['susceptibility_score']}/100<br>
                <b>Consequence Score:</b> {r['consequence_score']}/100<br>
                <b>Management Priority:</b> <span style="color: {priority_colors[r['management_priority']]}; font-weight: bold;">{r['management_priority']}</span>
            </div>
            """
            folium.CircleMarker(
                location=[r['latitude'], r['longitude']],
                radius=7,
                color=priority_colors[r['management_priority']],
                fill=True,
                fill_color=priority_colors[r['management_priority']],
                fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{r['incident_id']} [{r['management_priority']}] - {r['evidence_status']}"
            ).add_to(m)

    # Candidate Monitoring Zones
    if layer_zones:
        for z in candidate_zones:
            folium.Circle(
                location=[z['lat'], z['lon']],
                radius=z['radius_m'],
                color="#D35400",
                weight=2.5,
                dash_array="5, 5",
                fill=True,
                fill_color="#E67E22",
                fill_opacity=0.25,
                tooltip=f"{z['name']} (Risk Score: {z['risk_score']}/100)"
            ).add_to(m)

    # Heatmap
    if layer_heatmap:
        heat_data = [[r['latitude'], r['longitude'], r['mid_mass_tons']] for _, r in df.iterrows()]
        plugins.HeatMap(heat_data, radius=16, blur=14, min_opacity=0.3).add_to(m)

    st_folium(m, width=950, height=560)

# 4. Detailed Tabular Inventory with Uncertainty Intervals
with st.expander("📁 Detailed Incident Evidence & Evaluative Scoring Inventory"):
    table_df = df[[
        'incident_id', 'evidence_status', 'debris_type', 'footprint_m2',
        'vol_min_m3', 'vol_max_m3', 'mass_min_tons', 'mass_max_tons',
        'susceptibility_score', 'consequence_score', 'management_priority'
    ]].copy()
    
    table_df['Volume Range (m³)'] = table_df['vol_min_m3'].astype(str) + " – " + table_df['vol_max_m3'].astype(str)
    table_df['Mass Range (Tons)'] = table_df['mass_min_tons'].astype(str) + " – " + table_df['mass_max_tons'].astype(str)
    
    display_table = table_df[[
        'incident_id', 'evidence_status', 'debris_type', 'footprint_m2',
        'Volume Range (m³)', 'Mass Range (Tons)', 'susceptibility_score',
        'consequence_score', 'management_priority'
    ]]
    display_table.columns = [
        'Site ID', 'Evidence Status', 'Debris Class', 'Footprint (~m²)',
        'Est. Volume Range', 'Est. Mass Range', 'Susceptibility (0-100)',
        'Consequence (0-100)', 'Priority'
    ]
    
    st.dataframe(display_table, use_container_width=True)

# 5. Potential Management Interventions
with st.expander("🛠️ Potential Management Interventions (Decision-Support Recommendations)"):
    st.markdown("""
    Recommendations are tied directly to spatial risk scores and GIS infrastructure factors:

    * **High-Risk Vehicle Access Point (Post Oak Rd Terminus):**
      * *GIS Factor:* Paved-to-unpaved transition with documented turning radius.
      * *Action:* Evaluate feasibility of crash-rated perimeter swing gates or limestone boulder barriers.
    * **Repeated Dumping Hotspots:**
      * *GIS Factor:* DBSCAN clusters with high recency scores.
      * *Action:* Consider targeted, periodic mobile surveillance deployment rather than continuous static patrol.
    * **Low-Visibility Ingress Track:**
      * *GIS Factor:* Riparian tree canopy concealment with low ambient road lighting.
      * *Action:* Evaluate warning signage, solar deterrent lighting, and brush thinning along primary fence lines.
    * **Waste Connected to Active Drainage:**
      * *GIS Factor:* Piles situated within high flow-accumulation channels feeding the Trinity River.
      * *Action:* Prioritize abatement dispatch prior to forecasted USGS gauge stage increases.
    * **Recurring Scrap Tire Concentrations:**
      * *GIS Factor:* Repeated unpermitted scrap rubber deposits.
      * *Action:* Coordinate with local code compliance to audit regional commercial tire manifests.

    *Note: Implementation feasibility, jurisdictional authority, environmental permitting, and legal requirements must be reviewed and verified by responsible agencies prior to deployment.*
    """)

# 6. Methodology, Data Provenance & Framework
with st.expander("📚 Methodology, Data Provenance & Research Formulation"):
    st.markdown("""
    ### 1. Data Provenance & Sensor Integration
    * **Hydrological Ingestion:** USGS Water Services REST API (Station #08062500, Trinity River near Rosser, TX).
    * **Incident Distribution:** Simulated demonstration records parameterized against historical patterns from Dallas 311 service request open data.
    * **Cartographic Boundaries:** NCTCOG GIS regional parcel layers and OpenStreetMap road vector basemaps.

    ### 2. Waste Quantification Uncertainty
    Bulk conversions do not claim exact metric survey precision; instead, they represent bounded engineering ranges:
    * Passenger Scrap Tires: 0.009 to 0.012 metric tons/unit (~20–26 lbs/unit).
    * Construction & Demolition Rubble: 0.40 to 0.55 metric tons/m³.
    * Mixed Solid Waste & Bulky Furniture: 0.18 to 0.28 metric tons/m³.

    ### 3. Spatiotemporal Research Agenda (Hawkes Evaluation)
    To test whether self-exciting point processes provide predictive value over static GIS susceptibility models, ongoing work evaluates:
    * *Model A:* Historical spatial density baseline (Kernel Density Estimation).
    * *Model B:* Environmental and road accessibility susceptibility regression.
    * *Model C:* Spatiotemporal Hawkes self-excitation process ($w_i = \exp(-\beta \cdot \Delta t_i)$).
    * *Model D:* Integrated composite multi-criteria model.
    """)
