"""
SADAFCO Online Shopping — Sales Dashboard
Restyled in the Saudia color scheme (bright-blue filter bar + navy pivot headers).

Run:
    streamlit run sadafco_dashboard.py
"""

from __future__ import annotations

import io
from datetime import date, timedelta
import datetime as _dt

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from datetime import timedelta
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Page config + global CSS (Saudia palette)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SADAFCO Online Shopping Dashboard",
    page_icon="🧊",
    layout="wide",
)

st.markdown("""
<style>
.pivot-wrap table {
    width: 100%;
    table-layout: fixed;   /* KEY FIX */
    border-collapse: collapse;
}

.pivot-wrap td {
    padding: 4px 8px;
}

.row-label {
    text-align: left;
}

.num {
    text-align: right;
    width: 100px;          /* FIXED WIDTH FOR ALL NUMBERS */
    white-space: nowrap;
}
</style>
""", unsafe_allow_html=True)

SAUDIA_BLUE = "#009DE0"      # brand bright blue
NAVY = "#072E73"             # brand navy
NAVY_DARK = NAVY
RED = NAVY                   # unused pos/neg styling kept neutral
GREEN = SAUDIA_BLUE
BG = "#FFFFFF"
MUTED = "#6B7280"


def _blend(c1: str, c2: str, t: float) -> str:
    """Interpolate two hex colours. t in [0, 1]."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def shades(n: int) -> list[str]:
    """n shades from NAVY → SAUDIA_BLUE."""
    if n <= 1:
        return [NAVY]
    return [_blend(NAVY, SAUDIA_BLUE, i / (n - 1)) for i in range(n)]


# Platform colours — actual brand colours
PLATFORM_COLORS = {
    "Ninja":         "#39C3CC",  # Ninja teal
    "Keeta":         "#FFD600",  # Keeta/Meituan yellow
    "Amazon":        "#FF9900",  # Amazon orange
    "Hungerstation": "#FF5722",  # Hungerstation hot-orange
    "Noon":          "#F6EA00",  # Noon yellow
    "Careem":        "#00B140",  # Careem green
    "Nana":          "#7C3AED",  # Nana purple
    "Doosaha":       "#0EA5E9",  # Doosaha sky-blue
    "To you":        "#EC4899",  # To you magenta
    "Rabbit":        "#F43F5E",  # Rabbit rose
    "Other":         "#9CA3AF",  # neutral grey
}

# Category colours — single neutral colour (no colour encoding for categories)
CATEGORY_PALETTE = {
    "Frozen":   NAVY,
    "Snacks":   NAVY,
    "Drinks":   NAVY,
    "Dairy":    NAVY,
    "Culinary": NAVY,
}

st.markdown(
    f"""
    <style>
      /* base */
      .stApp {{ background: {BG}; }}
      header[data-testid="stHeader"] {{ background: transparent; }}
      .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}

      /* ---- Saudia hero header ---- */
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

      /* ---- filter bar ---- */
      .filter-bar {{
        padding: 8px 2px 0 2px;
      }}

      /* KPI cards */
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

      /* section titles */
      .sec-title {{
        font-family: Georgia, serif;
        font-size: 22px; font-weight: 700; color: {NAVY_DARK};
        margin: 22px 0 4px 0;
      }}
      .sec-sub {{ color: {MUTED}; font-size: 13px; margin-bottom: 8px; }}

      /* period-chip buttons */
      div[data-testid="column"] .stButton > button {{
        background: #fff; color: {NAVY_DARK};
        border: 1px solid #d1d5db; border-radius: 3px;
        font-weight: 600; font-size: 12px;
        padding: 6px 14px; width: 100%;
      }}
      div[data-testid="column"] .stButton > button:hover {{
        background: {NAVY_DARK}; color: #fff; border-color: {NAVY_DARK};
      }}
      .period-active > button {{
        background: {NAVY_DARK} !important; color: #fff !important; border-color: {NAVY_DARK} !important;
      }}

      /* pivot table headers */
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
    # everything else → Other
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
MONTH_NUM_TO_ABR = {i + 1: m for i, m in enumerate(MONTH_ORDER)}
MONTH_ABR_TO_NUM = {m: i + 1 for i, m in enumerate(MONTH_ORDER)}

# ---------------------------------------------------------------------------
# Platform inference from CustomerName (historical file has no CustGroup)
# ---------------------------------------------------------------------------
import re as _re

_PLATFORM_KW: list[tuple[_re.Pattern, str]] = [
    (_re.compile(r"hunger\s*sta", _re.I),             "Hungerstation"),
    (_re.compile(r"ninja", _re.I),                    "Ninja"),
    (_re.compile(r"noon", _re.I),                     "Noon"),
    (_re.compile(r"keeta", _re.I),                    "Keeta"),
    (_re.compile(r"amazon|afaq", _re.I),              "Amazon"),
    (_re.compile(r"careem", _re.I),                   "Careem"),
    (_re.compile(r"nana|sahabat|sahabath", _re.I),    "Nana"),
    (_re.compile(r"rabbit", _re.I),                   "Rabbit"),
    (_re.compile(r"doosa", _re.I),                    "Doosaha"),
    (_re.compile(r"to.you", _re.I),                   "To you"),
    (_re.compile(r"nefaah|matjar.annab", _re.I),      "Other"),
]

# CustGroup map (used when the MTD file has CustGroup directly)
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


def _infer_platform(name: str) -> str:
    for pat, plat in _PLATFORM_KW:
        if pat.search(name):
            return plat
    return "Other"


@st.cache_data(show_spinner=False)
def load_historic(path_or_buffer) -> pd.DataFrame:
    """Load the multi-year historical file (Online Shopping 24-26).
    Schema: Year(int), Month(int), CustomerName, Categroy, ItemSubGroup,
            ItemSubGroupDesc, SKU, Gross Sales Amount, Sales Qty.
    No Day column → we set Day=15 (mid-month) for date construction.
    """
    xl = pd.ExcelFile(path_or_buffer)
    sheet = xl.sheet_names[0]  # single sheet, name may vary
    df = pd.read_excel(xl, sheet_name=sheet)
    df.columns = [c.strip() for c in df.columns]
    # normalise column names → common schema
    df = df.rename(columns={
        "Categroy": "ItemCategory",
        "ItemSubGroup": "ItemGroupName",
        "ItemSubGroupDesc": "ItemSubGroupDescription",
        "SKU": "AlternateCode",
        "Gross Sales Amount": "Sales Val",
    })
    df["Platform"] = df["CustomerName"].apply(_infer_platform)
    df["Category"] = df["ItemCategory"].map(CATEGORY_MAP).fillna("Other")
    df["Brand"] = df["ItemGroupName"].astype(str)
    df["SKU_label"] = df["ItemSubGroupDescription"].astype(str)
    # Month is int in this file
    df["MonthNum"] = df["Month"].astype(int)
    df["Month"] = df["MonthNum"].map(MONTH_NUM_TO_ABR)
    df["Day"] = 15  # placeholder — no daily granularity in historic file
    df["Date"] = pd.to_datetime(
        dict(year=df["Year"], month=df["MonthNum"], day=df["Day"]),
        errors="coerce",
    )
    df["Sales Val"] = pd.to_numeric(df["Sales Val"], errors="coerce").fillna(0.0)
    df["Sales Qty"] = pd.to_numeric(df["Sales Qty"], errors="coerce").fillna(0.0)
    return df[["Year", "Month", "MonthNum", "Day", "Date",
               "DepotName", "CustomerName", "Platform",
               "ItemCategory", "ItemGroupName", "ItemSubGroupDescription",
               "AlternateCode", "Category", "Brand", "SKU_label",
               "Sales Val", "Sales Qty"]]


@st.cache_data(show_spinner=False)
def load_mtd(path_or_buffer) -> pd.DataFrame:
    """Load the week-level MTD file. Has CustGroup, Day, etc."""
    df = pd.read_excel(path_or_buffer, sheet_name="Data")
    df.columns = [c.strip() for c in df.columns]
    df["Platform"] = df["CustGroup"].map(PLATFORM_MAP).fillna("Other")
    df["Category"] = df["ItemCategory"].map(CATEGORY_MAP).fillna("Other")
    df["Brand"] = df["ItemGroupName"].astype(str)
    df["SKU_label"] = df["ItemSubGroupDescription"].astype(str)
    month_to_num = {m: i + 1 for i, m in enumerate(MONTH_ORDER)}
    df["MonthNum"] = df["Month"].map(month_to_num)
    df["Date"] = pd.to_datetime(
        dict(year=df["Year"], month=df["MonthNum"], day=df["Day"]),
        errors="coerce",
    )
    df["Sales Val"] = pd.to_numeric(df["Sales Val"], errors="coerce").fillna(0.0)
    df["Sales Qty"] = pd.to_numeric(df["Sales Qty"], errors="coerce").fillna(0.0)
    return df[["Year", "Month", "MonthNum", "Day", "Date",
               "DepotName", "CustomerName", "Platform",
               "ItemCategory", "ItemGroupName", "ItemSubGroupDescription",
               "AlternateCode", "Category", "Brand", "SKU_label",
               "Sales Val", "Sales Qty"]]


