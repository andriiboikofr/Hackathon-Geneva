
from app import go, topbar
import streamlit as st

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
