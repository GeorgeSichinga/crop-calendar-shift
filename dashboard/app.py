"""
dashboard/app.py
-----------------
Interactive Streamlit dashboard for the Crop Calendar Climate Shift Analyser.
Visualises onset-of-rains trends, shift magnitudes, and ENSO impacts
across Malawi's 28 districts.

Run:
    streamlit run dashboard/app.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Malawi Crop Calendar Shift",
    page_icon="🌧️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stMetricValue"]  { font-size: 1.6rem; font-weight: 600; }
  [data-testid="stMetricLabel"]  { font-size: 0.82rem; color: #666; }
  .block-container               { padding-top: 1.5rem; }
  h1                             { font-weight: 700; letter-spacing: -0.5px; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    oor_path    = Path("data/processed/oor_for_r.csv")
    trends_path = Path("outputs/tables/district_trends.csv")

    if not oor_path.exists():
        st.error("No data found. Run: `python scripts/python/03_export_for_r.py --synthetic`")
        st.stop()

    df = pd.read_csv(oor_path)
    df["region"] = df["region"].astype("category")

    trends = pd.read_csv(trends_path) if trends_path.exists() else None
    return df, trends


df, trends = load_data()

# ── ENSO years ────────────────────────────────────────────────────────────────
EL_NINO = {1991, 1994, 1997, 2002, 2004, 2009, 2015, 2018, 2023}
LA_NINA = {1995, 1998, 1999, 2000, 2007, 2010, 2011, 2020, 2021}

REGION_COLORS = {
    "Northern":  "#1D9E75",
    "Central":   "#378ADD",
    "Southern":  "#D85A30",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Flag_of_Malawi.svg/240px-Flag_of_Malawi.svg.png",
             width=120)
    st.markdown("## Crop Calendar Shift")
    st.caption("Malawi · 1990–2024")
    st.divider()

    regions = st.multiselect(
        "Regions",
        options=["Northern", "Central", "Southern"],
        default=["Northern", "Central", "Southern"],
    )
    all_districts = sorted(df[df["region"].isin(regions)]["district"].unique())
    selected_districts = st.multiselect(
        "Districts (optional filter)",
        options=all_districts,
        default=[],
        placeholder="All districts",
    )
    year_range = st.slider("Season range", 1990, 2023, (1990, 2023))
    show_enso  = st.toggle("Highlight ENSO events", value=True)
    st.divider()
    st.caption("George Sichinga · LUANAR · MSc Applied Data Science")

# ── Filter data ───────────────────────────────────────────────────────────────
mask = (
    df["region"].isin(regions) &
    df["season_start"].between(*year_range) &
    df["oor_doy"].notna()
)
if selected_districts:
    mask &= df["district"].isin(selected_districts)
dff = df[mask].copy()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🌧️ Has Malawi's planting season shifted?")
st.caption("Onset-of-rains (OOR) analysis using CHIRPS v2.0 · 1990–2024")

# ── KPI metrics ───────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

if trends is not None:
    tr = trends[trends["region"].isin(regions)]
    mean_shift = tr["shift_per_decade"].mean()
    n_sig      = tr["significant_mk"].sum()
    pct_delayed = (tr["sens_slope_days_per_year"] > 0).mean() * 100
    mean_oor   = tr["mean_oor_doy"].mean()
else:
    mean_shift  = dff.groupby("district")["oor_doy"].apply(
        lambda x: np.polyfit(range(len(x)), x.values, 1)[0] * 10
    ).mean()
    n_sig, pct_delayed, mean_oor = "—", "—", dff["oor_doy"].mean()

col1.metric("Mean OOR shift / decade",
            f"{mean_shift:+.1f} days" if isinstance(mean_shift, float) else mean_shift,
            "later onset trend" if isinstance(mean_shift, float) and mean_shift > 0 else "earlier onset")
col2.metric("Significant districts", f"{n_sig}" if isinstance(n_sig, int) else n_sig,
            "Mann-Kendall p < 0.05")
col3.metric("Districts with delayed onset",
            f"{pct_delayed:.0f}%" if isinstance(pct_delayed, float) else pct_delayed)
# Show mean OOR as a single readable value e.g. "Day 320 (Nov 15)"
if isinstance(mean_oor, float):
    mean_oor_date = (pd.Timestamp("2000-01-01") + pd.Timedelta(days=int(mean_oor) - 1)).strftime("%b %d")
    mean_oor_display = f"Day {mean_oor:.0f} ({mean_oor_date})"
else:
    mean_oor_display = mean_oor
col4.metric("Mean OOR (all)", mean_oor_display)

st.divider()

# ── Main charts ───────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📈 Time series", "🗺️ District map", "📦 Decade shifts", "📊 Trend table"])

# ── Tab 1: Time series ────────────────────────────────────────────────────────
with tab1:
    st.subheader("Regional onset-of-rains over time")

    regional_ts = (
        dff.groupby(["region", "season_start"])["oor_doy"]
        .mean().reset_index()
    )

    fig = px.line(
        regional_ts,
        x="season_start", y="oor_doy",
        color="region",
        color_discrete_map=REGION_COLORS,
        markers=True,
        labels={"season_start": "Season start year", "oor_doy": "Onset of rains (DOY)", "region": "Region"},
        height=420,
    )

    # Add trendlines
    for region, grp in regional_ts.groupby("region"):
        z = np.polyfit(grp["season_start"], grp["oor_doy"], 1)
        trend_y = np.poly1d(z)(grp["season_start"])
        fig.add_scatter(
            x=grp["season_start"], y=trend_y,
            mode="lines", name=f"{region} trend",
            line=dict(dash="dash", color=REGION_COLORS.get(region, "grey"), width=1.5),
            showlegend=False,
        )

    # ENSO shading
    if show_enso:
        for yr in EL_NINO:
            if year_range[0] <= yr <= year_range[1]:
                fig.add_vrect(x0=yr-0.4, x1=yr+0.4, fillcolor="#E24B4A", opacity=0.12,
                              line_width=0, annotation_text="" )
        for yr in LA_NINA:
            if year_range[0] <= yr <= year_range[1]:
                fig.add_vrect(x0=yr-0.4, x1=yr+0.4, fillcolor="#378ADD", opacity=0.12,
                              line_width=0)
        fig.add_annotation(x=year_range[0]+1, y=regional_ts["oor_doy"].max()+1,
                           text="🔴 El Niño  🔵 La Niña", showarrow=False,
                           font=dict(size=10, color="grey"))

    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        font_family="sans-serif",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
        margin=dict(l=40, r=20, t=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # District-level detail
    if selected_districts:
        st.subheader("Selected district timeseries")
        dist_ts = dff[dff["district"].isin(selected_districts)]
        fig_d = px.line(dist_ts, x="season_start", y="oor_doy",
                        color="district", markers=True, height=300,
                        labels={"season_start": "Year", "oor_doy": "OOR (DOY)"})
        fig_d.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                             margin=dict(l=40, r=20, t=20, b=40))
        st.plotly_chart(fig_d, use_container_width=True)

# ── Tab 2: Choropleth ─────────────────────────────────────────────────────────
with tab2:
    if trends is not None:
        st.subheader("Total OOR shift by district (1990–2024)")
        fig_map = px.choropleth(
            trends[trends["region"].isin(regions)],
            locations="district",
            locationmode="country names",
            color="total_shift_days",
            color_continuous_scale="RdBu_r",
            color_continuous_midpoint=0,
            hover_data=["region", "mean_oor_doy", "shift_per_decade", "mk_p_value"],
            labels={"total_shift_days": "Total shift (days)"},
            height=500,
        )
        fig_map.update_layout(
            geo=dict(scope="africa", fitbounds="locations", bgcolor="white"),
            margin=dict(l=0, r=0, t=0, b=0),
        )
        st.plotly_chart(fig_map, use_container_width=True)
        st.caption("Note: Choropleth uses country-name matching — for full district-level spatial mapping, render fig2 from the R script.")
    else:
        st.info("Run `Rscript scripts/r/04_trend_analysis.R` to generate district trend data, then reload.")

# ── Tab 3: Decade boxplot ─────────────────────────────────────────────────────
with tab3:
    st.subheader("OOR distribution by decade and region")
    df_dec = dff.copy()
    df_dec["decade"] = (df_dec["season_start"] // 10 * 10).astype(str) + "s"
    fig_box = px.box(
        df_dec, x="decade", y="oor_doy",
        color="region", color_discrete_map=REGION_COLORS,
        facet_col="region",
        labels={"decade": "Decade", "oor_doy": "Onset of rains (DOY)"},
        height=380,
    )
    fig_box.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        showlegend=False,
        margin=dict(l=40, r=20, t=30, b=40),
    )
    st.plotly_chart(fig_box, use_container_width=True)

# ── Tab 4: Trend table ────────────────────────────────────────────────────────
with tab4:
    if trends is not None:
        st.subheader("District-level trend statistics")
        show_df = trends[trends["region"].isin(regions)].copy()
        show_df["significant_mk"] = show_df["significant_mk"].map({True: "✅", False: "—"})

        st.dataframe(
            show_df[[
                "district", "region", "mean_oor_date",
                "shift_per_decade", "total_shift_days",
                "sens_slope_days_per_year", "mk_p_value", "significant_mk",
                "n_seasons"
            ]].sort_values("total_shift_days", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "district":                 st.column_config.TextColumn("District"),
                "region":                   st.column_config.TextColumn("Region"),
                "mean_oor_date":            st.column_config.TextColumn("Mean OOR date"),
                "shift_per_decade":         st.column_config.NumberColumn("Shift/decade (days)", format="%.2f"),
                "total_shift_days":         st.column_config.NumberColumn("Total shift (days)", format="%.1f"),
                "sens_slope_days_per_year": st.column_config.NumberColumn("Sen's slope (days/yr)", format="%.3f"),
                "mk_p_value":               st.column_config.NumberColumn("MK p-value", format="%.4f"),
                "significant_mk":           st.column_config.TextColumn("Significant"),
                "n_seasons":                st.column_config.NumberColumn("N seasons"),
            }
        )
        csv = show_df.to_csv(index=False).encode()
        st.download_button("⬇️ Download as CSV", csv, "district_trends.csv", "text/csv")
    else:
        st.info("Run `Rscript scripts/r/04_trend_analysis.R` first.")