def merge_historic_mtd(hist: pd.DataFrame, mtd: pd.DataFrame) -> pd.DataFrame:
    """Merge: for any (Year, Month) present in MTD, drop that month from historic
    and use the MTD data instead. This way the weekly MTD refresh always wins."""
    mtd_periods = mtd[["Year", "MonthNum"]].drop_duplicates()
    # Mark historic rows that overlap with MTD periods
    hist_keyed = hist.assign(_key=hist["Year"].astype(str) + "_" + hist["MonthNum"].astype(str))
    mtd_keys = set(mtd_periods["Year"].astype(str) + "_" + mtd_periods["MonthNum"].astype(str))
    hist_filtered = hist_keyed[~hist_keyed["_key"].isin(mtd_keys)].drop(columns="_key")
    return pd.concat([hist_filtered, mtd], ignore_index=True)


# Default file paths (when sitting next to the script)
DEFAULT_HIST = "Online Shopping 24-26 (1).xlsx"
DEFAULT_MTD  = "Online Shopping MTD (3).xlsx"
DEFAULT_DATA_DASH = "Sadafco Data Dashboard (1).xlsx"
DEFAULT_KEETA = "Sadafco Keeta Manual Tracker.xlsx"


def _parse_date_raw(v):
    """Parse a single date value without swapping."""
    if pd.isna(v):
        return pd.NaT
    if isinstance(v, str):
        return pd.to_datetime(v, dayfirst=True, errors="coerce")
    if isinstance(v, (_dt.datetime, pd.Timestamp)):
        return pd.Timestamp(v)
    return pd.NaT


def _fix_dates_column(series: pd.Series) -> pd.Series:
    """Two-pass fix for mixed Excel date formats."""
    is_str = series.apply(lambda v: isinstance(v, str))
    parsed = series.apply(_parse_date_raw)
    str_months = set(parsed[is_str].dropna().dt.month.unique())
    if not str_months:
        return parsed
    dt_mask = ~is_str & parsed.notna()
    result = parsed.copy()
    for idx in result[dt_mask].index:
        ts = result.at[idx]
        if ts.month not in str_months and ts.day <= 12 and ts.day in str_months:
            try:
                result.at[idx] = pd.Timestamp(year=ts.year, month=ts.day, day=ts.month)
            except Exception:
                pass
    return result


