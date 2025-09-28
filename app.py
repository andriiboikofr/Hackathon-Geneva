# streamlit_app.py

import numpy as np
import streamlit as st
import datetime as dt
import pandas as pd
import report_page
import didier_page
from sitg_map_component import render_sitg_map
import ast
import seaborn as sns
import matplotlib.pyplot as plt

sns.set_theme(style="whitegrid")
sns.set_context("talk", font_scale=0.9)
sns.set_palette(sns.color_palette(["#2ecc71"]))


# --- App setup
st.set_page_config(page_title="Geneva Map + Hidden Report", layout="wide")
buildings = pd.read_csv('data/buildings_cleaned.csv')
general_data=pd.read_excel('data/data_raw.xlsx', sheet_name='Clean_Data')

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
            if st.button("📝 Report generation", use_container_width=True,disabled='industry' in st.session_state.keys() and st.session_state['industry']=='None'):

                # Create a string with session state values
                session_data = "\n".join([f"{key}: {value}" for key, value in st.session_state.items()])

                # Optional: Add a timestamp
                session_data = f"\n{session_data}"
                print(session_data)
                # Save to a .txt file
                with open("report_session_data.txt", "w") as f:
                    f.write(session_data)
                go("report")


# --- PAGE 1: Map (regular Geneva basemap, no overlays)
def render_map_page():
    topbar("🗺️ Geneva — SITG Basemap Viewer", show_report_button=True)

    # ---- Inputs: industry / organization
    st.subheader("Scenario inputs")
    col1, col2 = st.columns(2)

    # industry selector (+ "None" meaning: all industries)
    industries = sorted(buildings["category"].dropna().unique().tolist())
    industry_options = industries + ["None"]
    with col1:
        st.session_state["industry"] = st.selectbox(
            "Select industry",
            options=industry_options,
            index=0 if industries else len(industry_options) - 1,
            key="selected_industry",
        )

    # organization selector, only populated when an industry (not "None") is selected
    if st.session_state["industry"] != "None":
        org_options = (
            buildings.loc[buildings["category"] == st.session_state["industry"], "nom"]
            .dropna()
            .unique()
            .tolist()
        )
    else:
        org_options = []  # no specific industry -> no org list

    # Make sure selectbox has at least one safe option
    safe_org_options = org_options if org_options else ["(no organization)"]

    with col2:
        st.session_state["organization"] = st.selectbox(
            "Select Organization",
            options=safe_org_options,
            index=0,
            key="selected_organization",
            disabled=(st.session_state["industry"] == "None"),
        )
        # Normalize the "no org" sentinel to None
        if st.session_state["organization"] == "(no organization)":
            st.session_state["organization"] = None

    # ---- Other inputs
    st.subheader("Scenario inputs")
    col1, col2 = st.columns(2)

    with col1:
        st.session_state["reduction_supply"] = st.selectbox(
            "Select energy reduction supply target in %",
            options=[10, 20, 30],
            index=2,
            key="selected_reduction_supply",
        )

    with col2:
        today = dt.date.today()
        default_start = today - dt.timedelta(days=6)
        default_end = today
        min_date = today - dt.timedelta(days=365 * 2)
        max_date = today + dt.timedelta(days=365)

        date_sel = st.date_input(
            "Select date range",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=max_date,
            help="Pick start and end dates (no time).",
        )

        if isinstance(date_sel, tuple) and len(date_sel) == 2:
            st.session_state["reduction_start"], st.session_state["reduction_end"] = date_sel
        else:
            st.session_state["reduction_start"] = st.session_state["reduction_end"] = date_sel

        # Safety fallback
        if not all(isinstance(d, dt.date) for d in (st.session_state["reduction_start"], st.session_state["reduction_end"])):
            st.session_state["reduction_start"], st.session_state["reduction_end"] = default_start, default_end

        if st.session_state["reduction_start"] > st.session_state["reduction_end"]:
            st.error("Start date cannot be after end date.")
            st.stop()

    # ---- Build org_data depending on selections
    # Clean year to int if needed (e.g., "2,023" -> 2023)
    def _to_year(x):
        try:
            return int(str(x).replace(",", "").strip())
        except Exception:
            return np.nan

    gdf = general_data.copy()
    gdf["annee"] = gdf["annee"].map(_to_year)
    # Coerce energy columns to numeric (handle stray commas)
    for col in ["kwh_electrique", "kwh_gaz", "kwh_cad", "kwh_mazout"]:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col].astype(str).str.replace(",", "", regex=False), errors="coerce")

    org = st.session_state.get("organization")
    ind = st.session_state.get("industry")

    if org:  # organization chosen -> use that org’s rows directly
        org_data = gdf[gdf["nom"] == org].copy()
    else:
        if ind and ind != "None":  # no org, but industry chosen -> aggregate within that industry
            org_data = (
                gdf[gdf["category"] == ind]
                .groupby("annee", as_index=False)
                .sum(numeric_only=True)
            )
        else:  # neither org nor specific industry -> aggregate across all industries
            org_data = gdf.groupby("annee", as_index=False).sum(numeric_only=True)

    # ---- Charts
    st.title("📈 Energy Trends")
    col1, col2 = st.columns(2)

    def add_pct_deviation(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        out = df.copy()
        for c in cols:
            if c in out.columns and out[c].notna().any():
                m = out[c].mean(skipna=True)
                if pd.notna(m) and m != 0:
                    out[f"{c}_pct"] = (out[c] / m - 1.0) * 100.0
                else:
                    out[f"{c}_pct"] = np.nan
        return out

    org_data = add_pct_deviation(
        org_data,
        cols=["kwh_electrique", "kwh_gaz", "kwh_cad", "kwh_mazout"]
    )

    years = sorted(org_data["annee"].dropna().unique().tolist())
    if not years:
        st.warning("No data to plot.")
        return

    # ===== Left chart: Electricity % deviation =====
    with col1:
        fig1, ax1 = plt.subplots(figsize=(10, 3))
        if "kwh_electrique_pct" in org_data.columns:
            sns.lineplot(
                data=org_data,
                x="annee", y="kwh_electrique_pct",
                linewidth=1.5, ax=ax1, color="#2ecc71"
            )
            ax1.axhline(0, ls="--", lw=1, color="#999")
            lo, hi = org_data["kwh_electrique_pct"].min(), org_data["kwh_electrique_pct"].max()
            span = max(abs(lo), abs(hi))
            ax1.set_ylim(-span * 1.1, span * 1.1)

        ax1.set_title("Electricity: % vs 4-year avg", fontsize=12, color="#2ecc71")
        ax1.set_xlabel("Year", fontsize=10)
        ax1.set_ylabel("% deviation", fontsize=10)
        ax1.set(xticks=years)
        sns.despine(ax=ax1)
        st.pyplot(fig1, clear_figure=True, use_container_width=True)

    # ===== Right chart: Fuels/Heat % deviation =====
    with col2:
        fig2, ax2 = plt.subplots(figsize=(10, 3))

        plotted = False
        for col, color, label in [
            ("kwh_gaz_pct", "#2ecc71", "Gaz"),
            ("kwh_cad_pct", "#9acc2e", "Cad"),
            ("kwh_mazout_pct", "#3e64d7", "Mazout"),
        ]:
            if col in org_data.columns:
                sns.lineplot(data=org_data, x="annee", y=col,
                             linewidth=2, ax=ax2, color=color, label=label)
                plotted = True

        if plotted:
            ax2.axhline(0, ls="--", lw=1, color="#999")
            vals = []
            for c in ["kwh_gaz_pct", "kwh_cad_pct", "kwh_mazout_pct"]:
                if c in org_data.columns and org_data[c].notna().any():
                    vals += org_data[c].tolist()
            if vals:
                lo, hi = np.nanmin(vals), np.nanmax(vals)
                span = max(abs(lo), abs(hi))
                ax2.set_ylim(-span * 1.1, span * 1.1)

        ax2.set_title("Fuels/Heat: % vs 4-year avg", fontsize=12, color="#2ecc71")
        ax2.set_xlabel("Year", fontsize=10)
        ax2.set_ylabel("% deviation", fontsize=10)
        ax2.set(xticks=years)
        if plotted:
            ax2.legend(frameon=False, fontsize=8)
        sns.despine(ax=ax2)
        st.pyplot(fig2, clear_figure=True, use_container_width=True)

    # ---- Basemap
    st.subheader("Basemap")
    # Collect EGIDs depending on selection
    def _flatten_egids(series):
        """Series holds strings like '[2037603, 295147434]'; return flat list of ints."""
        out = []
        for v in series.dropna().tolist():
            try:
                lst = v if isinstance(v, list) else ast.literal_eval(str(v))
                out.extend(int(x) for x in lst)
            except Exception:
                continue
        # dedupe, preserve order
        return list(dict.fromkeys(out))

    if org:  # plot buildings for selected organization
        egids = _flatten_egids(buildings.loc[buildings["nom"] == org, "EGIDs"])
        render_sitg_map(egids)
    else:
        if ind and ind != "None":  # all buildings in the chosen industry
            egids = _flatten_egids(buildings.loc[buildings["category"] == ind, "EGIDs"])
        else:  # no industry -> all buildings
            egids = _flatten_egids(buildings["EGIDs"])
        render_sitg_map(egids)

import didier_page

if st.session_state.route == "report":
    report_page.render()
else:
    render_map_page()

