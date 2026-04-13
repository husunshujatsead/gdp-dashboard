"""
SADAFCO Online Shopping — Sales Dashboard
Restyled in the Saudia color scheme (bright-blue filter bar + navy pivot headers).

Run:
    streamlit run sadafco_dashboard.py
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config + global CSS (Saudia palette)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SADAFCO Online Shopping Dashboard",
    page_icon="🧊",
    layout="wide",
)

SAUDIA_BLUE = "#009DE0"
NAVY = "#072E73"
NAVY_DARK = NAVY
RED = NAVY
GREEN = SAUDIA_BLUE
BG = "#FFFFFF"
MUTED = "#6B7280"


def _blend(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def shades(n: int) -> list[str]:
    if n <= 1:
        return [NAVY]
    return [_blend(NAVY, SAUDIA_BLUE, i / (n - 1)) for i in range(n)]


_PLATFORM_ORDER = ["Ninja", "Keeta", "Amazon", "Hungerstation", "Noon",
                   "Careem", "Nana", "Doosaha", "To you", "Rabbit", "Other"]
PLATFORM_COLORS = dict(zip(_PLATFORM_ORDER, shades(len(_PLATFORM_ORDER))))

_CATEGORY_ORDER = ["Frozen", "Snacks", "Drinks", "Dairy", "Culinary"]
CATEGORY_PALETTE = dict(zip(_CATEGORY_ORDER, shades(len(_CATEGORY_ORDER))))

st.markdown(
    f"""
    <style>
      .stApp {{ background: {BG}; }}
      header[data-testid="stHeader"] {{ background: transparent; }}
      .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}

      .saudia-hero {{
        background: linear-gradient(180deg, #ffffff 0%, #ffffff 100%);
        border-bottom: 1px solid #e5e7eb;
        padding: 14px 18px 16px 18px;
        margin-bottom: 0;
      }}
      .saudia-title {{
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 34px; font-weight: 700; color: #111827; margin: 0;
      }}
      .saudia-sub {{ color: {MUTED}; font-size: 13px; margin-top: 2px; }}

      .filter-bar {{
        padding: 8px 2px 0 2px;
      }}

      .kpi-card {{
        background: #fff;
        border: 1px solid #e5e7eb;
        border-left: 4px solid {SAUDIA_BLUE};
        border-radius: 6px;
        padding: 14px 16px;
        height: 100%;
      }}
      .kpi-label {{ color: {MUTED}; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }}
      .kpi-value {{ color: {NAVY_DARK}; font-size: 26px; font-weight: 700; margin-top: 4px; }}

      .sec-title {{
        font-family: Georgia, serif;
        font-size: 22px; font-weight: 700; color: {NAVY_DARK};
        margin: 22px 0 4px 0;
      }}
      .sec-sub {{ color: {MUTED}; font-size: 13px; margin-bottom: 8px; }}

      div[data-testid="column"] .stButton > button {{
        background: #fff; color: {NAVY_DARK};
        border: 1px solid #d1d5db; border-radius: 3px;
        font-weight: 600; font-size: 12px;
        padding: 6px 14px; width: 100%;
      }}
      div[data-testid="column"] .stButton > button:hover {{
        background: {NAVY_DARK}; color: #fff; border-color: {NAVY_DARK};
      }}

      .pivot-wrap table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
      .pivot-wrap thead th {{
        background: {NAVY}; color: #fff; text-align: center;
        padding: 10px 8px; font-weight: 600;
        border-right: 1px solid {NAVY_DARK};
      }}
      .pivot-wrap tbody td {{
        padding: 8px 10px; border-bottom: 1px solid #e5e7eb;
      }}
      .pivot-wrap tbody tr:nth-child(even) {{ background: #f9fafb; }}
      .pivot-wrap .row-label {{ font-weight: 600; color: {NAVY_DARK}; }}
      .pivot-wrap .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
      .pos {{ color: {GREEN}; font-weight: 600; }}
      .neg {{ color: {RED};   font-weight: 600; }}

      .pivot-filter-bar {{
        background: #f0f7fd;
        border: 1px solid #cce4f5;
        border-radius: 6px;
        padding: 10px 14px 6px 14px;
        margin-bottom: 10px;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data loading + cleaning
# ---------------------------------------------------------------------------
PLATFORM_MAP = {
    "Hungerstation": "Hungerstation",
    "Ninja Retail Company": "Ninja",
    "Noon": "Noon",
    "Doosaha": "Doosaha",
    "TO YOU": "To you",
    "AFAQ Q TECH GENERAL TRADING CO. SOUQ.COM": "Amazon",
    "keeta": "Keeta",
    "SAHABAT NANA": "Nana",
    "Rabbit": "Rabbit",
    "Careem": "Careem",
}

CATEGORY_MAP = {
    "ICE CREAM": "Frozen",
    "FROZEN FOOD": "Frozen",
    "CULINARY": "Culinary",
    "DAIRY": "Dairy",
    "NON-DAIRY DRINKS": "Drinks",
    "SNACKS": "Snacks",
}

MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@st.cache_data(show_spinner=False)
def load_data(path_or_buffer) -> pd.DataFrame:
    df = pd.read_excel(path_or_buffer, sheet_name="Data")
    df.columns = [c.strip() for c in df.columns]
    df["Platform"] = df["CustGroup"].map(PLATFORM_MAP).fillna("Other")
    df["Category"] = df["ItemCategory"].map(CATEGORY_MAP).fillna("Other")
    df["Brand"] = df["ItemGroupName"].astype(str)
    df["SKU"] = df["ItemSubGroupDescription"].astype(str)
    month_to_num = {m: i + 1 for i, m in enumerate(MONTH_ORDER)}
    df["MonthNum"] = df["Month"].map(month_to_num)
    df["Date"] = pd.to_datetime(
        dict(year=df["Year"], month=df["MonthNum"], day=df["Day"]),
        errors="coerce",
    )
    df["Sales Val"] = pd.to_numeric(df["Sales Val"], errors="coerce").fillna(0.0)
    df["Sales Qty"] = pd.to_numeric(df["Sales Qty"], errors="coerce").fillna(0.0)
    return df


DEFAULT_PATH = "Online Shopping MTD (2).xlsx"

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="saudia-hero">
      <div style="text-align:center; width:100%;">
        <div class="saudia-title">Online Shopping — Sales Dashboard</div>
        <div class="saudia-sub">Platform-wise & Platform-Category sales pivots, replicated from the SADAFCO tracker.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data source (upload or default)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"<h3 style='color:{NAVY_DARK};margin-top:0;'>Data source</h3>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload Online Shopping workbook (.xlsx)", type=["xlsx"])
    st.caption("If none uploaded, the app loads the file shipped with the app.")

try:
    df = load_data(uploaded) if uploaded is not None else load_data(DEFAULT_PATH)
except FileNotFoundError:
    st.error("No data file found. Please upload the Online Shopping workbook via the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Top filter bar — Brand, SKU, Date range only
# ---------------------------------------------------------------------------
st.markdown('<div class="filter-bar">', unsafe_allow_html=True)

max_date = df["Date"].max().date() if df["Date"].notna().any() else date.today()
min_date = df["Date"].min().date() if df["Date"].notna().any() else max_date - timedelta(days=365)

if "df_from" not in st.session_state:
    st.session_state.df_from = min_date
    st.session_state.df_to   = max_date

c1, c2, c3, c4 = st.columns([1.4, 1.8, 1, 1])
with c1:
    brands = ["All"] + sorted(df["Brand"].dropna().unique().tolist())
    f_brand = st.selectbox("Brand", brands, index=0)
with c2:
    sku_pool = df.copy()
    if f_brand != "All":
        sku_pool = sku_pool[sku_pool["Brand"] == f_brand]
    skus = ["All"] + sorted(sku_pool["SKU"].dropna().unique().tolist())
    f_sku = st.selectbox("SKU", skus, index=0)
with c3:
    f_date_from = st.date_input("Date from", value=st.session_state.df_from,
                                min_value=min_date, max_value=max_date)
    st.session_state.df_from = f_date_from
with c4:
    f_date_to = st.date_input("Date to", value=st.session_state.df_to,
                              min_value=min_date, max_value=max_date)
    st.session_state.df_to = f_date_to

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Apply base filters (no platform/category yet — those are pivot-level)
# ---------------------------------------------------------------------------
base_mask = (df["Date"].dt.date >= f_date_from) & (df["Date"].dt.date <= f_date_to)
if f_brand != "All": base_mask &= df["Brand"] == f_brand
if f_sku   != "All": base_mask &= df["SKU"] == f_sku
fdf_base = df[base_mask].copy()
months_present = [
    m for m in MONTH_ORDER
    if m in fdf_base["Month"].unique()
]
# ---------------------------------------------------------------------------
# KPI cards — based on full base-filtered data
# ---------------------------------------------------------------------------
def human(n: float) -> str:
    a = abs(n)
    if a >= 1e9: return f"{n/1e9:.2f}B"
    if a >= 1e6: return f"{n/1e6:.2f}M"
    if a >= 1e3: return f"{n/1e3:.1f}K"
    return f"{n:,.0f}"


total_sales = fdf_base["Sales Val"].sum()
total_units = fdf_base["Sales Qty"].sum()
n_platforms = fdf_base["Platform"].nunique()
n_skus = fdf_base["SKU"].nunique()
top_platform = (
    fdf_base.groupby("Platform")["Sales Val"].sum().sort_values(ascending=False).index[0]
    if not fdf_base.empty else "—"
)

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns(5)
for col, label, value in [
    (k1, "Total sales (SAR)", human(total_sales)),
    (k2, "Units sold",        human(total_units)),
    (k3, "Platforms",         str(n_platforms)),
    (k4, "Active SKUs",       str(n_skus)),
    (k5, "Top platform",      top_platform),
]:
    col.markdown(
        f"<div class='kpi-card'><div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Charts — use base-filtered data (no platform/category filter)
# ---------------------------------------------------------------------------
st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

st.markdown("<div class='sec-title'>Total sales by platform</div>", unsafe_allow_html=True)
bars = (fdf_base.groupby("Platform")["Sales Val"].sum()
            .sort_values(ascending=True).reset_index())
if bars.empty:
    st.info("No data for the current filters.")

else:
    bar_colors = [PLATFORM_COLORS.get(p, "#9CA3AF") for p in bars["Platform"]]
    fig = go.Figure(go.Bar(
        x=bars["Sales Val"], y=bars["Platform"], orientation="h",
        marker=dict(color=bar_colors),
        text=[human(v) for v in bars["Sales Val"]],
        textposition="outside", cliponaxis=False,
    ))
    fig.update_layout(
        height=400, margin=dict(l=10, r=40, t=10, b=10),
        plot_bgcolor="white",
        xaxis=dict(gridcolor="#e5e7eb", title="Total sales value (SAR)"),
        yaxis=dict(title=""),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<div class='sec-title'>Category mix by platform</div>", unsafe_allow_html=True)
mix = (fdf_base.groupby(["Platform", "Category"])["Sales Val"].sum().reset_index())
if mix.empty:
    st.info("No data for the current filters.")
else:
    plat_order = (mix.groupby("Platform")["Sales Val"].sum()
                       .sort_values(ascending=False).index.tolist())
    fig = px.bar(
        mix, x="Platform", y="Sales Val", color="Category",
        color_discrete_map=CATEGORY_PALETTE,
        category_orders={"Platform": plat_order,
                         "Category": list(CATEGORY_PALETTE.keys())},
    )
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white", barmode="stack",
        yaxis=dict(gridcolor="#e5e7eb", title="Sales value (SAR)"),
        xaxis=dict(title=""),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Year-over-Year comparison
# ---------------------------------------------------------------------------
st.markdown("<div class='sec-title' style='margin-top:28px;'>Year-over-Year comparison</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sec-sub'>For each month present in the current year we compare against the "
    "same month of the prior year. Partial months are compared day-matched "
    "(e.g. April 1–11 CY vs April 1–11 PY) so the numbers stay apples-to-apples.</div>",
    unsafe_allow_html=True,
)

yoy_base = fdf_base.copy()

cy_year = int(yoy_base["Year"].max()) if yoy_base["Year"].notna().any() else None
py_year = cy_year - 1 if cy_year else None

yoy_rows: list[dict] = []

if cy_year is None or py_year not in yoy_base["Year"].unique():
    st.info("Not enough history in the data to compute a year-over-year comparison for the current filters.")
else:
    cy_months = (yoy_base[yoy_base["Year"] == cy_year]["Month"].unique().tolist())
    cy_months = [m for m in MONTH_ORDER if m in cy_months]

    for m in cy_months:
        cy_slice = yoy_base[(yoy_base["Year"] == cy_year) & (yoy_base["Month"] == m)]
        if cy_slice.empty:
            continue
        max_day = int(cy_slice["Day"].max())
        py_slice = yoy_base[(yoy_base["Year"] == py_year) &
                            (yoy_base["Month"] == m) &
                            (yoy_base["Day"] <= max_day)]
        cy_val = float(cy_slice["Sales Val"].sum())
        py_val = float(py_slice["Sales Val"].sum())
        delta = cy_val - py_val
        pct = (delta / py_val * 100) if py_val else None
        yoy_rows.append({
            "Month": m, "Window": f"1–{max_day}",
            f"{cy_year}": cy_val, f"{py_year}": py_val,
            "Δ SAR": delta, "Δ %": pct,
        })

    if not yoy_rows:
        st.info("No overlapping months between current and prior year under the current filters.")
    else:
        def fmt_pct(p):
            if p is None or pd.isna(p):
                return "<span style='color:#9ca3af'>—</span>"
            arrow = "▲" if p >= 0 else "▼"
            color = SAUDIA_BLUE if p >= 0 else NAVY
            return f"<span style='color:{color};font-weight:700'>{arrow} {p:+.1f}%</span>"

        def fmt_delta(v):
            if v == 0 or pd.isna(v):
                return "<span style='color:#9ca3af'>—</span>"
            color = SAUDIA_BLUE if v >= 0 else NAVY
            sign = "+" if v > 0 else "−"
            return f"<span style='color:{color};font-weight:700'>{sign}{human(abs(v))}</span>"

        head = (f"<thead><tr>"
                f"<th>Month</th><th>Window</th>"
                f"<th>{cy_year}</th><th>{py_year}</th>"
                f"<th>Δ SAR</th><th>Δ %</th></tr></thead>")
        body = []
        for r in yoy_rows:
            body.append(
                "<tr>"
                f"<td class='row-label'>{r['Month']}</td>"
                f"<td class='num'>{r['Window']}</td>"
                f"<td class='num'>{human(r[str(cy_year)])}</td>"
                f"<td class='num'>{human(r[str(py_year)])}</td>"
                f"<td class='num'>{fmt_delta(r['Δ SAR'])}</td>"
                f"<td class='num'>{fmt_pct(r['Δ %'])}</td>"
                "</tr>"
            )
        st.markdown(
            f"<div class='pivot-wrap'><table>{head}<tbody>{''.join(body)}</tbody></table></div>",
            unsafe_allow_html=True,
        )

        latest_month = yoy_rows[-1]["Month"]
        latest_max_day = int(yoy_base[(yoy_base["Year"] == cy_year) &
                                      (yoy_base["Month"] == latest_month)]["Day"].max())

        cy_plat = (yoy_base[(yoy_base["Year"] == cy_year) &
                            (yoy_base["Month"] == latest_month)]
                   .groupby("Platform")["Sales Val"].sum())
        py_plat = (yoy_base[(yoy_base["Year"] == py_year) &
                            (yoy_base["Month"] == latest_month) &
                            (yoy_base["Day"] <= latest_max_day)]
                   .groupby("Platform")["Sales Val"].sum())

        plat_df = pd.DataFrame({f"{cy_year}": cy_plat, f"{py_year}": py_plat}).fillna(0)
        plat_df = plat_df.loc[plat_df.sum(axis=1).sort_values(ascending=False).index]

        if not plat_df.empty:
            st.markdown(
                f"<div class='sec-title' style='margin-top:18px;'>{latest_month} YoY by platform "
                f"<span style='font-size:13px;color:{MUTED};font-weight:500'>(1–{latest_max_day}, "
                f"{cy_year} vs {py_year})</span></div>",
                unsafe_allow_html=True,
            )
            fig = go.Figure()
            fig.add_bar(name=str(py_year), x=plat_df.index, y=plat_df[str(py_year)],
                        marker_color=SAUDIA_BLUE,
                        text=[human(v) for v in plat_df[str(py_year)]], textposition="outside")
            fig.add_bar(name=str(cy_year), x=plat_df.index, y=plat_df[str(cy_year)],
                        marker_color=NAVY,
                        text=[human(v) for v in plat_df[str(cy_year)]], textposition="outside")
            fig.update_layout(
                barmode="group", height=400,
                margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                yaxis=dict(gridcolor="#e5e7eb", title="Sales value (SAR)"),
                xaxis=dict(title=""), legend_title_text="Year",
            )
            st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Pivot tables — each has its own Platform / Category filter inline
# ---------------------------------------------------------------------------
def fmt_cell(v):
    if pd.isna(v) or v == 0:
        return "<span style='color:#9ca3af'>—</span>"
    return f"<span class='num'>{human(v)}</span>"


def render_pivot(pv: pd.DataFrame, index_cols: list[str]) -> str:
    months_present = [m for m in MONTH_ORDER if m in pv.columns]
    pv = pv[months_present]
    head = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in index_cols) + \
           "".join(f"<th>{m}</th>" for m in months_present) + "</tr></thead>"
    body_rows = []
    for idx, row in pv.iterrows():
        if isinstance(idx, tuple):
            idx_cells = "".join(f"<td class='row-label'>{i}</td>" for i in idx)
        else:
            idx_cells = f"<td class='row-label'>{idx}</td>"
        cells = "".join(f"<td class='num'>{fmt_cell(row[m])}</td>" for m in months_present)
        body_rows.append(f"<tr>{idx_cells}{cells}</tr>")
    return f"<div class='pivot-wrap'><table>{head}<tbody>{''.join(body_rows)}</tbody></table></div>"


# ── Platform Wise Sales pivot ────────────────────────────────────────────────
st.markdown(f"<h2 class='sec-title' style='margin-top:28px;'>Platform Wise Sales — {max_date.year}</h2>", unsafe_allow_html=True)
st.markdown("<div class='sec-sub'>Sum of Sales Val by Platform × Month</div>", unsafe_allow_html=True)

# Filter bar — Platform only (sits right above this pivot)
# st.markdown("<div class='pivot-filter-bar'>", unsafe_allow_html=True)
# pf1, _pf_spacer = st.columns([1.5, 4])
# with pf1:
#     pws_platforms = ["All"] + sorted(fdf_base["Platform"].unique().tolist())
#     f_pws_platform = st.selectbox("Filter by Platform", pws_platforms, index=0,
#                                   key="pws_platform_filter")
# st.markdown("</div>", unsafe_allow_html=True)

pws_data = fdf_base.copy()
# if f_pws_platform != "All":
#     pws_data = pws_data[pws_data["Platform"] == f_pws_platform]

plat_month = (pws_data.pivot_table(index="Platform", columns="Month",
                                   values="Sales Val", aggfunc="sum", fill_value=0)
                      .reindex(columns=months_present, fill_value=0))
plat_month = plat_month.loc[plat_month.sum(axis=1).sort_values(ascending=False).index]
st.markdown(render_pivot(plat_month, ["Platform"]), unsafe_allow_html=True)


# ── Platform-Category Wise Sales pivot ──────────────────────────────────────
st.markdown(f"<h2 class='sec-title' style='margin-top:32px;'>Platform-Category Wise Sales — {max_date.year}</h2>", unsafe_allow_html=True)
st.markdown("<div class='sec-sub'>Sum of Sales Val by Platform → Category × Month</div>", unsafe_allow_html=True)

# Filter bar — Platform + Category (sits right above this pivot)
st.markdown("<div class='pivot-filter-bar'>", unsafe_allow_html=True)
pc1, pc2, _pc_spacer = st.columns([1.5, 1.5, 3])
with pc1:
    pcw_platforms = ["All"] + sorted(fdf_base["Platform"].unique().tolist())
    f_pcw_platform = st.selectbox("Filter by Platform", pcw_platforms, index=0,
                                  key="pcw_platform_filter")
with pc2:
    pcw_categories = ["All"] + sorted(fdf_base["Category"].unique().tolist())
    f_pcw_category = st.selectbox("Filter by Category", pcw_categories, index=0,
                                  key="pcw_category_filter")
st.markdown("</div>", unsafe_allow_html=True)

pcw_data = fdf_base.copy()
if f_pcw_platform != "All":
    pcw_data = pcw_data[pcw_data["Platform"] == f_pcw_platform]
if f_pcw_category != "All":
    pcw_data = pcw_data[pcw_data["Category"] == f_pcw_category]

plat_cat_month = (pcw_data.pivot_table(index=["Platform", "Category"], columns="Month",
                                       values="Sales Val", aggfunc="sum", fill_value=0)
                           .reindex(columns=months_present, fill_value=0))
plat_totals = plat_cat_month.groupby(level=0).sum().sum(axis=1).sort_values(ascending=False)
plat_cat_month = plat_cat_month.reindex(plat_totals.index, level=0)
st.markdown(render_pivot(plat_cat_month, ["Platform", "Category"]), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Volumes view — focus SKUs
# ---------------------------------------------------------------------------
VOLUME_BUCKETS: dict[str, dict] = {
    "Whole Milk 1L":          {"sku": ["WHOLE MILK RECAP12X1000ML"]},
    "Whole Milk 2L":          {"sku": ["WHOLE MILK 6X2000 CC (PROMO)"]},
    "Whole Milk Pack of 4":   {"sku": ["WHOLE MILK 3X(4X1L)"]},
    "Whole Milk 200ml":       {"sku": ["WHOLE MILK 24X200ML"]},
    "Flavoured Milk 125ml":   {"group": "Flavoured Milk 125ml."},
    "Flavoured Milk 200ml":   {"group": "Flavoured Milk 200ml."},
    "Tomato Paste 135g":      {"sku": ["TOMATO PASTE 48X135 GM", "Tomato Paste Organic 6x4x135gm"]},
}


def bucket_mask(data: pd.DataFrame, spec: dict) -> pd.Series:
    if "sku" in spec:
        return data["ItemSubGroupDescription"].isin(spec["sku"])
    return data["ItemGroupName"] == spec["group"]


st.markdown(f"<h2 class='sec-title' style='margin-top:32px;'>Volumes View — Focus SKUs</h2>", unsafe_allow_html=True)
st.markdown("<div class='sec-sub'>Units sold per month for a fixed set of focus SKUs. 'Flavoured Milk' buckets sum across all flavours.</div>", unsafe_allow_html=True)

vol_rows: list[dict] = []
for label, spec in VOLUME_BUCKETS.items():
    sub = fdf_base[bucket_mask(fdf_base, spec)]
    if sub.empty:
        continue
    monthly = sub.groupby("Month")["Sales Qty"].sum()
    row = {"SKU": label}
    for m in MONTH_ORDER:
        row[m] = monthly.get(m, 0.0)
    row["Total"] = float(monthly.sum())
    vol_rows.append(row)

if not vol_rows:
    st.info("No units recorded for any of the focus SKUs under the current filters.")
else:
    vol_df = pd.DataFrame(vol_rows).set_index("SKU")
    months_present = [
        m for m in MONTH_ORDER
        if m in fdf_base["Month"].unique()
    ]
    head = "<thead><tr><th>Focus SKU</th>" + \
           "".join(f"<th>{m}</th>" for m in months_present) + "<th>Total</th></tr></thead>"
    body_html = []
    for idx, row in vol_df.iterrows():
        cells = "".join(
            f"<td class='num'>{fmt_cell(row[m])}</td>" for m in months_present
        )
        total_cell = f"<td class='num' style='background:#F3F6FB;font-weight:700;color:{NAVY_DARK}'>{human(row['Total'])}</td>"
        body_html.append(f"<tr><td class='row-label'>{idx}</td>{cells}{total_cell}</tr>")
    st.markdown(
        f"<div class='pivot-wrap'><table>{head}<tbody>{''.join(body_html)}</tbody></table></div>",
        unsafe_allow_html=True,
    )

    chart_df = vol_df[months_present].reset_index().melt(
        id_vars="SKU", var_name="Month", value_name="Units")
    chart_df["Month"] = pd.Categorical(chart_df["Month"],
                                       categories=months_present, ordered=True)
    chart_df = chart_df.sort_values("Month")
    n_months = len(months_present)
    fig = px.bar(
        chart_df, x="SKU", y="Units", color="Month", barmode="group",
        color_discrete_sequence=shades(max(n_months, 2)),
    )
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=20, b=80),
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#e5e7eb", title="Units sold"),
        xaxis=dict(title="", tickangle=-20),
        legend_title_text="Month",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Note: Flavoured Milk 250ml is not a current SADAFCO online-range SKU; Flavoured Milk 200ml shown as the closest match.")

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def build_excel() -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as xl:
        plat_month.to_excel(xl, sheet_name="Platform x Month")
        plat_cat_month.to_excel(xl, sheet_name="Platform-Category x Month")
        if yoy_rows:
            pd.DataFrame(yoy_rows).to_excel(xl, sheet_name="YoY Comparison", index=False)
        if vol_rows:
            pd.DataFrame(vol_rows).set_index("SKU").to_excel(
                xl, sheet_name="Focus SKU Volumes")
        fdf_base[["Date", "Platform", "Category", "Brand", "SKU",
                  "Sales Val", "Sales Qty"]].to_excel(xl, sheet_name="Filtered Data", index=False)
    return out.getvalue()


st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
st.download_button(
    "⬇  Download pivots as Excel",
    data=build_excel(),
    file_name="sadafco_online_shopping_pivots.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.caption(
    "Platforms are mapped from `CustGroup`; minor / one-off customer groups are bucketed as **Other**. "
    "Categories are normalised from `ItemCategory` (ICE CREAM & FROZEN FOOD → Frozen, NON-DAIRY DRINKS → Drinks, etc.)."
)
