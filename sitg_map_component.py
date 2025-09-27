import json
import requests
import streamlit as st
from streamlit_folium import st_folium
import folium

# ------------------------------------------------------------
# SITG CADASTRE — Bâtiments hors-sol (polygons)
# ------------------------------------------------------------
SITG_BUILDINGS_QUERY = "https://thematic.sitg.ge.ch/arcgis/rest/services/CADASTRE/FeatureServer/47/query"

def fetch_buildings_by_egid(egids, chunk_size=900, timeout=20):
    """
    Fetch building polygons for the given EGID list from SITG (layer 47).
    Returns a GeoJSON FeatureCollection in WGS84 (EPSG:4326).
    - Handles IN-clause chunking (ArcGIS often caps ~1000 items per request).
    - Requests geometry + all attributes (you can trim outFields if you want).
    """
    
    egids_str=str(egids).replace('[','').replace(']','')

    if not egids:
        return {"type": "FeatureCollection", "features": []}

    features = []
    for i in range(0, len(egids), chunk_size):
        # chunk = egids[i:i+chunk_size]
        if not egids_str:
            continue
        where = f"EGID IN ({egids_str})"  # EGID is numeric in this layer
        params = {
            "f": "geojson",
            "where": where,
            "returnGeometry": "true",
            "outFields": "*",
            "inSR": 4326,
            "outSR": 4326,              # reproject to WGS84 for Leaflet
            "geometryPrecision": 6,     # smaller payload; adjust if you need more detail
        }
        r = requests.get(SITG_BUILDINGS_QUERY, params=params, timeout=timeout)
        r.raise_for_status()
        chunk_fc = r.json()
        features.extend(chunk_fc.get("features", []))

    return {"type": "FeatureCollection", "features": features}


def add_highlight_layer(m: folium.Map, feature_collection: dict, name="Selected buildings (EGID)"):
    """
    Add a red-highlight GeoJson layer (filled + stroked) to a Folium map.
    No popups/tooltips are attached.
    """
    style = {
        "color": "#8b0000",      # dark red outline
        "weight": 2,
        "fillColor": "#ff0000",  # red fill
        "fillOpacity": 0.45,
    }

    gj = folium.GeoJson(
        data=feature_collection,
        name=name,
        style_function=lambda _: style,
        zoom_on_click=False,   # keep current view
    )
    gj.add_to(m)
    return gj


# ------------------------------------------------------------
# Simple map: basemap + optional EGID highlight (NO popups)
# ------------------------------------------------------------
def render_sitg_map(egids=None):

    CENTER = [46.2044, 6.1432]
    WEBMERCATOR_BASEMAPS = {
        "OSM": "OpenStreetMap",
        "Esri Light Gray": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        "Esri Imagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    }
    basemap_choice = "OSM"

    if egids:
        # Base map
        m = folium.Map(location=CENTER, zoom_start=15, control_scale=True, prefer_canvas=True, tiles=None)
        bm = WEBMERCATOR_BASEMAPS[basemap_choice]
        if bm == "OpenStreetMap":
            folium.TileLayer(bm, name="OSM", overlay=False).add_to(m)
        else:
            folium.TileLayer(tiles=bm, attr="© Esri", name=basemap_choice, overlay=False).add_to(m)

        # If EGIDs provided, fetch and highlight (no popup)
        if egids:
            with st.spinner("Fetching buildings by EGID…"):
                fc = fetch_buildings_by_egid(egids)

            if not fc["features"]:
                st.warning("No buildings found for the provided EGID(s).")
            else:
                add_highlight_layer(m, fc, name="Selected buildings (EGID)")
                folium.LayerControl(collapsed=False).add_to(m)
        st_folium(m, width="100%", height=650, key="map_egid")
