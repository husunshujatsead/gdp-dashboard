"""
SADAFCO Online Shopping — Sales Dashboard
==========================================
A Streamlit app that ingests the Online Shopping report and reproduces the
"Platform Wise Sales" and "Platform-Category Wise Sales" pivot tables from
the SADAFCO Sales Tracking workbook, with McKinsey-style visualizations.

Run:
    pip install streamlit pandas plotly openpyxl
    streamlit run sadafco_dashboard.py
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config & global styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SADAFCO Online Shopping Dashboard",
    page_icon="📊",
    layout="wide",
)

# McKinsey-inspired palette: deep navy, muted blues, warm accent
MCK_NAVY = "#051C2C"
MCK_BLUE = "#034B6F"
MCK_TEAL = "#00A9E0"
MCK_LIGHT = "#AAE6FA"
MCK_GREY = "#E6E6E6"
MCK_ACCENT = "#E5B611"
MCK_PALETTE = [
    "#051C2C", "#034B6F", "#00A9E0", "#2DCCD3", "#AAE6FA",
    "#E5B611", "#B08B00", "#7A8C99", "#C1CDD6", "#3F5161",
]

st.markdown(
    """
    <style>
        .main > div { padding-top: 1rem; }
        h1, h2, h3 { color: #051C2C; font-family: 'Helvetica Neue', sans-serif; }
        .stMetric { background: #F7F9FB; padding: 12px; border-left: 4px solid #00A9E0; border-radius: 4px; }
        [data-testid="stMetricValue"] { color: #051C2C; font-size: 1.6rem; }
        .block-container { padding-top: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Map raw "Categroy" values to the cleaner labels used in the SADAFCO pivot.
CATEGORY_MAP = {
    "CULINARY": "Culinary",
    "DAIRY": "Dairy",
    "NON-DAIRY DRINKS": "Drinks",
    "SNACKS": "Snacks",
    "ICE CREAM": "Frozen",
    "FROZEN FOOD": "Frozen",
}

# Ordered so longer / more specific keywords match first.
PLATFORM_PATTERNS: list[tuple[str, str]] = [
    ("Hungerstation", r"hunger\s*station"),
    ("Ninja",         r"\bninja\b"),
    ("Noon",          r"\bnoon\b"),
    ("Amazon",        r"\bamazon\b"),
    ("Nana",          r"\bnana\b"),
    ("Keeta",         r"\bkeeta\b"),
    ("Careem",        r"\bcareem\b"),
    ("Doosaha",       r"\bdoosaha\b"),
    ("Rabbit",        r"\brabbit\b"),
    ("To you",        r"\bto\s*you\b"),
    ("Breadfast",     r"\bbreadfast\b"),
]


# ---------------------------------------------------------------------------
# Data loading & shaping
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading sales data…")
def load_data(source) -> pd.DataFrame:
    """Read the Online Shopping workbook and return a tidy DataFrame."""
    df = pd.read_excel(source, sheet_name=0)

    df = df.rename(columns={
        "Categroy": "Category_Raw",
        "Gross Sales Amount": "Sales Val",
    })

    df["Category"] = df["Category_Raw"].map(CATEGORY_MAP).fillna(df["Category_Raw"])
    df["Platform"] = _extract_platform(df["CustomerName"])
    df["Month_Name"] = pd.Categorical(
        pd.to_datetime(df["Month"], format="%m").dt.strftime("%b"),
        categories=MONTH_ORDER,
        ordered=True,
    )
    df["Sales Val"] = pd.to_numeric(df["Sales Val"], errors="coerce").fillna(0.0)
    df["Sales Qty"] = pd.to_numeric(df["Sales Qty"], errors="coerce").fillna(0.0)
    return df


def _extract_platform(series: pd.Series) -> pd.Series:
    """Map a CustomerName free-text column to a platform label."""
    names = series.astype(str).str.lower()
    out = pd.Series("Other", index=series.index, dtype="object")
    for label, pattern in PLATFORM_PATTERNS:
        mask = names.str.contains(pattern, regex=True, na=False) & (out == "Other")
        out.loc[mask] = label
    return out


def build_platform_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Replicates 'Platform Wise Sales' — Platform x Month, sum of Sales Val."""
    pivot = (
        df.pivot_table(
            index="Platform",
            columns="Month_Name",
            values="Sales Val",
            aggfunc="sum",
            fill_value=0,
            observed=False,
        )
        .reindex(columns=MONTH_ORDER, fill_value=0)
    )
    pivot.loc["Grand Total"] = pivot.sum(axis=0)
    pivot["Grand Total"] = pivot.sum(axis=1)
    return pivot


def build_platform_category_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Replicates 'Platform-Category Wise Sales' — nested Platform/Category x Month."""
    pivot = (
        df.pivot_table(
            index=["Platform", "Category"],
            columns="Month_Name",
            values="Sales Val",
            aggfunc="sum",
            fill_value=0,
            observed=False,
        )
        .reindex(columns=MONTH_ORDER, fill_value=0)
    )
    pivot["Grand Total"] = pivot.sum(axis=1)
    return pivot


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def fmt_money(x: float) -> str:
    if pd.isna(x) or x == 0:
        return "—"
    if abs(x) >= 1e6:
        return f"{x/1e6:,.2f}M"
    if abs(x) >= 1e3:
        return f"{x/1e3:,.1f}K"
    return f"{x:,.0f}"


def style_pivot(pivot: pd.DataFrame):
    return (
        pivot.style
        .format(fmt_money)
        .background_gradient(cmap="Blues", axis=None,
                             subset=pd.IndexSlice[:, [c for c in pivot.columns if c != "Grand Total"]])
        .set_properties(**{"text-align": "right", "font-size": "12px"})
        .set_table_styles([
            {"selector": "th", "props": [("background-color", MCK_NAVY),
                                          ("color", "white"),
                                          ("font-weight", "600"),
                                          ("text-align", "center")]},
        ])
    )


# ---------------------------------------------------------------------------
# Charts (McKinsey style)
# ---------------------------------------------------------------------------
def _mck_layout(fig: go.Figure, title: str, height: int = 420) -> go.Figure:
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=18, color=MCK_NAVY), x=0.0, xanchor="left"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Helvetica Neue, Arial", size=12, color=MCK_NAVY),
        height=height,
        margin=dict(l=60, r=30, t=70, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, x=0),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    fig.update_xaxes(showgrid=False, linecolor=MCK_GREY, ticks="outside", tickcolor=MCK_GREY)
    fig.update_yaxes(showgrid=True, gridcolor=MCK_GREY, zeroline=False)
    return fig


def chart_platform_trend(df: pd.DataFrame) -> go.Figure:
    monthly = (
        df.groupby(["Platform", "Month_Name"], observed=True)["Sales Val"]
        .sum()
        .reset_index()
    )
    top_platforms = (
        monthly.groupby("Platform")["Sales Val"].sum()
        .sort_values(ascending=False).head(6).index.tolist()
    )
    monthly = monthly[monthly["Platform"].isin(top_platforms)]
    monthly["Month_Name"] = pd.Categorical(monthly["Month_Name"], MONTH_ORDER, ordered=True)
    monthly = monthly.sort_values("Month_Name")

    fig = px.line(
        monthly, x="Month_Name", y="Sales Val", color="Platform",
        markers=True, color_discrete_sequence=MCK_PALETTE,
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=8))
    return _mck_layout(fig, "Monthly sales trend — top 6 platforms", height=440)


def chart_platform_share(df: pd.DataFrame) -> go.Figure:
    totals = (df.groupby("Platform")["Sales Val"].sum()
                .sort_values(ascending=True))
    fig = go.Figure(go.Bar(
        x=totals.values, y=totals.index, orientation="h",
        marker=dict(color=totals.values, colorscale=[[0, MCK_LIGHT], [1, MCK_NAVY]]),
        text=[fmt_money(v) for v in totals.values],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Sales: %{text}<extra></extra>",
    ))
    fig.update_xaxes(title_text="Total sales value (SAR)")
    return _mck_layout(fig, "Total sales by platform", height=max(360, 28 * len(totals) + 120))


def chart_category_stack(df: pd.DataFrame) -> go.Figure:
    pc = (df.groupby(["Platform", "Category"], observed=True)["Sales Val"]
            .sum().reset_index())
    platform_order = (pc.groupby("Platform")["Sales Val"].sum()
                        .sort_values(ascending=False).index.tolist())
    pc["Platform"] = pd.Categorical(pc["Platform"], platform_order, ordered=True)
    pc = pc.sort_values("Platform")

    fig = px.bar(
        pc, x="Platform", y="Sales Val", color="Category",
        color_discrete_sequence=MCK_PALETTE,
    )
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="Sales value (SAR)")
    fig.update_xaxes(title_text="")
    return _mck_layout(fig, "Category mix by platform", height=460)


def chart_heatmap(pivot: pd.DataFrame) -> go.Figure:
    data = pivot.drop(index="Grand Total", errors="ignore") \
                .drop(columns="Grand Total", errors="ignore")
    fig = go.Figure(go.Heatmap(
        z=data.values, x=data.columns.tolist(), y=data.index.tolist(),
        colorscale=[[0, "#FFFFFF"], [0.5, MCK_TEAL], [1, MCK_NAVY]],
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:,.0f}<extra></extra>",
        colorbar=dict(title="SAR"),
    ))
    return _mck_layout(fig, "Sales intensity — platform × month", height=480)


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------
st.title("SADAFCO Online Shopping — Sales Dashboard")
st.caption("Platform-wise & Platform-Category sales pivots, replicated from the SADAFCO tracker.")

