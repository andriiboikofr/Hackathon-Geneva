# streamlit_app.py
import streamlit as st
from streamlit_folium import st_folium
import folium

# --- SITG basemaps ---
SITG_PLAN = "https://ge.ch/sitgags2/rest/services/RASTER/PLAN_SITG/MapServer/tile/{z}/{y}/{x}"
SITG_ORTO = "https://ge.ch/sitgags2/rest/services/RASTER/ORTHOPHOTOS_HAUTE_RESOLUTION/MapServer/tile/{z}/{y}/{x}"

# --- Center Geneva ---
CENTER = [46.2044, 6.1432]  # roughly city center

st.set_page_config(page_title="Geneva Base Map (Leaflet)", layout="wide")
st.title("🗺️ Geneva — SITG Basemap Viewer (Leaflet)")
st.caption("Fast Geneva map with SITG official basemap. No overlays yet.")

# Sidebar controls
with st.sidebar:
    st.header("🧭 Map Settings")
    basemap_choice = st.selectbox(
        "Basemap type",
        ["Plan SITG (map)", "Ortho (satellite)"],
        index=0,
    )
    zoom = st.slider("Zoom level", 8, 19, 13)
    st.markdown("Next step ➜ overlay specific building polygons (≤50).")

# --- Create Leaflet map ---
m = folium.Map(
    location=CENTER,
    zoom_start=zoom,
    control_scale=True,
    prefer_canvas=True,
    tiles=None,
)

# --- Add basemap layer ---
if "Plan" in basemap_choice:
    folium.raster_layers.TileLayer(
        tiles=SITG_PLAN,
        attr="© SITG | Plan SITG",
        name="Plan SITG",
        overlay=False,
    ).add_to(m)
else:
    folium.raster_layers.TileLayer(
        tiles=SITG_ORTO,
        attr="© SITG | Orthophotos HR",
        name="Orthophotos HR",
        overlay=False,
    ).add_to(m)

# Add layer switcher
folium.LayerControl().add_to(m)

# Display map
st_data = st_folium(m, width="100%", height=700)

with st.expander("ℹ️ Info"):
    st.markdown(
        """
        - Data source: [SITG (Système d'information du territoire à Genève)](https://ge.ch/sitg/)
        - Basemap layers:
            - **Plan SITG** — detailed map (streets, parcels, labels)
            - **Orthophotos HR** — high-res aerial imagery
        - Currently rendering **only the base map** for performance.
        - Ready to accept **≤50 custom overlays** (buildings, zones, etc.).
        """
    )
