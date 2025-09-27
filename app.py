# streamlit_app.py
import streamlit as st
from streamlit_folium import st_folium
import folium

# --- App setup
st.set_page_config(page_title="Geneva Map + Hidden Report", layout="wide")

# --- Simple router: session_state + optional URL param
# --- Simple router: session_state + optional URL param
if "route" not in st.session_state:
    # Read initial route from ?page=...
    st.session_state.route = st.query_params.get("page", "map")

def go(route: str):
    # Update state + URL, then rerun
    st.session_state.route = route
    st.query_params["page"] = route
    st.rerun()


# --- Common UI elements (top bar)
def topbar(title: str, show_report_button: bool = True):
    left, right = st.columns([4, 1])
    with left:
        st.title(title)
    with right:
        if show_report_button:
            st.write("")  # spacing
            if st.button("📝 Report generation", use_container_width=True):
                go("report")

# --- PAGE 1: Map (regular Geneva basemap, no overlays)
def render_map_page():
    topbar("🗺️ Geneva — SITG Basemap Viewer", show_report_button=True)

    # Basemap selection without using the sidebar
    st.subheader("Basemap")
    col1, col2 = st.columns(2)
    with col1:
        basemap_choice = st.selectbox("Choose basemap:",
                                      ["Plan SITG (map)", "Orthophotos HR (satellite)"],
                                      index=0)
    with col2:
        zoom = st.slider("Zoom level", 8, 19, 13)

    CENTER = [46.2044, 6.1432]
    SITG_PLAN = "https://ge.ch/sitgags2/rest/services/RASTER/PLAN_SITG/MapServer/tile/{z}/{y}/{x}"
    SITG_ORTO = "https://ge.ch/sitgags2/rest/services/RASTER/ORTHOPHOTOS_HAUTE_RESOLUTION/MapServer/tile/{z}/{y}/{x}"

    m = folium.Map(location=CENTER, zoom_start=zoom, control_scale=True, prefer_canvas=True, tiles=None)

    if "Plan" in basemap_choice:
        folium.raster_layers.TileLayer(
            tiles=SITG_PLAN, attr="© SITG | Plan SITG", name="Plan SITG", overlay=False
        ).add_to(m)
    else:
        folium.raster_layers.TileLayer(
            tiles=SITG_ORTO, attr="© SITG | Orthophotos HR", name="Orthophotos HR", overlay=False
        ).add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, width="100%", height=700)

    with st.expander("ℹ️ Info"):
        st.markdown(
            "- Data source: **SITG** (Système d'information du territoire à Genève)\n"
            "- This page shows only the **basemap** (fast). "
            "Next step: add up to **50 overlays** on demand."
        )

# --- PAGE 2: Hidden Report Generation (no sidebar entry)
def render_report_page():
    topbar("📝 Report generation", show_report_button=False)

    st.caption("This page is intentionally hidden from the sidebar. Access via the button or `?page=report`.")
    st.subheader("Parameters")
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Report title", value="Geneva Mapping Report")
        author = st.text_input("Author", value="Team")
    with col2:
        include_map = st.checkbox("Include current map screenshot (placeholder)", value=True)
        include_stats = st.checkbox("Include building stats (placeholder)", value=True)

    st.subheader("Generate")
    if st.button("Build report"):
        st.success("Report generated (placeholder). Plug in your real export logic here (PDF/HTML/Docx).")

    st.divider()
    if st.button("← Back to map"):
        go("map")

# --- Route
if st.session_state.route == "report":
    render_report_page()
else:
    render_map_page()