# --- Sidebar: data source & filters --------------------------------------
with st.sidebar:
    st.header("⚙︎ Data & Filters")
    #uploaded = st.file_uploader("Upload Online Shopping workbook (.xlsx)", type=["xlsx"])
    default_path = Path("Online Shopping 24-26 (1).xlsx")
    #if uploaded is not None:
    #     data_source = uploaded
    if default_path.exists():
        data_source = default_path
        st.info(f"Using default file: `{default_path.name}`")
    else:
        st.warning("Please upload the Online Shopping .xlsx file to begin.")
        st.stop()

df = load_data(data_source)

with st.sidebar:
    years = sorted(df["Year"].unique().tolist())
    year_sel = st.selectbox("Year", years, index=len(years) - 1)
    types = sorted(df["Type"].dropna().unique().tolist())
    type_sel = st.multiselect("Type", types, default=types)
    platforms_all = sorted(df["Platform"].unique().tolist())
    plat_sel = st.multiselect("Platforms", platforms_all, default=platforms_all)

mask = (df["Year"] == year_sel) & (df["Type"].isin(type_sel)) & (df["Platform"].isin(plat_sel))
fdf = df.loc[mask].copy()

if fdf.empty:
    st.error("No rows match the current filters.")
    st.stop()

# --- KPI strip ------------------------------------------------------------
total_sales = fdf["Sales Val"].sum()
total_qty = fdf["Sales Qty"].sum()
n_platforms = fdf["Platform"].nunique()
n_skus = fdf["SKU"].nunique()
top_platform = fdf.groupby("Platform")["Sales Val"].sum().idxmax()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total sales (SAR)", fmt_money(total_sales))
c2.metric("Units sold", fmt_money(total_qty))
c3.metric("Platforms", f"{n_platforms}")
c4.metric("Active SKUs", f"{n_skus:,}")
c5.metric("Top platform", top_platform)