@st.cache_data(show_spinner=False)
def load_pricing(path_or_buffer) -> pd.DataFrame:
    df = pd.read_excel(path_or_buffer, sheet_name="Price")
    df.columns = [c.strip() for c in df.columns]
    df["Date"] = _fix_dates_column(df["Date"])
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_availability(path_or_buffer) -> pd.DataFrame:
    df = pd.read_excel(path_or_buffer, sheet_name="Availability")
    df.columns = [c.strip() for c in df.columns]
    df["Date"] = _fix_dates_column(df["Date"])
    df["Availability"] = pd.to_numeric(df["Availability"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_keeta_tracker(path_or_buffer) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the Keeta Manual Tracker — returns (price_df, avail_df) in the same
    schema as the main data dashboard file so they can be concatenated."""
    xl = pd.ExcelFile(path_or_buffer)
    # Parse locations key — headers are in data row, not header row
    loc_raw = pd.read_excel(xl, sheet_name="Locations Key", header=None)
    # Find the row containing "City" to use as header
    header_row = None
    for i, row in loc_raw.iterrows():
        if row.astype(str).str.contains("City", case=False).any():
            header_row = i
            break
    if header_row is not None:
        loc = loc_raw.iloc[header_row + 1:].copy()
        loc.columns = loc_raw.iloc[header_row].values
    else:
        loc = pd.DataFrame()

    city_map = {}
    if not loc.empty and "Location Name" in loc.columns and "City" in loc.columns:
        loc = loc.dropna(subset=["Location Name"])
        city_map = dict(zip(loc["Location Name"].astype(str).str.strip(),
                            loc["City"].astype(str).str.strip()))

    rows = []
    for sheet in xl.sheet_names:
        if sheet == "Locations Key":
            continue
        sdf = pd.read_excel(xl, sheet_name=sheet)
        sdf.columns = [c.strip() for c in sdf.columns]
        sdf["Store"] = sheet
        sdf["City"] = city_map.get(sheet, "Unknown")
        rows.append(sdf)

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    raw = pd.concat(rows, ignore_index=True)
    raw = raw.dropna(subset=["SKU"])

    # Assign yesterday's date (snapshot date)
    snap_date = pd.Timestamp(date.today() - timedelta(days=1))

    # Infer Brand from SKU name
    def _keeta_brand(sku: str) -> str:
        s = str(sku).lower()
        if "saudia" in s:
            return "Saudia"
        if "nadec" in s:
            return "Nadec"
        if "almarai" in s:
            return "Almarai"
        if "al safi" in s:
            return "Al Safi"
        if "lays" in s:
            return "Lays"
        if "al batal" in s:
            return "Al Batal"
        if "pringles" in s:
            return "Pringles"
        if "baskin" in s:
            return "Baskin Robbins"
        if "kwality" in s:
            return "Kwality"
        if "nada" in s:
            return "Nada"
        if "luna" in s:
            return "Luna"
        if "al alali" in s:
            return "Al Alali"
        return "Other"

    # Infer Category from SKU name
    def _keeta_category(sku: str) -> str:
        s = str(sku).lower()
        if "milk" in s:
            return "Milk"
        if "ice cream" in s or "sandwich" in s:
            return "Ice Cream"
        if "tomato paste" in s or "paste" in s:
            return "Paste"
        if "ketchup" in s:
            return "Ketchup"
        if "yoghurt" in s or "yogurt" in s:
            return "Yoghurt"
        if "evaporated" in s:
            return "Evaporated Milk"
        if "pizza sauce" in s or "sauce" in s:
            return "Sauce"
        if "chips" in s or "rings" in s or "letters" in s or "cheese balls" in s:
            return "Snacks"
        return "Other"

    # Determine Brand vs Competitor type
    def _keeta_type(brand: str) -> str:
        return "Brand" if brand in ("Saudia", "Crispy") else "Competitor"

    raw["Brand"] = raw["SKU"].apply(_keeta_brand)
    raw["Category"] = raw["SKU"].apply(_keeta_category)
    raw["Type"] = raw["Brand"].apply(_keeta_type)
    raw["Platform"] = "Keeta"
    raw["Date"] = snap_date

    # Price DataFrame
    keeta_price = raw[["Date", "Platform", "Brand", "Category", "SKU",
                       "Store", "City", "Type", "Price"]].copy()
    keeta_price["Price"] = pd.to_numeric(keeta_price["Price"], errors="coerce")

    # Availability DataFrame
    keeta_avail = raw[["Date", "Platform", "Brand", "Category", "SKU",
                       "Store", "City", "Availability"]].copy()
    keeta_avail["Availability"] = pd.to_numeric(keeta_avail["Availability"], errors="coerce")

    return keeta_price, keeta_avail

# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="saudia-hero">
      <div style="text-align:center; width:100%;">
        <div class="saudia-title">SADAFCO — Online Shopping Dashboard</div>
        <div class="saudia-sub">Sales tracker, pricing & availability — all in one place.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data source — sidebar with all upload slots
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"<h3 style='color:{NAVY_DARK};margin-top:0;'>Sales Tracker</h3>", unsafe_allow_html=True)
    st.caption(
        "Upload the **historic** file once (Online Shopping 24-26). "
        "Each week, upload the latest **MTD** file — it replaces the "
        "overlapping months in the historic data automatically."
    )
    hist_upload = st.file_uploader("Historic file (.xlsx)", type=["xlsx"],
                                   key="hist_upload")
    mtd_upload  = st.file_uploader("MTD file (.xlsx)", type=["xlsx"],
                                   key="mtd_upload")
    st.markdown("---")
    st.markdown(f"<h3 style='color:{NAVY_DARK};margin-top:0;'>Pricing & Availability</h3>", unsafe_allow_html=True)
    data_dash_upload = st.file_uploader("Data Dashboard file (.xlsx)", type=["xlsx"],
                                        key="data_dash_upload")
    keeta_upload = st.file_uploader("Keeta Manual Tracker (.xlsx)", type=["xlsx"],
                                    key="keeta_upload")

# --- Load sales data ---
hist_df = None
mtd_df  = None
try:
    hist_src = hist_upload if hist_upload is not None else DEFAULT_HIST
    hist_df = load_historic(hist_src)
except Exception:
    pass
try:
    mtd_src = mtd_upload if mtd_upload is not None else DEFAULT_MTD
    mtd_df = load_mtd(mtd_src)
except Exception:
    pass

if hist_df is not None and mtd_df is not None:
    df = merge_historic_mtd(hist_df, mtd_df)
elif hist_df is not None:
    df = hist_df
elif mtd_df is not None:
    df = mtd_df
else:
    df = None
if df is not None:
    df["SKU"] = df["SKU_label"]

# --- Load pricing & availability data ---
dd_src = data_dash_upload if data_dash_upload is not None else DEFAULT_DATA_DASH
price_df = None
avail_df = None
_dd_load_error = None
try:
    price_df = load_pricing(dd_src)
    avail_df = load_availability(dd_src)
except Exception as e:
    _dd_load_error = str(e)

# --- Load Keeta tracker and merge ---
keeta_src = keeta_upload if keeta_upload is not None else DEFAULT_KEETA
try:
    keeta_price, keeta_avail = load_keeta_tracker(keeta_src)
    if not keeta_price.empty:
        if price_df is not None:
            # Align columns — keep only common columns
            common_pr = [c for c in price_df.columns if c in keeta_price.columns]
            price_df = pd.concat([price_df[common_pr], keeta_price[common_pr]], ignore_index=True)
        else:
            price_df = keeta_price
    if not keeta_avail.empty:
        if avail_df is not None:
            common_av = [c for c in avail_df.columns if c in keeta_avail.columns]
            avail_df = pd.concat([avail_df[common_av], keeta_avail[common_av]], ignore_index=True)
        else:
            avail_df = keeta_avail
except Exception:
    pass  # Keeta file is optional

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab_sales, tab_pricing, tab_availability = st.tabs(["📊 Sales Tracker", "💲 Pricing", "📦 Availability"])


# ===========================================================================
# TAB 1 — SALES TRACKER
# ===========================================================================
with tab_sales:
    if df is None:
        st.info("No sales data found. Upload the historic and/or MTD workbooks via the sidebar.")
    else:
        # ---------------------------------------------------------------------------
        # Filter bar (Saudia blue)
        # ---------------------------------------------------------------------------
        st.markdown('<div class="filter-bar">', unsafe_allow_html=True)

        max_date = df["Date"].max().date() if df["Date"].notna().any() else date.today()
        min_date = df["Date"].min().date() if df["Date"].notna().any() else max_date - timedelta(days=365)

        # default date range — full span of the data
        if "df_from" not in st.session_state:
            st.session_state.df_from = min_date
            st.session_state.df_to   = max_date

        # Row 1 — dropdowns + date pickers
        c1, c2, c3, c4, c5, c6 = st.columns([1.1, 1.1, 1.1, 1.4, 1, 1])
        with c1:
            platforms = ["All"] + sorted(df["Platform"].unique().tolist())
            f_platform = st.selectbox("Platform", platforms, index=0)
        with c2:
            brand_pool = df if f_platform == "All" else df[df["Platform"] == f_platform]
            brands = ["All"] + sorted(brand_pool["Brand"].dropna().unique().tolist())
            f_brand = st.selectbox("Brand", brands, index=0)
        with c3:
            categories = ["All"] + sorted(df["Category"].unique().tolist())
            f_category = st.selectbox("Category", categories, index=0)
        with c4:
            sku_pool = df.copy()
            if f_platform != "All": sku_pool = sku_pool[sku_pool["Platform"] == f_platform]
            if f_brand != "All":    sku_pool = sku_pool[sku_pool["Brand"] == f_brand]
            if f_category != "All": sku_pool = sku_pool[sku_pool["Category"] == f_category]
            skus = ["All"] + sorted(sku_pool["SKU"].dropna().unique().tolist())
            f_sku = st.selectbox("SKU", skus, index=0)
        with c5:
            f_date_from = st.date_input("Date from", value=st.session_state.df_from,
                                        min_value=min_date, max_value=max_date)
            st.session_state.df_from = f_date_from
        with c6:
            f_date_to = st.date_input("Date to", value=st.session_state.df_to,
                                      min_value=min_date, max_value=max_date)
            st.session_state.df_to = f_date_to

        st.markdown("</div>", unsafe_allow_html=True)  # /filter-bar

        # ---------------------------------------------------------------------------
        # Apply filters
        # ---------------------------------------------------------------------------
        mask = (df["Date"].dt.date >= f_date_from) & (df["Date"].dt.date <= f_date_to)
        if f_platform != "All": mask &= df["Platform"] == f_platform
        if f_brand    != "All": mask &= df["Brand"] == f_brand
        if f_category != "All": mask &= df["Category"] == f_category
        if f_sku      != "All": mask &= df["SKU"] == f_sku
        fdf = df[mask].copy()

        # ---------------------------------------------------------------------------
        # KPI cards
        # ---------------------------------------------------------------------------
        def human(n: float) -> str:
            a = abs(n)
            if a >= 1e9: return f"{n/1e9:.2f}B"
            if a >= 1e6: return f"{n/1e6:.2f}M"
            if a >= 1e3: return f"{n/1e3:.1f}K"
            return f"{n:,.0f}"


        total_sales = fdf["Sales Val"].sum()
        total_units = fdf["Sales Qty"].sum()
        n_platforms = fdf["Platform"].nunique()
        n_skus = fdf["SKU"].nunique()
        top_platform = (
            fdf.groupby("Platform")["Sales Val"].sum().sort_values(ascending=False).index[0]
            if not fdf.empty else "—"
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
        # Charts — monthly trend & platform totals
        # ---------------------------------------------------------------------------
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

        st.markdown("<div class='sec-title'>Total sales by platform</div>", unsafe_allow_html=True)
        bars = (fdf.groupby("Platform")["Sales Val"].sum()
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

        # Category mix by platform
        st.markdown("<div class='sec-title'>Category mix by platform</div>", unsafe_allow_html=True)
        mix = (fdf.groupby(["Platform", "Category"])["Sales Val"].sum().reset_index())
        if mix.empty:
            st.info("No data for the current filters.")
        else:
            plat_order = (mix.groupby("Platform")["Sales Val"].sum()
                               .sort_values(ascending=False).index.tolist())
            fig = px.bar(
                mix, x="Category", y="Sales Val", color="Platform",
                color_discrete_map=PLATFORM_COLORS,
                category_orders={"Platform": plat_order,
                                 "Category": list(CATEGORY_PALETTE.keys())},
            )
            fig.update_layout(
                height=380, margin=dict(l=10, r=10, t=10, b=10),
                plot_bgcolor="white", barmode="group",
                yaxis=dict(gridcolor="#e5e7eb", title="Sales value (SAR)"),
                xaxis=dict(title=""),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ----- Category × Platform trendline (Top 5 platforms) -----
        st.markdown("<div class='sec-title'>Category trend by platform — top 5 platforms</div>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Monthly sales value split by category, one panel per category, lines colored by platform.</div>", unsafe_allow_html=True)
        top5 = (fdf.groupby("Platform")["Sales Val"].sum()
                     .sort_values(ascending=False).head(5).index.tolist())
        cat_trend = (fdf[fdf["Platform"].isin(top5)]
                     .groupby(["Platform", "Category", "Month"])["Sales Val"].sum().reset_index())
        if cat_trend.empty:
            st.info("No data for the current filters.")
        else:
            cat_trend["Month"] = pd.Categorical(cat_trend["Month"], categories=MONTH_ORDER, ordered=True)
            cat_trend = cat_trend.sort_values("Month")
            cats_present = [c for c in CATEGORY_PALETTE if c in cat_trend["Category"].unique()]
            fig = px.line(
                cat_trend, x="Month", y="Sales Val", color="Platform", markers=True,
                facet_col="Category", facet_col_wrap=5,
                color_discrete_map=PLATFORM_COLORS,
                category_orders={"Platform": top5, "Category": cats_present},
            )
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1],
                                                       font=dict(size=13, color=NAVY_DARK)))
            fig.update_yaxes(matches=None, showticklabels=True, gridcolor="#e5e7eb", title="")
            fig.update_xaxes(title="")
            fig.update_layout(
                height=340, margin=dict(l=10, r=10, t=40, b=10),
                plot_bgcolor="white", legend_title_text="Platform",
            )
            st.plotly_chart(fig, use_container_width=True)

        # ---------------------------------------------------------------------------
        # Year-over-Year comparison — driven by the date-range filter
        # ---------------------------------------------------------------------------
        # Determine which months the user selected via the date picker
        _sel_months: list[tuple[int, int]] = []  # (year, month_num) pairs from filter
        if fdf["Date"].notna().any():
            _sel_ym = fdf[["Year", "MonthNum"]].drop_duplicates()
            _sel_months = list(zip(_sel_ym["Year"].astype(int), _sel_ym["MonthNum"].astype(int)))
            _sel_months.sort()

        # We only compare months from the *latest year* in the selection against the prior year
        _sel_years = sorted(set(y for y, _ in _sel_months))
        if _sel_years:
            cy_year = _sel_years[-1]
            py_year = cy_year - 1
            cy_month_nums = sorted(set(mn for y, mn in _sel_months if y == cy_year))
        else:
            cy_year = None
            py_year = None
            cy_month_nums = []

        # Base data — respects Platform/Brand/Category/SKU filters but NOT date range
        yoy_base = df.copy()
        if f_platform != "All": yoy_base = yoy_base[yoy_base["Platform"] == f_platform]
        if f_brand    != "All": yoy_base = yoy_base[yoy_base["Brand"] == f_brand]
        if f_category != "All": yoy_base = yoy_base[yoy_base["Category"] == f_category]
        if f_sku      != "All": yoy_base = yoy_base[yoy_base["SKU"] == f_sku]

        yoy_rows: list[dict] = []

        has_py = cy_year is not None and py_year in yoy_base["Year"].unique()

        if not cy_month_nums:
            pass  # nothing selected — skip silently
        elif not has_py:
            st.markdown("<div class='sec-title' style='margin-top:28px;'>Year-over-Year comparison</div>", unsafe_allow_html=True)
            st.info(f"No {py_year} data available to compare against.")
        else:
            st.markdown("<div class='sec-title' style='margin-top:28px;'>Year-over-Year comparison</div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='sec-sub'>Comparing each selected month of the current year against the "
                "same month of the prior year. Partial months are day-matched automatically.</div>",
                unsafe_allow_html=True,
            )

            cy_months_abr = [MONTH_NUM_TO_ABR[mn] for mn in cy_month_nums
                             if mn in MONTH_NUM_TO_ABR]

            for m in cy_months_abr:
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
                # --- summary table ---
                def fmt_pct(p):
                    if p is None or pd.isna(p):
                        return "<span style='color:#9ca3af'>—</span>"
                    arrow = "▲" if p >= 0 else "▼"
                    color = "#00A651" if p >= 0 else "#E00034"
                    return f"<span style='color:{color};font-weight:700'>{arrow} {p:+.1f}%</span>"

                def fmt_delta(v):
                    if v == 0 or pd.isna(v):
                        return "<span style='color:#9ca3af'>—</span>"
                    color = "#00A651" if v >= 0 else "#E00034"
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

                # --- YoY by platform chart for EACH selected month ---
                for row in yoy_rows:
                    m = row["Month"]
                    cy_slice = yoy_base[(yoy_base["Year"] == cy_year) & (yoy_base["Month"] == m)]
                    max_day = int(cy_slice["Day"].max())

                    cy_plat = cy_slice.groupby("Platform")["Sales Val"].sum()
                    py_plat = (yoy_base[(yoy_base["Year"] == py_year) &
                                        (yoy_base["Month"] == m) &
                                        (yoy_base["Day"] <= max_day)]
                               .groupby("Platform")["Sales Val"].sum())

                    plat_df = pd.DataFrame({f"{cy_year}": cy_plat, f"{py_year}": py_plat}).fillna(0)
                    plat_df = plat_df.loc[plat_df.sum(axis=1).sort_values(ascending=False).index]

                    if plat_df.empty:
                        continue
                    st.markdown(
                        f"<div class='sec-title' style='margin-top:18px;'>{m} YoY by platform "
                        f"<span style='font-size:13px;color:{MUTED};font-weight:500'>(1–{max_day}, "
                        f"{cy_year} vs {py_year})</span></div>",
                        unsafe_allow_html=True,
                    )
                    fig = go.Figure()
                    py_colors = [PLATFORM_COLORS.get(p, "#9CA3AF") for p in plat_df.index]
                    cy_colors = [PLATFORM_COLORS.get(p, "#9CA3AF") for p in plat_df.index]
                    fig.add_bar(name=str(py_year), x=plat_df.index, y=plat_df[str(py_year)],
                                marker_color=py_colors, marker_opacity=0.45,
                                text=[human(v) for v in plat_df[str(py_year)]], textposition="outside")
                    fig.add_bar(name=str(cy_year), x=plat_df.index, y=plat_df[str(cy_year)],
                                marker_color=cy_colors,
                                text=[human(v) for v in plat_df[str(cy_year)]], textposition="outside")
                    fig.update_layout(
                        barmode="group", height=400,
                        margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                        yaxis=dict(gridcolor="#e5e7eb", title="Sales value (SAR)"),
                        xaxis=dict(title=""), legend_title_text="Year",
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # --- Platform × Category YoY breakdown ---
                    cy_pc = (cy_slice.groupby(["Platform", "Category"])["Sales Val"].sum()
                             .reset_index().rename(columns={"Sales Val": "CY"}))
                    py_pc_slice = yoy_base[(yoy_base["Year"] == py_year) &
                                           (yoy_base["Month"] == m) &
                                           (yoy_base["Day"] <= max_day)]
                    py_pc = (py_pc_slice.groupby(["Platform", "Category"])["Sales Val"].sum()
                             .reset_index().rename(columns={"Sales Val": "PY"}))
                    pc_merged = pd.merge(cy_pc, py_pc, on=["Platform", "Category"], how="outer").fillna(0)
                    pc_merged["Δ SAR"] = pc_merged["CY"] - pc_merged["PY"]
                    pc_merged["Growth %"] = pc_merged.apply(
                        lambda r: (r["Δ SAR"] / r["PY"] * 100) if r["PY"] != 0 else None, axis=1)
                    # Sort by CY desc
                    pc_merged = pc_merged.sort_values("CY", ascending=False)

                    if not pc_merged.empty:
                        st.markdown(
                            f"<div class='sec-title' style='margin-top:14px;font-size:18px;'>{m} YoY — Platform × Category "
                            f"<span style='font-size:13px;color:{MUTED};font-weight:500'>(1–{max_day}, "
                            f"{cy_year} vs {py_year})</span></div>",
                            unsafe_allow_html=True,
                        )
                        pc_head = (f"<thead><tr><th>Platform</th><th>Category</th>"
                                   f"<th>{cy_year}</th><th>{py_year}</th>"
                                   f"<th>Δ SAR</th><th>Growth %</th></tr></thead>")
                        pc_body = []
                        for _, r in pc_merged.iterrows():
                            pc_body.append(
                                "<tr>"
                                f"<td class='row-label'>{r['Platform']}</td>"
                                f"<td class='row-label'>{r['Category']}</td>"
                                f"<td class='num'>{human(r['CY'])}</td>"
                                f"<td class='num'>{human(r['PY'])}</td>"
                                f"<td class='num'>{fmt_delta(r['Δ SAR'])}</td>"
                                f"<td class='num'>{fmt_pct(r['Growth %'])}</td>"
                                "</tr>"
                            )
                        st.markdown(
                            f"<div class='pivot-wrap'><table>{pc_head}<tbody>{''.join(pc_body)}</tbody></table></div>",
                            unsafe_allow_html=True,
                        )

        # ---------------------------------------------------------------------------
        # Pivot tables (navy-headered, styled HTML)
        # ---------------------------------------------------------------------------
        def fmt_cell(v):
            if pd.isna(v) or v == 0:
                return "<span style='color:#9ca3af'>—</span>"
            return f"<span class='num'>{human(v)}</span>"


        def render_pivot(pv: pd.DataFrame, index_cols: list[str]) -> str:
            """Render a pivot DataFrame as HTML with navy headers."""
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


        # ----- Platform × Month -----
        st.markdown(f"<h2 class='sec-title' style='margin-top:28px;'>Platform Wise Sales</h2>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Sum of Sales Val by Platform × Month</div>", unsafe_allow_html=True)

        # Build a base that respects dropdown filters but NOT the date range
        pivot_base = df.copy()
        if f_platform != "All": pivot_base = pivot_base[pivot_base["Platform"] == f_platform]
        if f_brand    != "All": pivot_base = pivot_base[pivot_base["Brand"] == f_brand]
        if f_category != "All": pivot_base = pivot_base[pivot_base["Category"] == f_category]
        if f_sku      != "All": pivot_base = pivot_base[pivot_base["SKU"] == f_sku]

        available_years = sorted(pivot_base["Year"].dropna().unique().astype(int), reverse=True)
        all_platforms = sorted(pivot_base["Platform"].dropna().unique().tolist())
        all_categories = sorted(pivot_base["Category"].dropna().unique().tolist())

        pv_col1, pv_col2 = st.columns(2)
        with pv_col1:
            pv1a, pv1b = st.columns(2)
            with pv1a:
                pv1_year = st.selectbox("Year", available_years, index=0, key="pv1_year")
            with pv1b:
                pv1_months_in_year = [m for m in MONTH_ORDER
                                      if not pivot_base[(pivot_base["Year"] == pv1_year) &
                                                        (pivot_base["Month"] == m)].empty]
                pv1_month_opts = ["All"] + pv1_months_in_year
                pv1_month = st.selectbox("Month", pv1_month_opts, index=0, key="pv1_month")
        with pv_col2:
            pv1_platforms = st.multiselect("Platforms", all_platforms, default=all_platforms, key="pv1_plat")

        pv1_data = pivot_base[pivot_base["Year"] == pv1_year]
        if pv1_month != "All":
            pv1_data = pv1_data[pv1_data["Month"] == pv1_month]
        if pv1_platforms:
            pv1_data = pv1_data[pv1_data["Platform"].isin(pv1_platforms)]

        plat_month = (pv1_data.pivot_table(index="Platform", columns="Month",
                                      values="Sales Val", aggfunc="sum", fill_value=0)
                         .reindex(columns=MONTH_ORDER, fill_value=0))
        plat_month = plat_month.loc[plat_month.sum(axis=1).sort_values(ascending=False).index]
        st.markdown(render_pivot(plat_month, ["Platform"]), unsafe_allow_html=True)

        # ----- Platform × Category × Month -----
        st.markdown(f"<h2 class='sec-title' style='margin-top:28px;'>Platform-Category Wise Sales</h2>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Sum of Sales Val by Platform → Category × Month</div>", unsafe_allow_html=True)

        pv2_col1, pv2_col2 = st.columns(2)
        with pv2_col1:
            pv2a, pv2b = st.columns(2)
            with pv2a:
                pv2_year = st.selectbox("Year", available_years, index=0, key="pv2_year")
            with pv2b:
                pv2_months_in_year = [m for m in MONTH_ORDER
                                      if not pivot_base[(pivot_base["Year"] == pv2_year) &
                                                        (pivot_base["Month"] == m)].empty]
                pv2_month_opts = ["All"] + pv2_months_in_year
                pv2_month = st.selectbox("Month", pv2_month_opts, index=0, key="pv2_month")
        with pv2_col2:
            pv2_platforms = st.multiselect("Platforms", all_platforms, default=all_platforms, key="pv2_plat")
        pv2_categories = st.multiselect("Categories", all_categories, default=all_categories, key="pv2_cat")

        pv2_data = pivot_base[pivot_base["Year"] == pv2_year]
        if pv2_month != "All":
            pv2_data = pv2_data[pv2_data["Month"] == pv2_month]
        if pv2_platforms:
            pv2_data = pv2_data[pv2_data["Platform"].isin(pv2_platforms)]
        if pv2_categories:
            pv2_data = pv2_data[pv2_data["Category"].isin(pv2_categories)]

        plat_cat_month = (pv2_data.pivot_table(index=["Platform", "Category"], columns="Month",
                                          values="Sales Val", aggfunc="sum", fill_value=0)
                             .reindex(columns=MONTH_ORDER, fill_value=0))
        # order platforms by total sales desc
        plat_totals = plat_cat_month.groupby(level=0).sum().sum(axis=1).sort_values(ascending=False)
        plat_cat_month = plat_cat_month.reindex(plat_totals.index, level=0)
        st.markdown(render_pivot(plat_cat_month, ["Platform", "Category"]), unsafe_allow_html=True)

        # ---------------------------------------------------------------------------
        # Volumes view — focus SKUs
        # ---------------------------------------------------------------------------
        # Each bucket is either an explicit SKU list (exact ItemSubGroupDescription match)
        # or an ItemGroupName (sums all variants, e.g. all flavours of 125ml flavoured milk).
        VOLUME_BUCKETS: dict[str, dict] = {
            "Whole Milk 1L":          {"sku": ["WHOLE MILK RECAP12X1000ML"]},
            "Whole Milk 2L":          {"sku": ["WHOLE MILK 6X2000 CC (PROMO)"]},
            "Whole Milk Pack of 4":   {"sku": ["WHOLE MILK 3X(4X1L)"]},
            "Whole Milk 200ml":       {"sku": ["WHOLE MILK 24X200ML"]},
            "Flavoured Milk 125ml":   {"group": "Flavoured Milk 125ml."},   # all flavours
            "Flavoured Milk 200ml":   {"group": "Flavoured Milk 200ml."},   # closest to 250ml — no 250ml in range
            "Tomato Paste 135g":      {"sku": ["TOMATO PASTE 48X135 GM", "Tomato Paste Organic 6x4x135gm"]},
        }


        def bucket_mask(data: pd.DataFrame, spec: dict) -> pd.Series:
            if "sku" in spec:
                return data["ItemSubGroupDescription"].isin(spec["sku"])
            return data["ItemGroupName"] == spec["group"]


        st.markdown(f"<h2 class='sec-title' style='margin-top:32px;'>Volumes View — Focus SKUs</h2>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Units sold per platform per month for focus SKUs. 'Flavoured Milk' buckets sum across all flavours.</div>", unsafe_allow_html=True)

        # Platform selector for volumes
        vol_platforms_avail = sorted(fdf["Platform"].dropna().unique().tolist())
        vol_platform = st.selectbox("Platform", ["All"] + vol_platforms_avail, index=0, key="vol_plat")
        vol_base = fdf if vol_platform == "All" else fdf[fdf["Platform"] == vol_platform]

        vol_rows: list[dict] = []
        for label, spec in VOLUME_BUCKETS.items():
            sub = vol_base[bucket_mask(vol_base, spec)]
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
            # Render as the same navy-header pivot style + a Total column
            months_present = [m for m in MONTH_ORDER if vol_df[m].sum() > 0]
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

            # Platform breakdown table — for the selected SKUs, show units by platform
            st.markdown("<div class='sec-title' style='margin-top:18px;'>Platform breakdown</div>", unsafe_allow_html=True)
            plat_vol_rows = []
            for label, spec in VOLUME_BUCKETS.items():
                sub = fdf[bucket_mask(fdf, spec)]  # always full (not filtered by vol_platform)
                if sub.empty:
                    continue
                by_plat = sub.groupby("Platform")["Sales Qty"].sum().sort_values(ascending=False)
                for plat, qty in by_plat.items():
                    if qty == 0:
                        continue
                    plat_vol_rows.append({"Focus SKU": label, "Platform": plat, "Units": qty})

            if plat_vol_rows:
                pvol_df = pd.DataFrame(plat_vol_rows)
                # Pivot: SKU rows × Platform columns
                pvol_pivot = pvol_df.pivot_table(index="Focus SKU", columns="Platform",
                                                 values="Units", aggfunc="sum", fill_value=0)
                # Order platforms by total units desc
                plat_order = pvol_pivot.sum().sort_values(ascending=False).index.tolist()
                pvol_pivot = pvol_pivot[plat_order]
                # Order SKUs by VOLUME_BUCKETS order
                sku_order = [k for k in VOLUME_BUCKETS if k in pvol_pivot.index]
                pvol_pivot = pvol_pivot.reindex(sku_order)

                phead = "<thead><tr><th>Focus SKU</th>" + \
                        "".join(f"<th>{p}</th>" for p in plat_order) + "</tr></thead>"
                pbody = []
                for idx, row in pvol_pivot.iterrows():
                    cells = "".join(f"<td class='num'>{fmt_cell(row[p])}</td>" for p in plat_order)
                    pbody.append(f"<tr><td class='row-label'>{idx}</td>{cells}</tr>")
                st.markdown(
                    f"<div class='pivot-wrap'><table>{phead}<tbody>{''.join(pbody)}</tbody></table></div>",
                    unsafe_allow_html=True,
                )

            st.caption("Note: Flavoured Milk 250ml is not a current SADAFCO online-range SKU; Flavoured Milk 200ml shown as the closest match.")

        # ===========================================================================
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
                fdf[["Date", "Platform", "Category", "Brand", "SKU",
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

# ===========================================================================
# TAB 2 — PRICING
# ===========================================================================
with tab_pricing:
    # ---- PRICING SECTION ----
    if price_df is not None and not price_df.empty:
        st.markdown(
            f"<div class='saudia-title' style='text-align:center;'>Pricing</div>"
            f"<div class='sec-sub' style='text-align:center;'>Average prices (SAR) by Brand × Platform, with daily change.</div>",
            unsafe_allow_html=True,
        )

        # Filters
        pr_c1, pr_c2, pr_c3, pr_c4, pr_c5, pr_c6 = st.columns([1, 1, 1, 1, 1.2, 1.2])
        with pr_c1:
            pr_platforms = ["All"] + sorted(price_df["Platform"].dropna().unique().tolist())
            pr_f_plat = st.selectbox("Platform", pr_platforms, index=0, key="pr_plat")
        with pr_c2:
            pr_brands = ["All"] + sorted(price_df["Brand"].dropna().unique().tolist())
            pr_f_brand = st.selectbox("Brand", pr_brands, index=0, key="pr_brand")
        with pr_c3:
            pr_cats = ["All"] + sorted(price_df["Category"].dropna().unique().tolist())
            pr_f_cat = st.selectbox("Category", pr_cats, index=0, key="pr_cat")
        with pr_c4:
            pr_types = ["All", "Brand", "Competitor"]
            pr_f_type = st.selectbox("Type", pr_types, index=0, key="pr_type")
        with pr_c5:
            pr_min_date = price_df["Date"].min().date() if price_df["Date"].notna().any() else date.today()
            pr_max_date = price_df["Date"].max().date() if price_df["Date"].notna().any() else date.today()
            pr_date_from = st.date_input("Date from", value=pr_min_date,
                                         min_value=pr_min_date, max_value=pr_max_date, key="pr_dfrom")
        with pr_c6:
            pr_date_to = st.date_input("Date to", value=pr_max_date,
                                       min_value=pr_min_date, max_value=pr_max_date, key="pr_dto")

        # --- NEW: Comparison date range ---
        pr_c7, pr_c8 = st.columns(2)
        with pr_c7:
            pr_comp_from = st.date_input("Compare from", value=pr_min_date, key="pr_cfrom")
        with pr_c8:
            pr_comp_to = st.date_input("Compare to", value=pr_max_date, key="pr_cto")

        # Apply filters
        # --- Main period ---
        pf_main = price_df.copy()
        if pr_f_plat != "All":  pf_main = pf_main[pf_main["Platform"] == pr_f_plat]
        if pr_f_brand != "All": pf_main = pf_main[pf_main["Brand"] == pr_f_brand]
        if pr_f_cat != "All":   pf_main = pf_main[pf_main["Category"] == pr_f_cat]
        if pr_f_type != "All":  pf_main = pf_main[pf_main["Type"] == pr_f_type]
        pf_main = pf_main[(pf_main["Date"].dt.date >= pr_date_from) & (pf_main["Date"].dt.date <= pr_date_to)]

        # --- Comparison period ---
        pf_comp = price_df.copy()
        if pr_f_plat != "All":  pf_comp = pf_comp[pf_comp["Platform"] == pr_f_plat]
        if pr_f_brand != "All": pf_comp = pf_comp[pf_comp["Brand"] == pr_f_brand]
        if pr_f_cat != "All":   pf_comp = pf_comp[pf_comp["Category"] == pr_f_cat]
        if pr_f_type != "All":  pf_comp = pf_comp[pf_comp["Type"] == pr_f_type]
        pf_comp = pf_comp[(pf_comp["Date"].dt.date >= pr_comp_from) & (pf_comp["Date"].dt.date <= pr_comp_to)]


        if pf_main.empty:
            st.info("No pricing data for the selected filters.")
        else:
            all_dates = sorted(pf_main["Date"].dropna().unique())
            latest = all_dates[-1] if all_dates else None
            prev = all_dates[-2] if len(all_dates) >= 2 else None

            def fmt_change(v):
                if pd.isna(v) or v == 0:
                    return f"<span style='color:#00A651;font-weight:600'>SAR 0.00</span>"
                color = "#E00034" if v < 0 else "#00A651"
                return f"<span style='color:{color};font-weight:600'>SAR {v:+.2f}</span>"


            def _price_metrics(main_df, comp_df, group_cols):
                clean_main = main_df.dropna(subset=group_cols)
                clean_comp = comp_df.dropna(subset=group_cols)

                if clean_main.empty:
                    return pd.DataFrame()

                rows = []

                grouped_main = clean_main.groupby(group_cols)
                grouped_comp = clean_comp.groupby(group_cols)

                for keys, grp_main in grouped_main:
                    if not isinstance(keys, tuple):
                        keys = (keys,)

                    avg_main = grp_main["Price"].mean()

                    # match comparison group
                    try:
                        grp_comp = grouped_comp.get_group(keys)
                        avg_comp = grp_comp["Price"].mean()
                    except KeyError:
                        avg_comp = None

                    chg = avg_main - avg_comp if avg_comp is not None else None

                    row = dict(zip(group_cols, keys))
                    row["Price"] = avg_main
                    row["Change"] = chg
                    rows.append(row)

                return pd.DataFrame(rows).sort_values(group_cols, ignore_index=True)

            def _price_cells(r):
                p = f"{r['Price']:.2f}" if pd.notna(r["Price"]) else "—"
                return (
                    f"<td class='num'>{p}</td>"
                    f"<td class='num'>{fmt_change(r['Change'])}</td>"
                )

            has_sku = "SKU" in pf_main.columns and pf_main["SKU"].notna().any()

            # ----- drill-down state -----
            if "pr_open_plats" not in st.session_state:
                st.session_state.pr_open_plats = set()
            if "pr_open_brands" not in st.session_state:
                st.session_state.pr_open_brands = set()
            if "pr_open_cats" not in st.session_state:
                st.session_state.pr_open_cats = set()

            # ----- header -----
            st.markdown(
                f"<div class='pivot-wrap' style='margin-bottom:0'><table><thead><tr>"
                f"<th style='min-width:240px;text-align:left'>Name</th>"
                f"<th>Price (SAR)</th><th>Change</th>"
                f"</tr></thead></table></div>",
                unsafe_allow_html=True,
            )

            # ===== LEVEL 1: Platforms =====
            plat_tbl = _price_metrics(pf_main, pf_comp, ["Platform"])

            for _, pr_row in plat_tbl.iterrows():
                plat = pr_row["Platform"]
                plat_open = plat in st.session_state.pr_open_plats
                icon = "▼" if plat_open else "▶"

                c1, c2 = st.columns([0.04, 0.96])
                with c1:
                    if st.button(icon, key=f"prp_{plat}"):
                        if plat_open:
                            st.session_state.pr_open_plats.discard(plat)
                            st.session_state.pr_open_brands = {
                                k for k in st.session_state.pr_open_brands
                                if not k.startswith(f"{plat}||")
                            }
                            st.session_state.pr_open_cats = {
                                k for k in st.session_state.pr_open_cats
                                if not k.startswith(f"{plat}||")
                            }
                        else:
                            st.session_state.pr_open_plats.add(plat)
                        st.rerun()
                with c2:
                    st.markdown(
                        f"<div class='pivot-wrap' style='margin:0'><table><tr>"
                        f"<td class='row-label' style='font-weight:700;min-width:230px'>{plat}</td>"
                        f"{_price_cells(pr_row)}</tr></table></div>",
                        unsafe_allow_html=True,
                    )

                if not plat_open:
                    continue

                # ===== LEVEL 2: Brands under this platform =====
                plat_data = pf_main[pf_main["Platform"] == plat]
                brand_tbl = _price_metrics(
                    pf_main[pf_main["Platform"] == plat],
                    pf_comp[pf_comp["Platform"] == plat],
                    ["Brand"]
                )

                for _, br_row in brand_tbl.iterrows():
                    brand = br_row["Brand"]
                    brand_key = f"{plat}||{brand}"
                    brand_open = brand_key in st.session_state.pr_open_brands
                    icon2 = "▼" if brand_open else "▶"

                    c_sp, c_btn, c_tbl = st.columns([0.03, 0.04, 0.93])
                    with c_btn:
                        if st.button(icon2, key=f"prb_{brand_key}"):
                            if brand_open:
                                st.session_state.pr_open_brands.discard(brand_key)
                                st.session_state.pr_open_cats = {
                                    k for k in st.session_state.pr_open_cats
                                    if not k.startswith(f"{brand_key}||")
                                }
                            else:
                                st.session_state.pr_open_brands.add(brand_key)
                            st.rerun()
                    with c_tbl:
                        st.markdown(
                            f"<div class='pivot-wrap' style='margin:0'><table><tr>"
                            f"<td class='row-label' style='padding-left:16px;min-width:214px'>{brand}</td>"
                            f"{_price_cells(br_row)}</tr></table></div>",
                            unsafe_allow_html=True,
                        )

                    if not brand_open:
                        continue

                    # ===== LEVEL 3: Categories under this brand =====
                    brand_data = plat_data[plat_data["Brand"] == brand]
                    cat_tbl = _price_metrics(
                        pf_main[(pf_main["Platform"] == plat) & (pf_main["Brand"] == brand)],
                        pf_comp[(pf_comp["Platform"] == plat) & (pf_comp["Brand"] == brand)],
                        ["Category"]
                    )

                    for _, ct_row in cat_tbl.iterrows():
                        cat = ct_row["Category"]
                        cat_key = f"{brand_key}||{cat}"
                        cat_open = cat_key in st.session_state.pr_open_cats
                        icon3 = "▼" if cat_open else "▶"

                        s_sp, s_sp2, s_btn, s_tbl = st.columns([0.03, 0.03, 0.04, 0.90])
                        with s_btn:
                            if has_sku and st.button(icon3, key=f"prc_{hash(cat_key) % 10**8}"):
                                if cat_open:
                                    st.session_state.pr_open_cats.discard(cat_key)
                                else:
                                    st.session_state.pr_open_cats.add(cat_key)
                                st.rerun()
                        with s_tbl:
                            st.markdown(
                                f"<div class='pivot-wrap' style='margin:0'><table><tr>"
                                f"<td class='row-label' style='padding-left:8px;min-width:198px;font-size:12px'>"
                                f"{cat}</td>"
                                f"{_price_cells(ct_row)}</tr></table></div>",
                                unsafe_allow_html=True,
                            )

                        if not cat_open or not has_sku:
                            continue

                        # ===== LEVEL 4: SKUs under this category =====
                        cat_data = brand_data[brand_data["Category"] == cat]
                        sku_tbl = _price_metrics(
                            pf_main[(pf_main["Platform"] == plat) & (pf_main["Brand"] == brand) & (
                                        pf_main["Category"] == cat)],
                            pf_comp[(pf_comp["Platform"] == plat) & (pf_comp["Brand"] == brand) & (
                                        pf_comp["Category"] == cat)],
                            ["SKU"]
                        )

                        for _, sk_row in sku_tbl.iterrows():
                            sku_label = str(sk_row["SKU"])
                            if " PC: Z" in sku_label:
                                sku_label = sku_label.split(" PC: Z")[0]
                            st.markdown(
                                f"<div class='pivot-wrap' style='margin:0 0 0 90px'><table><tr>"
                                f"<td class='num' style='min-width:180px;color:{MUTED};font-size:12px'>"
                                f"{sku_label}</td>"
                                f"{_price_cells(sk_row)}</tr></table></div>",
                                unsafe_allow_html=True,
                            )

            # ----- Total row -----
            if not plat_tbl.empty:
                tp = plat_tbl["Price"].mean()
                tc = plat_tbl["Change"].mean()
                st.markdown(
                    f"<div class='pivot-wrap' style='margin-top:2px'><table>"
                    f"<tr style='border-top:2px solid {NAVY}'>"
                    f"<td class='row-label' style='font-weight:700;min-width:240px'>Total</td>"
                    f"<td class='num' style='font-weight:700'>{tp:.2f}</td>"
                    f"<td class='num'>{fmt_change(tc)}</td>"
                    f"</tr></table></div>",
                    unsafe_allow_html=True,
                )
    else:
        if _dd_load_error:
            st.error(f"Failed to load pricing data: {_dd_load_error}")
        else:
            st.info("No pricing data available. Upload the Data Dashboard file (.xlsx) via the sidebar.")


# ===========================================================================
# TAB 3 — AVAILABILITY
# ===========================================================================
with tab_availability:
    # ---- AVAILABILITY SECTION ----
    if avail_df is not None and not avail_df.empty:
        st.markdown(
            f"<div class='saudia-title' style='text-align:center;'>Availability</div>"
            f"<div class='sec-sub' style='text-align:center;'>SKU availability % by Brand × Platform, with period comparison.</div>",
            unsafe_allow_html=True,
        )

        # Filters
        av_c1, av_c2, av_c3, av_c4, av_c5, av_c6 = st.columns([1, 1, 1, 1, 1.2, 1.2])
        with av_c1:
            av_platforms = ["All"] + sorted(avail_df["Platform"].dropna().unique().tolist())
            av_f_plat = st.selectbox("Platform", av_platforms, index=0, key="av_plat")
        with av_c2:
            av_stores = ["All"] + sorted(avail_df["Store"].dropna().unique().tolist())
            av_f_store = st.selectbox("Store", av_stores, index=0, key="av_store")
        with av_c3:
            av_cats = ["All"] + sorted(avail_df["Category"].dropna().unique().tolist())
            av_f_cat = st.selectbox("Category", av_cats, index=0, key="av_cat")
        with av_c4:
            av_brands = ["All"] + sorted(avail_df["Brand"].dropna().unique().tolist())
            av_f_brand = st.selectbox("Brand", av_brands, index=0, key="av_brand")
        with av_c5:
            av_min_date = avail_df["Date"].min().date() if avail_df["Date"].notna().any() else date.today()
            av_max_date = avail_df["Date"].max().date() if avail_df["Date"].notna().any() else date.today()
            av_date_from = st.date_input("Date from", value=av_min_date,
                                         min_value=av_min_date, max_value=av_max_date, key="av_dfrom")
        with av_c6:
            av_date_to = st.date_input("Date to", value=av_max_date,
                                       min_value=av_min_date, max_value=av_max_date, key="av_dto")

        # Apply filters
        af = avail_df.copy()
        if av_f_plat != "All":  af = af[af["Platform"] == av_f_plat]
        if av_f_store != "All": af = af[af["Store"] == av_f_store]
        if av_f_cat != "All":   af = af[af["Category"] == av_f_cat]
        if av_f_brand != "All": af = af[af["Brand"] == av_f_brand]
        af = af[(af["Date"].dt.date >= av_date_from) & (af["Date"].dt.date <= av_date_to)]

        if af.empty:
            st.info("No availability data for the selected filters.")
        else:
            overall_avail = af["Availability"].mean() * 100

            # KPI
            st.markdown(
                f"<div style='text-align:center;margin:16px 0;'>"
                f"<span style='font-size:48px;font-weight:700;color:{NAVY_DARK}'>{overall_avail:.0f}%</span>"
                f"<br><span style='color:{MUTED};font-size:14px;'>Availability</span></div>",
                unsafe_allow_html=True,
            )

            # ----- helpers -----
            def fmt_avail_pct(v):
                if pd.isna(v):
                    return "<span style='color:#9ca3af'>—</span>"
                color = "#E00034" if v < 60 else ("#FF9800" if v < 80 else "#00A651")
                return f"<span style='color:{color};font-weight:600'>{v:.0f}%</span>"

            def fmt_vs_period(curr, prev):
                if pd.isna(curr) or pd.isna(prev):
                    return "<span style='color:#9ca3af'>—</span>"
                diff = curr - prev
                if diff > 0:
                    return f"<span style='color:#00A651;font-weight:600'>▲ {diff:+.0f}%</span>"
                elif diff < 0:
                    return f"<span style='color:#E00034;font-weight:600'>▼ {diff:+.0f}%</span>"
                return f"<span style='color:{MUTED}'>0%</span>"

            def _avail_metrics(data, data_full, group_cols):
                if data.empty:
                    return pd.DataFrame()
                clean = data.dropna(subset=group_cols)
                if clean.empty:
                    return pd.DataFrame()
                grouped = (clean.groupby(group_cols)["Availability"]
                           .mean() * 100).round(1).reset_index()
                grouped.columns = list(group_cols) + ["Availability"]
                range_days = (av_date_to - av_date_from).days + 1
                comp_from = av_date_from - timedelta(days=range_days)
                comp_to = av_date_from - timedelta(days=1)
                af_c = data_full[(data_full["Date"].dt.date >= comp_from) &
                                 (data_full["Date"].dt.date <= comp_to)]
                if not af_c.empty:
                    clean_c = af_c.dropna(subset=group_cols)
                    if not clean_c.empty:
                        comp = (clean_c.groupby(group_cols)["Availability"]
                                .mean() * 100).round(1).reset_index()
                        comp.columns = list(group_cols) + ["Availability_comp"]
                        grouped = grouped.merge(comp, on=group_cols, how="left")
                    else:
                        grouped["Availability_comp"] = float("nan")
                else:
                    grouped["Availability_comp"] = float("nan")
                today = av_date_to
                for label, s_date in [("MTD", today.replace(day=1)),
                                      ("YTD", today.replace(month=1, day=1))]:
                    src = data_full[(data_full["Date"].dt.date >= s_date) &
                                    (data_full["Date"].dt.date <= today)]
                    if not src.empty:
                        clean_s = src.dropna(subset=group_cols)
                        if not clean_s.empty:
                            m = (clean_s.groupby(group_cols)["Availability"]
                                 .mean() * 100).round(1).reset_index()
                            m.columns = list(group_cols) + [label]
                            grouped = grouped.merge(m, on=group_cols, how="left")
                        else:
                            grouped[label] = float("nan")
                    else:
                        grouped[label] = float("nan")
                return grouped.sort_values("Availability", ignore_index=True)

            def _metric_cells(r):
                return (
                    f"<td class='num'>{fmt_avail_pct(r['Availability'])}</td>"
                    f"<td class='num'>{fmt_vs_period(r['Availability'], r.get('Availability_comp', float('nan')))}</td>"
                    f"<td class='num'>{fmt_avail_pct(r.get('MTD', float('nan')))}</td>"
                    f"<td class='num'>{fmt_avail_pct(r.get('YTD', float('nan')))}</td>"
                )

            def _clean_sku(s):
                s = str(s)
                if " PC: Z" in s:
                    return s.split(" PC: Z")[0]
                return s

            def _clean_store(s):
                return str(s).replace("_", " ").title()

            # ----- filtered full dataset -----
            af_full = avail_df.copy()
            if av_f_plat != "All":  af_full = af_full[af_full["Platform"] == av_f_plat]
            if "Store" in af_full.columns and av_f_store != "All":
                af_full = af_full[af_full["Store"] == av_f_store]
            if av_f_cat != "All":   af_full = af_full[af_full["Category"] == av_f_cat]
            if av_f_brand != "All": af_full = af_full[af_full["Brand"] == av_f_brand]

            has_store = "Store" in af.columns and af["Store"].notna().any()
            has_sku = "SKU" in af.columns and af["SKU"].notna().any()

            # ----- drill-down state -----
            if "av_open_plats" not in st.session_state:
                st.session_state.av_open_plats = set()
            if "av_open_cats" not in st.session_state:
                st.session_state.av_open_cats = set()
            if "av_open_skus" not in st.session_state:
                st.session_state.av_open_skus = set()

            # ----- header row (always visible) -----
            hdr_html = (
                f"<div class='pivot-wrap' style='margin-bottom:0'><table><thead><tr>"
                f"<th style='min-width:240px;text-align:left'>Name</th>"
                f"<th>Availability</th><th>vs Period</th><th>MTD</th><th>YTD</th>"
                f"</tr></thead></table></div>"
            )
            st.markdown(hdr_html, unsafe_allow_html=True)

            # ===== LEVEL 1: Platforms =====
            plat_table = _avail_metrics(af, af_full, ["Platform"])

            for _, pr in plat_table.iterrows():
                plat = pr["Platform"]
                plat_open = plat in st.session_state.av_open_plats
                icon = "▼" if plat_open else "▶"

                # Platform row
                c1, c2 = st.columns([0.04, 0.96])
                with c1:
                    if st.button(icon, key=f"avp_{plat}"):
                        if plat_open:
                            st.session_state.av_open_plats.discard(plat)
                            # close children too
                            st.session_state.av_open_cats = {
                                k for k in st.session_state.av_open_cats
                                if not k.startswith(f"{plat}||")
                            }
                            st.session_state.av_open_skus = {
                                k for k in st.session_state.av_open_skus
                                if not k.startswith(f"{plat}||")
                            }
                        else:
                            st.session_state.av_open_plats.add(plat)
                        st.rerun()
                with c2:
                    st.markdown(
                        f"<div class='pivot-wrap' style='margin:0'><table><tr>"
                        f"<td class='row-label' style='font-weight:700;min-width:230px'>{plat}</td>"
                        f"{_metric_cells(pr)}</tr></table></div>",
                        unsafe_allow_html=True,
                    )

                if not plat_open:
                    continue

                # ===== LEVEL 2: Categories under this platform =====
                plat_data = af[af["Platform"] == plat]
                plat_full = af_full[af_full["Platform"] == plat]
                cat_table = _avail_metrics(plat_data, plat_full, ["Category"])

                for _, cr in cat_table.iterrows():
                    cat = cr["Category"]
                    cat_key = f"{plat}||{cat}"
                    cat_open = cat_key in st.session_state.av_open_cats
                    icon2 = "▼" if cat_open else "▶"

                    c_sp, c_btn, c_tbl = st.columns([0.03, 0.04, 0.93])
                    with c_btn:
                        if has_sku and st.button(icon2, key=f"avc_{cat_key}"):
                            if cat_open:
                                st.session_state.av_open_cats.discard(cat_key)
                                st.session_state.av_open_skus = {
                                    k for k in st.session_state.av_open_skus
                                    if not k.startswith(f"{cat_key}||")
                                }
                            else:
                                st.session_state.av_open_cats.add(cat_key)
                            st.rerun()
                    with c_tbl:
                        st.markdown(
                            f"<div class='pivot-wrap' style='margin:0'><table><tr>"
                            f"<td class='row-label' style='padding-left:16px;min-width:214px'>{cat}</td>"
                            f"{_metric_cells(cr)}</tr></table></div>",
                            unsafe_allow_html=True,
                        )

                    if not cat_open or not has_sku:
                        continue

                    # ===== LEVEL 3: SKUs under this category =====
                    cat_data = plat_data[plat_data["Category"] == cat]
                    cat_full = plat_full[plat_full["Category"] == cat]
                    sku_table = _avail_metrics(cat_data, cat_full, ["SKU"])

                    for _, sr in sku_table.iterrows():
                        sku_raw = sr["SKU"]
                        sku_label = _clean_sku(sku_raw)
                        sku_key = f"{cat_key}||{sku_raw}"
                        sku_open = sku_key in st.session_state.av_open_skus
                        icon3 = "▼" if sku_open else "▶"

                        s_sp, s_sp2, s_btn, s_tbl = st.columns([0.03, 0.03, 0.04, 0.90])
                        with s_btn:
                            if has_store and st.button(icon3, key=f"avs_{hash(sku_key) % 10**8}"):
                                if sku_open:
                                    st.session_state.av_open_skus.discard(sku_key)
                                else:
                                    st.session_state.av_open_skus.add(sku_key)
                                st.rerun()
                        with s_tbl:
                            st.markdown(
                                f"<div class='pivot-wrap' style='margin:0'><table><tr>"
                                f"<td class='row-label' style='padding-left:8px;min-width:198px;font-size:12px'>"
                                f"{sku_label}</td>"
                                f"{_metric_cells(sr)}</tr></table></div>",
                                unsafe_allow_html=True,
                            )

                        if not sku_open or not has_store:
                            continue

                        # ===== LEVEL 4: Dark Stores under this SKU =====
                        sku_data = cat_data[cat_data["SKU"] == sku_raw]
                        sku_full = cat_full[cat_full["SKU"] == sku_raw]
                        store_table = _avail_metrics(sku_data, sku_full, ["Store"])

                        for _, dr in store_table.iterrows():
                            st.markdown(
                                f"<div class='pivot-wrap' style='margin:0 0 0 90px'><table><tr>"
                                f"<td class='num' style='min-width:180px;color:{MUTED};font-size:12px'>"
                                f"{_clean_store(dr['Store'])}</td>"
                                f"{_metric_cells(dr)}</tr></table></div>",
                                unsafe_allow_html=True,
                            )

            # ----- Total row -----
            if not plat_table.empty:
                ta = plat_table["Availability"].mean()
                tc = plat_table["Availability_comp"].mean()
                tm = plat_table["MTD"].mean()
                ty = plat_table["YTD"].mean()
                st.markdown(
                    f"<div class='pivot-wrap' style='margin-top:2px'><table>"
                    f"<tr style='border-top:2px solid {NAVY}'>"
                    f"<td class='row-label' style='font-weight:700;min-width:240px'>Total</td>"
                    f"<td class='num'>{fmt_avail_pct(ta)}</td>"
                    f"<td class='num'>{fmt_vs_period(ta, tc)}</td>"
                    f"<td class='num'>{fmt_avail_pct(tm)}</td>"
                    f"<td class='num'>{fmt_avail_pct(ty)}</td>"
                    f"</tr></table></div>",
                    unsafe_allow_html=True,
                )

            # ===== PLATFORM BAR CHART =====
            st.markdown("<div class='sec-title' style='margin-top:24px;'>Availability by Platform</div>",
                        unsafe_allow_html=True)
            plat_avail = (af.groupby("Platform")["Availability"].mean() * 100).round(1)
            if not plat_avail.empty:
                fig = go.Figure(go.Bar(
                    x=plat_avail.index, y=plat_avail.values,
                    marker_color=[PLATFORM_COLORS.get(p, "#9CA3AF") for p in plat_avail.index],
                    text=[f"{v:.0f}%" for v in plat_avail.values],
                    textposition="outside",
                ))
                fig.update_layout(
                    height=340, margin=dict(l=10, r=10, t=10, b=10),
                    plot_bgcolor="white",
                    yaxis=dict(gridcolor="#e5e7eb", title="Availability %", range=[0, 105]),
                    xaxis=dict(title=""),
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        if _dd_load_error:
            st.error(f"Failed to load availability data: {_dd_load_error}")
        else:
            st.info("No availability data available. Upload the Data Dashboard file (.xlsx) via the sidebar.")