st.divider()

# --- Charts row -----------------------------------------------------------
left, right = st.columns([1.3, 1])
with left:
    st.plotly_chart(chart_platform_trend(fdf), use_container_width=True)
with right:
    st.plotly_chart(chart_platform_share(fdf), use_container_width=True)

st.plotly_chart(chart_category_stack(fdf), use_container_width=True)

st.divider()

# --- Pivot 1: Platform Wise Sales ----------------------------------------
st.subheader(f"Platform Wise Sales — {year_sel}")
st.caption("Sum of Sales Val by Platform × Month")

p1_platforms = sorted(fdf["Platform"].unique().tolist())
p1_categories = sorted(fdf["Category"].dropna().unique().tolist())

p1c1, p1c2 = st.columns(2)
with p1c1:
    p1_plat_sel = st.multiselect(
        "Filter platforms", p1_platforms, default=p1_platforms, key="p1_plat",
    )
with p1c2:
    p1_cat_sel = st.multiselect(
        "Filter categories", p1_categories, default=p1_categories, key="p1_cat",
    )

p1_df = fdf[fdf["Platform"].isin(p1_plat_sel) & fdf["Category"].isin(p1_cat_sel)]

if p1_df.empty:
    st.info("No rows match the selected platforms and categories.")
    p1 = build_platform_pivot(fdf).iloc[0:0]
else:
    p1 = build_platform_pivot(p1_df)
    st.dataframe(style_pivot(p1), use_container_width=True)
    st.plotly_chart(chart_heatmap(p1), use_container_width=True)

# --- Pivot 2: Platform-Category Wise Sales -------------------------------
st.subheader(f"Platform-Category Wise Sales — {year_sel}")
st.caption("Sum of Sales Val by Platform → Category × Month")

pc_platforms = sorted(fdf["Platform"].unique().tolist())
pc_categories = sorted(fdf["Category"].dropna().unique().tolist())

fc1, fc2 = st.columns(2)
with fc1:
    pc_plat_sel = st.multiselect(
        "Filter platforms", pc_platforms, default=pc_platforms, key="pc_plat",
    )
with fc2:
    pc_cat_sel = st.multiselect(
        "Filter categories", pc_categories, default=pc_categories, key="pc_cat",
    )

pc_df = fdf[fdf["Platform"].isin(pc_plat_sel) & fdf["Category"].isin(pc_cat_sel)]

if pc_df.empty:
    st.info("No rows match the selected platforms and categories.")
    p2 = build_platform_category_pivot(fdf).iloc[0:0]
else:
    p2 = build_platform_category_pivot(pc_df)
    st.dataframe(style_pivot(p2), use_container_width=True, height=600)

# --- Download -------------------------------------------------------------
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    p1.to_excel(xw, sheet_name="Platform Wise Sales")
    p2.to_excel(xw, sheet_name="Platform-Category Wise")
st.download_button(
    "⬇︎ Download pivots as Excel",
    data=buf.getvalue(),
    file_name=f"sadafco_pivots_{year_sel}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.caption(
    "Platforms are inferred from CustomerName via keyword matching. "
    "Customers that don't match any known platform (e.g., generic 'Dark Store' entries) "
    "are bucketed as **Other**."
)
