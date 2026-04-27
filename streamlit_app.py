"""
SADAFCO Online Shopping — Sales Dashboard (Optimized)

Performance fixes vs. original:
  1. Drill-down (Pricing & Availability) uses native HTML <details>/<summary>.
     Clicking a caret toggles in the browser — NO Streamlit rerun. Previously
     every click reran the whole script (incl. excel reload, chart regen, etc).
  2. Hierarchical aggregates pre-computed once per period via a single groupby
     per level. Replaces the O(rows × levels) repeated-groupby pattern.
  3. MTD / YTD / comparison-period slices filtered ONCE up front, not per-row.
  4. The full drill-down tree is rendered as a single st.markdown HTML string
     instead of dozens of st.columns + st.button + st.markdown calls per row.
  5. Platform / Brand / Category / SKU columns set to Categorical dtype for
     faster groupbys.
  6. _price_metrics / _avail_metrics vectorized via merge instead of Python
     loops over groupby objects.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
import datetime as _dt
import re as _re

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Page config
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

PLATFORM_COLORS = {
    "Ninja":         "#39C3CC",
    "Keeta":         "#FFD600",
    "Amazon":        "#FF9900",
    "Hungerstation": "#FF5722",
    "Noon":          "#F6EA00",
    "Careem":        "#00B140",
    "Nana":          "#7C3AED",
    "Doosaha":       "#0EA5E9",
    "To you":        "#EC4899",
    "Rabbit":        "#F43F5E",
    "Other":         "#9CA3AF",
}

CATEGORY_PALETTE = {
    "Frozen":   NAVY,
    "Snacks":   NAVY,
    "Drinks":   NAVY,
    "Dairy":    NAVY,
    "Culinary": NAVY,
}

# ---------------------------------------------------------------------------
# CSS — includes the new drill-tree styles for HTML <details> rendering
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
      /* base */
      .stApp {{ background: {BG}; }}
      header[data-testid="stHeader"] {{ background: transparent; }}
      .block-container {{ padding-top: 1rem; padding-bottom: 2rem; }}

      .saudia-hero {{
        background: linear-gradient(180deg, #ffffff 0%, #ffffff 100%);
        border-bottom: 1px solid #e5e7eb;
        padding: 14px 18px 16px 18px; margin-bottom: 0;
      }}
      .saudia-title {{
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 34px; font-weight: 700; color: #111827; margin: 0;
      }}
      .saudia-sub {{ color: {MUTED}; font-size: 13px; margin-top: 2px; }}

      .filter-bar {{ padding: 8px 2px 0 2px; }}

      .kpi-card {{
        background: #fff; border: 1px solid #e5e7eb;
        border-left: 4px solid {SAUDIA_BLUE};
        border-radius: 6px; padding: 14px 16px; height: 100%;
      }}
      .kpi-label {{ color: {MUTED}; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }}
      .kpi-value {{ color: {NAVY_DARK}; font-size: 26px; font-weight: 700; margin-top: 4px; }}

      .sec-title {{
        font-family: Georgia, serif;
        font-size: 22px; font-weight: 700; color: {NAVY_DARK};
        margin: 22px 0 4px 0;
      }}
      .sec-sub {{ color: {MUTED}; font-size: 13px; margin-bottom: 8px; }}

      /* pivot tables */
      .pivot-wrap table {{
          border-collapse: collapse; width: 100%; font-size: 13px;
          table-layout: fixed;
      }}
      .pivot-wrap thead th {{
        background: {NAVY}; color: #fff; text-align: center;
        padding: 10px 8px; font-weight: 600;
        border-right: 1px solid {NAVY_DARK};
      }}
      .pivot-wrap tbody td {{ padding: 8px 10px; border-bottom: 1px solid #e5e7eb; }}
      .pivot-wrap tbody tr:nth-child(even) {{ background: #f9fafb; }}
      .pivot-wrap .row-label {{ font-weight: 600; color: {NAVY_DARK}; text-align: left; }}
      .pivot-wrap .num {{ text-align: right; font-variant-numeric: tabular-nums; width: 110px; white-space: nowrap; }}
      .pos {{ color: {GREEN}; font-weight: 600; }}
      .neg {{ color: {RED};   font-weight: 600; }}

      /* ============== drill-tree (Pricing / Availability) ============== */
      .drill-tree {{
          font-size: 13px; border: 1px solid #e5e7eb; border-radius: 6px;
          overflow: hidden; margin-top: 8px;
      }}
      .drill-tree details {{ margin: 0; }}
      .drill-tree summary {{
          cursor: pointer; list-style: none; user-select: none; outline: none;
      }}
      .drill-tree summary::-webkit-details-marker {{ display: none; }}
      .drill-tree summary::marker {{ display: none; }}

      .drill-tree .row {{
          display: grid; align-items: center;
          padding: 7px 12px; border-bottom: 1px solid #f1f5f9;
          transition: background-color .08s ease;
      }}
      .drill-tree summary:hover > .row {{ background: #f9fafb; }}
      .drill-tree .header {{
          background: {NAVY}; color: #fff; font-weight: 600;
          border-bottom: none;
      }}
      .drill-tree .header span {{ padding: 4px 0; }}

      .drill-tree .row .name {{
          font-weight: 600; color: {NAVY_DARK};
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }}
      .drill-tree .row .num {{
          text-align: right; font-variant-numeric: tabular-nums;
      }}
      .drill-tree .caret {{ display: inline-block; width: 14px; color: {NAVY_DARK}; font-size: 9px; }}
      .drill-tree .caret::before {{ content: "▶"; }}
      .drill-tree details[open] > summary > .row > .caret::before {{ content: "▼"; }}
      .drill-tree .caret-empty {{ display: inline-block; width: 14px; }}

      .drill-tree .level-0 {{ padding-left: 12px; }}
      .drill-tree .level-1 {{ padding-left: 36px; background: #fafafa; }}
      .drill-tree .level-2 {{ padding-left: 60px; background: #f5f7fb; }}
      .drill-tree .level-3 {{ padding-left: 84px; background: #f0f3fa; font-size: 12px; color: {MUTED}; }}
      .drill-tree .level-3 .name {{ font-weight: 500; color: {MUTED}; }}
      .drill-tree .level-4 {{ padding-left: 108px; background: #e8edf6; font-size: 12px; color: {MUTED}; }}
      .drill-tree .level-4 .name {{ font-weight: 500; color: {MUTED}; }}

      .drill-tree .total {{
          background: #fff !important; border-top: 2px solid {NAVY};
          font-weight: 700;
      }}
      .drill-tree .total .name {{ font-weight: 700; }}

      /* 3-column tree (pricing) */
      .drill-tree.cols-3 .row {{
          grid-template-columns: minmax(220px, 2.4fr) minmax(90px, 110px) minmax(110px, 130px);
          gap: 8px;
      }}
      /* 5-column tree (availability) */
      .drill-tree.cols-5 .row {{
          grid-template-columns: minmax(220px, 2.4fr) repeat(4, minmax(90px, 120px));
          gap: 8px;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Maps + helpers
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
MONTH_NUM_TO_ABR = {i + 1: m for i, m in enumerate(MONTH_ORDER)}
MONTH_ABR_TO_NUM = {m: i + 1 for i, m in enumerate(MONTH_ORDER)}

_PLATFORM_KW: list[tuple] = [
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


def _infer_platform(name: str) -> str:
    for pat, plat in _PLATFORM_KW:
        if pat.search(str(name)):
            return plat
    return "Other"


def _to_categorical(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convert columns to categorical dtype in-place; cheap groupby boost."""
    for c in cols:
        if c in df.columns and df[c].dtype != "category":
            df[c] = df[c].astype("category")
    return df


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

import time
import numpy as np
import pandas as pd
from pathlib import Path
def process_mfilterit_av_pr_file(PRICING_FILE,OSA_FILE):
# ── CONFIG ─────────────────────────────────────────────────────────────────

    OWN_BRANDS          = ["Saudia", "Crispy"]              # → Type = "Brand"
    TRACKED_COMPETITORS = ["Almarai", "Nadec"]              # → Type = "Competitor"

    PLATFORM_MAP = {
        "quickmarket_ksa":      "Hunger Station",
        "noon_minutes_ksa_app": "Noon",
    }

    t0 = time.perf_counter()

    # ── 1. AVAILABILITY  (OSA wide → long) ─────────────────────────────────────
    # OSA "Base Data" has one row per (SKU, store) with one column per date.
    # Strategy: filter to tracked brands BEFORE melting (≈ 5× speed-up on 14k×46),
    # then melt the date columns down, drop the days where the platform didn't
    # scrape that store (NaN), and rename to dashboard schema.

    ID_COLS = ["platform", "brand", "sub_category", "oem_code",
               "product_code", "title_local", "pincode"]

    osa = pd.read_excel(OSA_FILE, sheet_name="Base Data", engine="calamine")
    date_cols = [c for c in osa.columns if hasattr(c, "year")]   # datetime cols only

    osa = osa.loc[osa["brand"].isin(OWN_BRANDS), ID_COLS + date_cols]

    a = (osa.melt(id_vars=ID_COLS, value_vars=date_cols,
                  var_name="Date", value_name="Availability")
            .dropna(subset=["Availability"]))

    availability = pd.DataFrame({
        "Brand ":       a["brand"].astype("string"),
        "Category":     a["sub_category"].astype("string"),
        "Unit Barcode": pd.to_numeric(a["oem_code"], errors="coerce"),
        "SKU":          a["title_local"].astype("string") + " PC: " + a["product_code"].astype("string"),
        "Platform":     a["platform"].map(PLATFORM_MAP).astype("string"),
        "Store":        a["pincode"].astype("string"),
        "Date":         pd.to_datetime(a["Date"]).dt.strftime("%d/%m/%Y"),
        "Availability": a["Availability"].astype("float64"),
    })

    t1 = time.perf_counter()
    print(f"Availability built in {t1-t0:5.2f}s · {len(availability):>7,} rows")

    # ── 2. PRICE  (per-store rows → per-(SKU, platform, date) mean MRP) ───────
    # `usecols` keeps only the 9 columns we need from a 33-col, 115k-row sheet.
    # We aggregate MRP (the listed price) — that's what the existing dashboard
    # tracks. Switch to "asp" if you'd rather track post-discount selling price.

    PRICE_USECOLS = ["inserted_date", "platform", "oem_code", "product_code",
                     "brand", "brand_type", "sub_category", "title_local", "mrp"]

    pricing = pd.read_excel(PRICING_FILE, sheet_name="Base data",
                            usecols=PRICE_USECOLS, engine="calamine")
    pricing = pricing[pricing["brand"].isin(OWN_BRANDS + TRACKED_COMPETITORS)]

    GROUP = ["inserted_date", "platform", "brand", "brand_type",
             "sub_category", "oem_code", "product_code", "title_local"]
    agg = (pricing.groupby(GROUP, as_index=False, observed=True)
                  .agg(Price=("mrp", "mean")))

    price_df = pd.DataFrame({
        "Brand ":       agg["brand"].astype("string"),
        "Category":     agg["sub_category"].astype("string"),
        "Unit Barcode": np.nan,                                  # left blank to match existing schema
        "SKU":          agg["title_local"].astype("string") + " PC: " + agg["product_code"].astype("string"),
        "Platform":     agg["platform"].map(PLATFORM_MAP).astype("string"),
        "Date":         pd.to_datetime(agg["inserted_date"]).dt.strftime("%d/%m/%Y"),
        "Price":        agg["Price"].astype("float64"),
        "Type":         np.where(agg["brand_type"].eq("Own"), "Brand", "Competitor"),
    })
    return price_df,availability

@st.cache_data(show_spinner="Loading historic file…")
def load_historic(path_or_buffer) -> pd.DataFrame:
    xl = pd.ExcelFile(path_or_buffer)
    sheet = xl.sheet_names[0]
    df = pd.read_excel(xl, sheet_name=sheet)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={
        "Categroy": "ItemCategory",
        "ItemSubGroup": "ItemGroupName",
        "ItemSubGroupDesc": "ItemSubGroupDescription",
        "SKU": "AlternateCode",
        "Gross Sales Amount": "Sales Val",
    })
    df["Platform"] = df["CustomerName"].astype(str).map(_infer_platform)
    df["Category"] = df["ItemCategory"].map(CATEGORY_MAP).fillna("Other")
    df["Brand"] = df["ItemGroupName"].astype(str)
    df["SKU_label"] = df["ItemSubGroupDescription"].astype(str)
    df["MonthNum"] = df["Month"].astype(int)
    df["Month"] = df["MonthNum"].map(MONTH_NUM_TO_ABR)
    df["Day"] = 15
    df["Date"] = pd.to_datetime(
        dict(year=df["Year"], month=df["MonthNum"], day=df["Day"]),
        errors="coerce",
    )
    df["Sales Val"] = pd.to_numeric(df["Sales Val"], errors="coerce").fillna(0.0)
    df["Sales Qty"] = pd.to_numeric(df["Sales Qty"], errors="coerce").fillna(0.0)
    out = df[["Year", "Month", "MonthNum", "Day", "Date",
              "DepotName", "CustomerName", "Platform",
              "ItemCategory", "ItemGroupName", "ItemSubGroupDescription",
              "AlternateCode", "Category", "Brand", "SKU_label",
              "Sales Val", "Sales Qty"]].copy()
    return _to_categorical(out, ["Platform", "Category", "Brand"])


@st.cache_data(show_spinner="Loading MTD file…")
def load_mtd(path_or_buffer) -> pd.DataFrame:
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
    out = df[["Year", "Month", "MonthNum", "Day", "Date",
              "DepotName", "CustomerName", "Platform",
              "ItemCategory", "ItemGroupName", "ItemSubGroupDescription",
              "AlternateCode", "Category", "Brand", "SKU_label",
              "Sales Val", "Sales Qty"]].copy()
    return _to_categorical(out, ["Platform", "Category", "Brand"])


@st.cache_data(show_spinner=False)
def merge_historic_mtd(hist: pd.DataFrame, mtd: pd.DataFrame) -> pd.DataFrame:
    mtd_periods = mtd[["Year", "MonthNum"]].drop_duplicates()
    mtd_keys = set(zip(mtd_periods["Year"].astype(int),
                       mtd_periods["MonthNum"].astype(int)))
    hist_keys = list(zip(hist["Year"].astype(int), hist["MonthNum"].astype(int)))
    keep = [k not in mtd_keys for k in hist_keys]
    hist_filtered = hist.loc[keep]
    out = pd.concat([hist_filtered, mtd], ignore_index=True)
    return _to_categorical(out, ["Platform", "Category", "Brand"])


def _parse_date_raw(v):
    if pd.isna(v):
        return pd.NaT
    if isinstance(v, str):
        return pd.to_datetime(v, dayfirst=True, errors="coerce")
    if isinstance(v, (_dt.datetime, pd.Timestamp)):
        return pd.Timestamp(v)
    return pd.NaT


def _fix_dates_column(series: pd.Series) -> pd.Series:
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


@st.cache_data(show_spinner="Loading pricing data…")
def load_pricing(df) -> pd.DataFrame:
    #df = pd.read_excel(path_or_buffer, sheet_name="Price")
    df.columns = [c.strip() for c in df.columns]
    df["Date"] = _fix_dates_column(df["Date"])
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    return _to_categorical(df, ["Platform", "Brand", "Category", "Type"])


@st.cache_data(show_spinner="Loading availability data…")
def load_availability(df) -> pd.DataFrame:
    #df = pd.read_excel(path_or_buffer, sheet_name="Availability")
    df.columns = [c.strip() for c in df.columns]
    df["Date"] = _fix_dates_column(df["Date"])
    df["Availability"] = pd.to_numeric(df["Availability"], errors="coerce")
    return _to_categorical(df, ["Platform", "Brand", "Category", "Store"])


@st.cache_data(show_spinner="Loading Keeta tracker…")
def load_keeta_tracker(path_or_buffer):
    xl = pd.ExcelFile(path_or_buffer)
    loc_raw = pd.read_excel(xl, sheet_name="Locations Key", header=None)
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
    snap_date = pd.Timestamp(date.today() - timedelta(days=1))

    def _keeta_brand(sku):
        s = str(sku).lower()
        for kw, brand in [("saudia","Saudia"),("nadec","Nadec"),("almarai","Almarai"),
                          ("al safi","Al Safi"),("lays","Lays"),("al batal","Al Batal"),
                          ("pringles","Pringles"),("baskin","Baskin Robbins"),
                          ("kwality","Kwality"),("nada","Nada"),("luna","Luna"),
                          ("al alali","Al Alali")]:
            if kw in s: return brand
        return "Other"

    def _keeta_category(sku):
        s = str(sku).lower()
        for kw, cat in [("milk","Milk"),("ice cream","Ice Cream"),("sandwich","Ice Cream"),
                        ("tomato paste","Paste"),("paste","Paste"),("ketchup","Ketchup"),
                        ("yoghurt","Yoghurt"),("yogurt","Yoghurt"),
                        ("evaporated","Evaporated Milk"),("pizza sauce","Sauce"),("sauce","Sauce")]:
            if kw in s: return cat
        if any(kw in s for kw in ("chips","rings","letters","cheese balls")):
            return "Snacks"
        return "Other"

    raw["Brand"] = raw["SKU"].apply(_keeta_brand)
    raw["Category"] = raw["SKU"].apply(_keeta_category)
    raw["Type"] = raw["Brand"].apply(lambda b: "Brand" if b in ("Saudia","Crispy") else "Competitor")
    raw["Platform"] = "Keeta"
    raw["Date"] = snap_date

    keeta_price = raw[["Date","Platform","Brand","Category","SKU",
                       "Store","City","Type","Price"]].copy()
    keeta_price["Price"] = pd.to_numeric(keeta_price["Price"], errors="coerce")
    keeta_avail = raw[["Date","Platform","Brand","Category","SKU",
                       "Store","City","Availability"]].copy()
    keeta_avail["Availability"] = pd.to_numeric(keeta_avail["Availability"], errors="coerce")
    return keeta_price, keeta_avail


@st.cache_data(show_spinner="Loading Ninja tracker…")
def load_ninja_tracker(path_or_buffer):
    """Load the Ninja Manual Tracker — same output schema as Keeta so the
    two can be concatenated transparently into price_df / avail_df.

    Layout differences vs Keeta:
      - Column A is empty on every sheet (data starts at column B). We use
        usecols="B:F" so we only pick up SKU, Availability, Price,
        Discounted Price, Discount Percentage and ignore the small legend
        on columns H–I.
      - Sheet names use " - " separator (e.g. "Khobar - Danah") so the city
        is just the first token. The Locations Key sheet uses a different
        format ("Khobar Danah") so we don't need to consult it.
      - Brand/category inference is the same as Keeta — the SKU naming
        convention is identical across the two trackers.
    """
    xl = pd.ExcelFile(path_or_buffer)
    rows = []
    for sheet in xl.sheet_names:
        if sheet == "Locations Key":
            continue
        sdf = pd.read_excel(xl, sheet_name=sheet, usecols="B:F", header=0)
        sdf.columns = [str(c).strip() for c in sdf.columns]
        # Empty rows separate brand groups within each sheet — drop them.
        sdf = sdf.dropna(subset=["SKU"])
        sdf["Store"] = sheet
        sdf["City"] = sheet.split(" - ")[0].strip() if " - " in sheet else "Unknown"
        rows.append(sdf)

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    raw = pd.concat(rows, ignore_index=True)
    raw = raw.dropna(subset=["SKU"])
    snap_date = pd.Timestamp(date.today() - timedelta(days=1))

    def _ninja_brand(sku):
        s = str(sku).lower()
        for kw, brand in [("saudia","Saudia"),("nadec","Nadec"),("almarai","Almarai"),
                          ("al safi","Al Safi"),("lays","Lays"),("al batal","Al Batal"),
                          ("pringles","Pringles"),("baskin","Baskin Robbins"),
                          ("kwality","Kwality"),("nada","Nada"),("luna","Luna"),
                          ("al alali","Al Alali")]:
            if kw in s: return brand
        return "Other"

    def _ninja_category(sku):
        s = str(sku).lower()
        for kw, cat in [("milk","Milk"),("ice cream","Ice Cream"),("sandwich","Ice Cream"),
                        ("tomato paste","Paste"),("paste","Paste"),("ketchup","Ketchup"),
                        ("yoghurt","Yoghurt"),("yogurt","Yoghurt"),
                        ("evaporated","Evaporated Milk"),("pizza sauce","Sauce"),("sauce","Sauce")]:
            if kw in s: return cat
        if any(kw in s for kw in ("chips","rings","letters","cheese balls")):
            return "Snacks"
        return "Other"

    raw["Brand"] = raw["SKU"].apply(_ninja_brand)
    raw["Category"] = raw["SKU"].apply(_ninja_category)
    raw["Type"] = raw["Brand"].apply(lambda b: "Brand" if b in ("Saudia","Crispy") else "Competitor")
    raw["Platform"] = "Ninja"
    raw["Date"] = snap_date

    ninja_price = raw[["Date","Platform","Brand","Category","SKU",
                       "Store","City","Type","Price"]].copy()
    ninja_price["Price"] = pd.to_numeric(ninja_price["Price"], errors="coerce")
    ninja_avail = raw[["Date","Platform","Brand","Category","SKU",
                       "Store","City","Availability"]].copy()
    ninja_avail["Availability"] = pd.to_numeric(ninja_avail["Availability"], errors="coerce")
    return ninja_price, ninja_avail


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    """
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
# Sidebar
# ---------------------------------------------------------------------------
DEFAULT_HIST = "Online Shopping 24-26 (1).xlsx"
DEFAULT_MTD  = "Online Shopping MTD (3).xlsx"
PRICING_DF, AVAILABILITY_DF = process_mfilterit_av_pr_file('mfilterit_pricing.xlsx','mfilterit_availability.xlsx')
DEFAULT_KEETA = "Sadafco Keeta Manual Tracker.xlsx"
DEFAULT_NINJA = "Sadafco_Ninja_Manual_Tracker.xlsx"

with st.sidebar:
    st.markdown(f"<h3 style='color:{NAVY_DARK};margin-top:0;'>Sales Tracker</h3>", unsafe_allow_html=True)
    st.caption(
        "Upload the **historic** file once. Each week, upload the latest **MTD** "
        "file — overlapping months are auto-replaced."
    )
    hist_upload = st.file_uploader("Historic file (.xlsx)", type=["xlsx"], key="hist_upload")
    mtd_upload  = st.file_uploader("MTD file (.xlsx)", type=["xlsx"], key="mtd_upload")
    st.markdown("---")
    st.markdown(f"<h3 style='color:{NAVY_DARK};margin-top:0;'>Pricing & Availability</h3>", unsafe_allow_html=True)
    data_dash_upload = st.file_uploader("Data Dashboard file (.xlsx)", type=["xlsx"], key="data_dash_upload")
    keeta_upload = st.file_uploader("Keeta Manual Tracker (.xlsx)", type=["xlsx"], key="keeta_upload")
    ninja_upload = st.file_uploader("Ninja Manual Tracker (.xlsx)", type=["xlsx"], key="ninja_upload")

# Load
hist_df, mtd_df = None, None
try:
    hist_df = load_historic(hist_upload if hist_upload is not None else DEFAULT_HIST)
except Exception:
    pass
try:
    mtd_df = load_mtd(mtd_upload if mtd_upload is not None else DEFAULT_MTD)
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

# dd_src = data_dash_upload if data_dash_upload is not None else DEFAULT_DATA_DASH
price_df, avail_df = None, None
_dd_load_error = None
try:
    price_df = load_pricing(PRICING_DF)
    avail_df = load_availability(AVAILABILITY_DF)
except Exception as e:
    _dd_load_error = str(e)

keeta_src = keeta_upload if keeta_upload is not None else DEFAULT_KEETA
try:
    keeta_price, keeta_avail = load_keeta_tracker(keeta_src)
    if not keeta_price.empty:
        if price_df is not None:
            common = [c for c in price_df.columns if c in keeta_price.columns]
            price_df = pd.concat([price_df[common], keeta_price[common]], ignore_index=True)
        else:
            price_df = keeta_price
    if not keeta_avail.empty:
        if avail_df is not None:
            common = [c for c in avail_df.columns if c in keeta_avail.columns]
            avail_df = pd.concat([avail_df[common], keeta_avail[common]], ignore_index=True)
        else:
            avail_df = keeta_avail
except Exception:
    pass

ninja_src = ninja_upload if ninja_upload is not None else DEFAULT_NINJA
try:
    ninja_price, ninja_avail = load_ninja_tracker(ninja_src)
    if not ninja_price.empty:
        if price_df is not None:
            common = [c for c in price_df.columns if c in ninja_price.columns]
            price_df = pd.concat([price_df[common], ninja_price[common]], ignore_index=True)
        else:
            price_df = ninja_price
    if not ninja_avail.empty:
        if avail_df is not None:
            common = [c for c in avail_df.columns if c in ninja_avail.columns]
            avail_df = pd.concat([avail_df[common], ninja_avail[common]], ignore_index=True)
        else:
            avail_df = ninja_avail
except Exception:
    pass


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def human(n: float) -> str:
    if pd.isna(n): return "—"
    a = abs(n)
    if a >= 1e9: return f"{n/1e9:.2f}B"
    if a >= 1e6: return f"{n/1e6:.2f}M"
    if a >= 1e3: return f"{n/1e3:.1f}K"
    return f"{n:,.0f}"


tab_sales, tab_pricing, tab_availability = st.tabs(["📊 Sales Tracker", "💲 Pricing", "📦 Availability"])


# ===========================================================================
# TAB 1 — SALES TRACKER
# ===========================================================================
with tab_sales:
    if df is None:
        st.info("No sales data found. Upload the historic and/or MTD workbooks via the sidebar.")
    else:
        st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
        max_date = df["Date"].max().date() if df["Date"].notna().any() else date.today()
        min_date = df["Date"].min().date() if df["Date"].notna().any() else max_date - timedelta(days=365)
        if "df_from" not in st.session_state:
            st.session_state.df_from = min_date
            st.session_state.df_to = max_date

        c1, c2, c3, c4, c5, c6 = st.columns([1.1, 1.1, 1.1, 1.4, 1, 1])
        with c1:
            platforms = ["All"] + sorted(df["Platform"].astype(str).unique().tolist())
            f_platform = st.selectbox("Platform", platforms, index=0)
        with c2:
            brand_pool = df if f_platform == "All" else df[df["Platform"] == f_platform]
            brands = ["All"] + sorted(brand_pool["Brand"].dropna().astype(str).unique().tolist())
            f_brand = st.selectbox("Brand", brands, index=0)
        with c3:
            categories = ["All"] + sorted(df["Category"].astype(str).unique().tolist())
            f_category = st.selectbox("Category", categories, index=0)
        with c4:
            sku_pool = df
            if f_platform != "All": sku_pool = sku_pool[sku_pool["Platform"] == f_platform]
            if f_brand != "All":    sku_pool = sku_pool[sku_pool["Brand"] == f_brand]
            if f_category != "All": sku_pool = sku_pool[sku_pool["Category"] == f_category]
            skus = ["All"] + sorted(sku_pool["SKU"].dropna().astype(str).unique().tolist())
            f_sku = st.selectbox("SKU", skus, index=0)
        with c5:
            f_date_from = st.date_input("Date from", value=st.session_state.df_from,
                                        min_value=min_date, max_value=max_date)
            st.session_state.df_from = f_date_from
        with c6:
            f_date_to = st.date_input("Date to", value=st.session_state.df_to,
                                      min_value=min_date, max_value=max_date)
            st.session_state.df_to = f_date_to
        st.markdown("</div>", unsafe_allow_html=True)

        # Build mask vectorized
        date_arr = df["Date"].dt.date
        mask = (date_arr >= f_date_from) & (date_arr <= f_date_to)
        if f_platform != "All": mask &= df["Platform"].astype(str) == f_platform
        if f_brand    != "All": mask &= df["Brand"].astype(str) == f_brand
        if f_category != "All": mask &= df["Category"].astype(str) == f_category
        if f_sku      != "All": mask &= df["SKU"].astype(str) == f_sku
        fdf = df[mask]

        # KPIs
        total_sales = fdf["Sales Val"].sum()
        total_units = fdf["Sales Qty"].sum()
        n_platforms = fdf["Platform"].nunique()
        n_skus = fdf["SKU"].nunique()
        if not fdf.empty:
            top_platform = fdf.groupby("Platform", observed=True)["Sales Val"].sum().idxmax()
        else:
            top_platform = "—"

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        k1, k2, k3, k4, k5 = st.columns(5)
        for col, label, value in [
            (k1, "Total sales (SAR)", human(total_sales)),
            (k2, "Units sold",        human(total_units)),
            (k3, "Platforms",         str(n_platforms)),
            (k4, "Active SKUs",       str(n_skus)),
            (k5, "Top platform",      str(top_platform)),
        ]:
            col.markdown(
                f"<div class='kpi-card'><div class='kpi-label'>{label}</div>"
                f"<div class='kpi-value'>{value}</div></div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='sec-title'>Total sales by platform</div>", unsafe_allow_html=True)
        bars = (fdf.groupby("Platform", observed=True)["Sales Val"].sum()
                    .sort_values(ascending=True).reset_index())
        if bars.empty:
            st.info("No data for the current filters.")
        else:
            bar_colors = [PLATFORM_COLORS.get(str(p), "#9CA3AF") for p in bars["Platform"]]
            fig = go.Figure(go.Bar(
                x=bars["Sales Val"], y=bars["Platform"].astype(str), orientation="h",
                marker=dict(color=bar_colors),
                text=[human(v) for v in bars["Sales Val"]],
                textposition="outside", cliponaxis=False,
            ))
            fig.update_layout(height=400, margin=dict(l=10, r=40, t=10, b=10),
                              plot_bgcolor="white",
                              xaxis=dict(gridcolor="#e5e7eb", title="Total sales value (SAR)"),
                              yaxis=dict(title=""))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='sec-title'>Category mix by platform</div>", unsafe_allow_html=True)
        mix = fdf.groupby(["Platform", "Category"], observed=True)["Sales Val"].sum().reset_index()
        if mix.empty:
            st.info("No data for the current filters.")
        else:
            plat_order = (mix.groupby("Platform", observed=True)["Sales Val"].sum()
                              .sort_values(ascending=False).index.astype(str).tolist())
            mix["Platform"] = mix["Platform"].astype(str)
            mix["Category"] = mix["Category"].astype(str)
            fig = px.bar(mix, x="Category", y="Sales Val", color="Platform",
                         color_discrete_map=PLATFORM_COLORS,
                         category_orders={"Platform": plat_order,
                                          "Category": list(CATEGORY_PALETTE.keys())})
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                              plot_bgcolor="white", barmode="group",
                              yaxis=dict(gridcolor="#e5e7eb", title="Sales value (SAR)"),
                              xaxis=dict(title=""))
            st.plotly_chart(fig, use_container_width=True)

        # Top-5 platform trend
        st.markdown("<div class='sec-title'>Category trend by platform — top 5 platforms</div>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Monthly sales value split by category, one panel per category, lines colored by platform.</div>", unsafe_allow_html=True)
        top5 = (fdf.groupby("Platform", observed=True)["Sales Val"].sum()
                    .sort_values(ascending=False).head(5).index.astype(str).tolist())
        cat_trend = fdf[fdf["Platform"].astype(str).isin(top5)]
        cat_trend = cat_trend.groupby(["Platform", "Category", "Month"],
                                      observed=True)["Sales Val"].sum().reset_index()
        if cat_trend.empty:
            st.info("No data for the current filters.")
        else:
            cat_trend["Month"] = pd.Categorical(cat_trend["Month"], categories=MONTH_ORDER, ordered=True)
            cat_trend = cat_trend.sort_values("Month")
            cat_trend["Platform"] = cat_trend["Platform"].astype(str)
            cat_trend["Category"] = cat_trend["Category"].astype(str)
            cats_present = [c for c in CATEGORY_PALETTE if c in cat_trend["Category"].unique()]
            fig = px.line(cat_trend, x="Month", y="Sales Val", color="Platform", markers=True,
                          facet_col="Category", facet_col_wrap=5,
                          color_discrete_map=PLATFORM_COLORS,
                          category_orders={"Platform": top5, "Category": cats_present})
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1],
                                                       font=dict(size=13, color=NAVY_DARK)))
            fig.update_yaxes(matches=None, showticklabels=True, gridcolor="#e5e7eb", title="")
            fig.update_xaxes(title="")
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10),
                              plot_bgcolor="white", legend_title_text="Platform")
            st.plotly_chart(fig, use_container_width=True)

        # ----- YoY (vectorized) -----
        _sel_months = []
        if fdf["Date"].notna().any():
            _sel_ym = fdf[["Year", "MonthNum"]].drop_duplicates()
            _sel_months = sorted(zip(_sel_ym["Year"].astype(int), _sel_ym["MonthNum"].astype(int)))
        _sel_years = sorted(set(y for y, _ in _sel_months))
        if _sel_years:
            cy_year = _sel_years[-1]
            py_year = cy_year - 1
            cy_month_nums = sorted(set(mn for y, mn in _sel_months if y == cy_year))
        else:
            cy_year = py_year = None
            cy_month_nums = []

        # YoY base — apply dropdown filters but NOT date range (vectorized once)
        yoy_mask = pd.Series(True, index=df.index)
        if f_platform != "All": yoy_mask &= df["Platform"].astype(str) == f_platform
        if f_brand    != "All": yoy_mask &= df["Brand"].astype(str) == f_brand
        if f_category != "All": yoy_mask &= df["Category"].astype(str) == f_category
        if f_sku      != "All": yoy_mask &= df["SKU"].astype(str) == f_sku
        yoy_base = df[yoy_mask]

        yoy_rows = []
        has_py = cy_year is not None and py_year in yoy_base["Year"].unique()

        if cy_month_nums and not has_py:
            st.markdown("<div class='sec-title' style='margin-top:28px;'>Year-over-Year comparison</div>",
                        unsafe_allow_html=True)
            st.info(f"No {py_year} data available to compare against.")
        elif cy_month_nums:
            st.markdown("<div class='sec-title' style='margin-top:28px;'>Year-over-Year comparison</div>",
                        unsafe_allow_html=True)
            st.markdown(
                "<div class='sec-sub'>Comparing each selected month of the current year against the "
                "same month of the prior year. Partial months are day-matched automatically.</div>",
                unsafe_allow_html=True,
            )
            cy_months_abr = [MONTH_NUM_TO_ABR[mn] for mn in cy_month_nums if mn in MONTH_NUM_TO_ABR]

            # Pre-compute per-month max-day in CY (single pass)
            cy_slice = yoy_base[yoy_base["Year"] == cy_year]
            max_days = cy_slice.groupby("Month", observed=True)["Day"].max()

            for m in cy_months_abr:
                if m not in max_days.index:
                    continue
                max_day = int(max_days[m])
                cy_val = float(cy_slice[cy_slice["Month"] == m]["Sales Val"].sum())
                py_val = float(yoy_base[(yoy_base["Year"] == py_year) &
                                        (yoy_base["Month"] == m) &
                                        (yoy_base["Day"] <= max_day)]["Sales Val"].sum())
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
                    if p is None or pd.isna(p): return "<span style='color:#9ca3af'>—</span>"
                    arrow = "▲" if p >= 0 else "▼"
                    color = "#00A651" if p >= 0 else "#E00034"
                    return f"<span style='color:{color};font-weight:700'>{arrow} {p:+.1f}%</span>"

                def fmt_delta(v):
                    if v == 0 or pd.isna(v): return "<span style='color:#9ca3af'>—</span>"
                    color = "#00A651" if v >= 0 else "#E00034"
                    sign = "+" if v > 0 else "−"
                    return f"<span style='color:{color};font-weight:700'>{sign}{human(abs(v))}</span>"

                head = (f"<thead><tr><th>Month</th><th>Window</th>"
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

                # YoY by platform per month — vectorized
                for row in yoy_rows:
                    m = row["Month"]
                    max_day = int(max_days[m])
                    cy_plat = (cy_slice[cy_slice["Month"] == m]
                               .groupby("Platform", observed=True)["Sales Val"].sum())
                    py_plat = (yoy_base[(yoy_base["Year"] == py_year) &
                                        (yoy_base["Month"] == m) &
                                        (yoy_base["Day"] <= max_day)]
                               .groupby("Platform", observed=True)["Sales Val"].sum())
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
                    plat_names = plat_df.index.astype(str).tolist()
                    py_colors = [PLATFORM_COLORS.get(p, "#9CA3AF") for p in plat_names]
                    cy_colors = py_colors
                    fig.add_bar(name=str(py_year), x=plat_names, y=plat_df[str(py_year)],
                                marker_color=py_colors, marker_opacity=0.45,
                                text=[human(v) for v in plat_df[str(py_year)]], textposition="outside")
                    fig.add_bar(name=str(cy_year), x=plat_names, y=plat_df[str(cy_year)],
                                marker_color=cy_colors,
                                text=[human(v) for v in plat_df[str(cy_year)]], textposition="outside")
                    fig.update_layout(barmode="group", height=400,
                                      margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                                      yaxis=dict(gridcolor="#e5e7eb", title="Sales value (SAR)"),
                                      xaxis=dict(title=""), legend_title_text="Year")
                    st.plotly_chart(fig, use_container_width=True)

                    # Platform × Category YoY breakdown
                    cy_pc = (cy_slice[cy_slice["Month"] == m]
                             .groupby(["Platform", "Category"], observed=True)["Sales Val"].sum()
                             .rename("CY"))
                    py_pc = (yoy_base[(yoy_base["Year"] == py_year) &
                                      (yoy_base["Month"] == m) &
                                      (yoy_base["Day"] <= max_day)]
                             .groupby(["Platform", "Category"], observed=True)["Sales Val"].sum()
                             .rename("PY"))
                    pc_merged = pd.concat([cy_pc, py_pc], axis=1).fillna(0).reset_index()
                    pc_merged["Δ SAR"] = pc_merged["CY"] - pc_merged["PY"]
                    pc_merged["Growth %"] = np.where(pc_merged["PY"] != 0,
                                                     pc_merged["Δ SAR"] / pc_merged["PY"] * 100,
                                                     np.nan)
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

        # ----- Pivots -----
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

        st.markdown("<h2 class='sec-title' style='margin-top:28px;'>Platform Wise Sales</h2>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Sum of Sales Val by Platform × Month</div>", unsafe_allow_html=True)

        # Pivot base — apply dropdown filters but not date range (one shot)
        pv_mask = pd.Series(True, index=df.index)
        if f_platform != "All": pv_mask &= df["Platform"].astype(str) == f_platform
        if f_brand    != "All": pv_mask &= df["Brand"].astype(str) == f_brand
        if f_category != "All": pv_mask &= df["Category"].astype(str) == f_category
        if f_sku      != "All": pv_mask &= df["SKU"].astype(str) == f_sku
        pivot_base = df[pv_mask]

        available_years = sorted(pivot_base["Year"].dropna().unique().astype(int), reverse=True)
        all_platforms = sorted(pivot_base["Platform"].dropna().astype(str).unique().tolist())
        all_categories = sorted(pivot_base["Category"].dropna().astype(str).unique().tolist())

        pv_col1, pv_col2 = st.columns(2)
        with pv_col1:
            pv1a, pv1b = st.columns(2)
            with pv1a:
                pv1_year = st.selectbox("Year", available_years, index=0, key="pv1_year")
            with pv1b:
                year_slice = pivot_base[pivot_base["Year"] == pv1_year]
                months_in_year = year_slice["Month"].astype(str).unique().tolist()
                pv1_months_in_year = [m for m in MONTH_ORDER if m in months_in_year]
                pv1_month = st.selectbox("Month", ["All"] + pv1_months_in_year, index=0, key="pv1_month")
        with pv_col2:
            pv1_platforms = st.multiselect("Platforms", all_platforms, default=all_platforms, key="pv1_plat")

        pv1_data = pivot_base[pivot_base["Year"] == pv1_year]
        if pv1_month != "All":
            pv1_data = pv1_data[pv1_data["Month"] == pv1_month]
        if pv1_platforms:
            pv1_data = pv1_data[pv1_data["Platform"].astype(str).isin(pv1_platforms)]

        plat_month = (pv1_data.pivot_table(index="Platform", columns="Month",
                                           values="Sales Val", aggfunc="sum",
                                           fill_value=0, observed=True)
                              .reindex(columns=MONTH_ORDER, fill_value=0))
        plat_month = plat_month.loc[plat_month.sum(axis=1).sort_values(ascending=False).index]
        st.markdown(render_pivot(plat_month, ["Platform"]), unsafe_allow_html=True)

        st.markdown("<h2 class='sec-title' style='margin-top:28px;'>Platform-Category Wise Sales</h2>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Sum of Sales Val by Platform → Category × Month</div>", unsafe_allow_html=True)
        pv2_col1, pv2_col2 = st.columns(2)
        with pv2_col1:
            pv2a, pv2b = st.columns(2)
            with pv2a:
                pv2_year = st.selectbox("Year", available_years, index=0, key="pv2_year")
            with pv2b:
                pv2_year_slice = pivot_base[pivot_base["Year"] == pv2_year]
                months_in_year2 = pv2_year_slice["Month"].astype(str).unique().tolist()
                pv2_months = [m for m in MONTH_ORDER if m in months_in_year2]
                pv2_month = st.selectbox("Month", ["All"] + pv2_months, index=0, key="pv2_month")
        with pv2_col2:
            pv2_platforms = st.multiselect("Platforms", all_platforms, default=all_platforms, key="pv2_plat")
        pv2_categories = st.multiselect("Categories", all_categories, default=all_categories, key="pv2_cat")

        pv2_data = pivot_base[pivot_base["Year"] == pv2_year]
        if pv2_month != "All":
            pv2_data = pv2_data[pv2_data["Month"] == pv2_month]
        if pv2_platforms:
            pv2_data = pv2_data[pv2_data["Platform"].astype(str).isin(pv2_platforms)]
        if pv2_categories:
            pv2_data = pv2_data[pv2_data["Category"].astype(str).isin(pv2_categories)]

        plat_cat_month = (pv2_data.pivot_table(index=["Platform", "Category"], columns="Month",
                                               values="Sales Val", aggfunc="sum",
                                               fill_value=0, observed=True)
                                  .reindex(columns=MONTH_ORDER, fill_value=0))
        plat_totals = plat_cat_month.groupby(level=0, observed=True).sum().sum(axis=1).sort_values(ascending=False)
        plat_cat_month = plat_cat_month.reindex(plat_totals.index, level=0)
        st.markdown(render_pivot(plat_cat_month, ["Platform", "Category"]), unsafe_allow_html=True)

        # ----- Volumes view -----
        VOLUME_BUCKETS = {
            "Whole Milk 1L":          {"sku": ["WHOLE MILK RECAP12X1000ML"]},
            "Whole Milk 2L":          {"sku": ["WHOLE MILK 6X2000 CC (PROMO)"]},
            "Whole Milk Pack of 4":   {"sku": ["WHOLE MILK 3X(4X1L)"]},
            "Whole Milk 200ml":       {"sku": ["WHOLE MILK 24X200ML"]},
            "Flavoured Milk 125ml":   {"group": "Flavoured Milk 125ml."},
            "Flavoured Milk 200ml":   {"group": "Flavoured Milk 200ml."},
            "Tomato Paste 135g":      {"sku": ["TOMATO PASTE 48X135 GM", "Tomato Paste Organic 6x4x135gm"]},
        }

        def bucket_mask(data, spec):
            if "sku" in spec:
                return data["ItemSubGroupDescription"].isin(spec["sku"])
            return data["ItemGroupName"] == spec["group"]

        st.markdown("<h2 class='sec-title' style='margin-top:32px;'>Volumes View — Focus SKUs</h2>", unsafe_allow_html=True)
        st.markdown("<div class='sec-sub'>Units sold per platform per month for focus SKUs.</div>", unsafe_allow_html=True)
        vol_platforms_avail = sorted(fdf["Platform"].dropna().astype(str).unique().tolist())
        vol_platform = st.selectbox("Platform", ["All"] + vol_platforms_avail, index=0, key="vol_plat")
        vol_base = fdf if vol_platform == "All" else fdf[fdf["Platform"].astype(str) == vol_platform]

        vol_rows = []
        for label, spec in VOLUME_BUCKETS.items():
            sub = vol_base[bucket_mask(vol_base, spec)]
            if sub.empty: continue
            monthly = sub.groupby("Month", observed=True)["Sales Qty"].sum()
            row = {"SKU": label}
            for m in MONTH_ORDER:
                row[m] = float(monthly.get(m, 0.0))
            row["Total"] = float(monthly.sum())
            vol_rows.append(row)

        if not vol_rows:
            st.info("No units recorded for any of the focus SKUs under the current filters.")
        else:
            vol_df = pd.DataFrame(vol_rows).set_index("SKU")
            months_present = [m for m in MONTH_ORDER if vol_df[m].sum() > 0]
            head = "<thead><tr><th>Focus SKU</th>" + \
                   "".join(f"<th>{m}</th>" for m in months_present) + "<th>Total</th></tr></thead>"
            body_html = []
            for idx, row in vol_df.iterrows():
                cells = "".join(f"<td class='num'>{fmt_cell(row[m])}</td>" for m in months_present)
                total_cell = f"<td class='num' style='background:#F3F6FB;font-weight:700;color:{NAVY_DARK}'>{human(row['Total'])}</td>"
                body_html.append(f"<tr><td class='row-label'>{idx}</td>{cells}{total_cell}</tr>")
            st.markdown(
                f"<div class='pivot-wrap'><table>{head}<tbody>{''.join(body_html)}</tbody></table></div>",
                unsafe_allow_html=True,
            )

            # Platform breakdown — single groupby
            st.markdown("<div class='sec-title' style='margin-top:18px;'>Platform breakdown</div>", unsafe_allow_html=True)
            pvol_rows = []
            for label, spec in VOLUME_BUCKETS.items():
                sub = fdf[bucket_mask(fdf, spec)]
                if sub.empty: continue
                by_plat = sub.groupby("Platform", observed=True)["Sales Qty"].sum()
                for plat, qty in by_plat.items():
                    if qty == 0: continue
                    pvol_rows.append({"Focus SKU": label, "Platform": str(plat), "Units": float(qty)})

            if pvol_rows:
                pvol_df = pd.DataFrame(pvol_rows)
                pvol_pivot = pvol_df.pivot_table(index="Focus SKU", columns="Platform",
                                                 values="Units", aggfunc="sum", fill_value=0)
                plat_order = pvol_pivot.sum().sort_values(ascending=False).index.tolist()
                pvol_pivot = pvol_pivot[plat_order]
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

        # Download
        def build_excel():
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as xl:
                plat_month.to_excel(xl, sheet_name="Platform x Month")
                plat_cat_month.to_excel(xl, sheet_name="Platform-Category x Month")
                if yoy_rows:
                    pd.DataFrame(yoy_rows).to_excel(xl, sheet_name="YoY Comparison", index=False)
                if vol_rows:
                    pd.DataFrame(vol_rows).set_index("SKU").to_excel(xl, sheet_name="Focus SKU Volumes")
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


# ===========================================================================
# Drill-tree helpers (shared by Pricing and Availability tabs)
# ===========================================================================
def _esc(s) -> str:
    """Minimal HTML escape — drill-tree text only, no rich formatting."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                  .replace(">", "&gt;").replace('"', "&quot;"))


def _get_loc(series: pd.Series, key) -> float:
    """Safely fetch from a (possibly multi-index) Series. Returns NaN if missing."""
    if series is None or series.empty:
        return float("nan")
    try:
        v = series.loc[key]
        return float(v) if not isinstance(v, pd.Series) else float("nan")
    except (KeyError, TypeError):
        return float("nan")


def _hier_means(df: pd.DataFrame, hierarchy: list[str], value_col: str,
                multiplier: float = 1.0) -> dict[int, pd.Series]:
    """Compute mean of `value_col` at each prefix-level of `hierarchy`.
    Returns dict {1: Series indexed by hierarchy[:1], 2: ..., etc.}."""
    out: dict[int, pd.Series] = {}
    if df.empty:
        for i in range(1, len(hierarchy) + 1):
            out[i] = pd.Series(dtype=float)
        return out
    for i in range(1, len(hierarchy) + 1):
        cols = hierarchy[:i]
        clean = df.dropna(subset=cols)
        if clean.empty:
            out[i] = pd.Series(dtype=float)
            continue
        s = clean.groupby(cols, observed=True)[value_col].mean()
        if multiplier != 1.0:
            s = s * multiplier
        out[i] = s
    return out


# ===========================================================================
# TAB 2 — PRICING
# ===========================================================================
with tab_pricing:
    if price_df is None or price_df.empty:
        if _dd_load_error:
            st.error(f"Failed to load pricing data: {_dd_load_error}")
        else:
            st.info("No pricing data available. Upload the Data Dashboard file (.xlsx) via the sidebar.")
    else:
        st.markdown(
            "<div class='saudia-title' style='text-align:center;'>Pricing</div>"
            "<div class='sec-sub' style='text-align:center;'>Average prices (SAR) by Brand × Platform, with period comparison.</div>",
            unsafe_allow_html=True,
        )

        # Filters
        pr_c1, pr_c2, pr_c3, pr_c4, pr_c5, pr_c6 = st.columns([1, 1, 1, 1, 1.2, 1.2])
        with pr_c1:
            pr_platforms = ["All"] + sorted(price_df["Platform"].dropna().astype(str).unique().tolist())
            pr_f_plat = st.selectbox("Platform", pr_platforms, index=0, key="pr_plat")
        with pr_c2:
            pr_brands = ["All"] + sorted(price_df["Brand"].dropna().astype(str).unique().tolist())
            pr_f_brand = st.selectbox("Brand", pr_brands, index=0, key="pr_brand")
        with pr_c3:
            pr_cats = ["All"] + sorted(price_df["Category"].dropna().astype(str).unique().tolist())
            pr_f_cat = st.selectbox("Category", pr_cats, index=0, key="pr_cat")
        with pr_c4:
            pr_f_type = st.selectbox("Type", ["All", "Brand", "Competitor"], index=0, key="pr_type")
        with pr_c5:
            pr_min_date = price_df["Date"].min().date() if price_df["Date"].notna().any() else date.today()
            pr_max_date = price_df["Date"].max().date() if price_df["Date"].notna().any() else date.today()
            pr_date_from = st.date_input("Date from", value=pr_min_date,
                                         min_value=pr_min_date, max_value=pr_max_date, key="pr_dfrom")
        with pr_c6:
            pr_date_to = st.date_input("Date to", value=pr_max_date,
                                       min_value=pr_min_date, max_value=pr_max_date, key="pr_dto")

        pr_c7, pr_c8 = st.columns(2)
        with pr_c7:
            pr_comp_from = st.date_input("Compare from", value=pr_min_date, key="pr_cfrom")
        with pr_c8:
            pr_comp_to = st.date_input("Compare to", value=pr_max_date, key="pr_cto")

        # Build masks vectorized — once each for main + comp
        pdates = price_df["Date"].dt.date
        pbase_mask = pd.Series(True, index=price_df.index)
        if pr_f_plat != "All":  pbase_mask &= price_df["Platform"].astype(str) == pr_f_plat
        if pr_f_brand != "All": pbase_mask &= price_df["Brand"].astype(str) == pr_f_brand
        if pr_f_cat != "All":   pbase_mask &= price_df["Category"].astype(str) == pr_f_cat
        if pr_f_type != "All" and "Type" in price_df.columns:
            pbase_mask &= price_df["Type"].astype(str) == pr_f_type

        pf_main = price_df[pbase_mask & (pdates >= pr_date_from) & (pdates <= pr_date_to)]
        pf_comp = price_df[pbase_mask & (pdates >= pr_comp_from) & (pdates <= pr_comp_to)]

        if pf_main.empty:
            st.info("No pricing data for the selected filters.")
        else:
            has_sku = "SKU" in pf_main.columns and pf_main["SKU"].notna().any()
            hierarchy = ["Platform", "Brand", "Category"] + (["SKU"] if has_sku else [])

            main_levels = _hier_means(pf_main, hierarchy, "Price")
            comp_levels = _hier_means(pf_comp, hierarchy, "Price")

            def fmt_change(curr, prev):
                if pd.isna(curr) or pd.isna(prev):
                    return "<span style='color:#9ca3af'>—</span>"
                diff = curr - prev
                if diff == 0:
                    return "<span style='color:#9ca3af'>SAR 0.00</span>"
                color = "#E00034" if diff < 0 else "#00A651"
                return f"<span style='color:{color};font-weight:600'>SAR {diff:+.2f}</span>"

            def cells(curr, prev):
                price_str = f"{curr:.2f}" if pd.notna(curr) else "—"
                return (f"<span class='num'>{price_str}</span>"
                        f"<span class='num'>{fmt_change(curr, prev)}</span>")

            def _strip_pcz(s):
                s = str(s)
                return s.split(" PC: Z")[0] if " PC: Z" in s else s

            # Build the HTML tree as a single string ------------------------------
            parts = ["<div class='drill-tree cols-3'>"]
            parts.append(
                "<div class='row header'>"
                "<span>Platform</span>"
                "<span class='num'>Price (SAR)</span>"
                "<span class='num'>Change</span>"
                "</div>"
            )

            plat_series = main_levels[1].sort_values(ascending=False)
            for plat in plat_series.index:
                plat_v = float(plat_series[plat])
                plat_c = _get_loc(comp_levels[1], plat)
                plat_label = _esc(plat)

                # Brands under this platform
                if 2 in main_levels and not main_levels[2].empty:
                    try:
                        brand_series = main_levels[2].loc[plat]
                        if isinstance(brand_series, float):  # singleton edge case
                            brand_series = pd.Series(dtype=float)
                    except KeyError:
                        brand_series = pd.Series(dtype=float)
                else:
                    brand_series = pd.Series(dtype=float)

                if brand_series.empty:
                    parts.append(
                        f"<div class='row level-0'>"
                        f"<span><span class='caret-empty'></span> "
                        f"<span class='name'>{plat_label}</span></span>"
                        f"{cells(plat_v, plat_c)}</div>"
                    )
                    continue

                parts.append(
                    f"<details><summary><div class='row level-0'>"
                    f"<span><span class='caret'></span> "
                    f"<span class='name'>{plat_label}</span></span>"
                    f"{cells(plat_v, plat_c)}</div></summary>"
                )

                for brand in brand_series.sort_values(ascending=False).index:
                    brand_v = float(brand_series[brand])
                    brand_c = _get_loc(comp_levels[2], (plat, brand))
                    brand_label = _esc(brand)

                    if 3 in main_levels and not main_levels[3].empty:
                        try:
                            cat_series = main_levels[3].loc[(plat, brand)]
                            if isinstance(cat_series, float):
                                cat_series = pd.Series(dtype=float)
                        except KeyError:
                            cat_series = pd.Series(dtype=float)
                    else:
                        cat_series = pd.Series(dtype=float)

                    if cat_series.empty:
                        parts.append(
                            f"<div class='row level-1'>"
                            f"<span><span class='caret-empty'></span> "
                            f"<span class='name'>{brand_label}</span></span>"
                            f"{cells(brand_v, brand_c)}</div>"
                        )
                        continue

                    parts.append(
                        f"<details><summary><div class='row level-1'>"
                        f"<span><span class='caret'></span> "
                        f"<span class='name'>{brand_label}</span></span>"
                        f"{cells(brand_v, brand_c)}</div></summary>"
                    )

                    for cat in cat_series.sort_values(ascending=False).index:
                        cat_v = float(cat_series[cat])
                        cat_c = _get_loc(comp_levels[3], (plat, brand, cat))
                        cat_label = _esc(cat)

                        if has_sku and 4 in main_levels and not main_levels[4].empty:
                            try:
                                sku_series = main_levels[4].loc[(plat, brand, cat)]
                                if isinstance(sku_series, float):
                                    sku_series = pd.Series(dtype=float)
                            except KeyError:
                                sku_series = pd.Series(dtype=float)
                        else:
                            sku_series = pd.Series(dtype=float)

                        if sku_series.empty:
                            parts.append(
                                f"<div class='row level-2'>"
                                f"<span><span class='caret-empty'></span> "
                                f"<span class='name'>{cat_label}</span></span>"
                                f"{cells(cat_v, cat_c)}</div>"
                            )
                            continue

                        parts.append(
                            f"<details><summary><div class='row level-2'>"
                            f"<span><span class='caret'></span> "
                            f"<span class='name'>{cat_label}</span></span>"
                            f"{cells(cat_v, cat_c)}</div></summary>"
                        )

                        for sku in sku_series.sort_values(ascending=False).index:
                            sku_v = float(sku_series[sku])
                            sku_c = _get_loc(comp_levels[4], (plat, brand, cat, sku))
                            sku_label = _esc(_strip_pcz(sku))
                            parts.append(
                                f"<div class='row level-3'>"
                                f"<span><span class='caret-empty'></span> "
                                f"<span class='name'>{sku_label}</span></span>"
                                f"{cells(sku_v, sku_c)}</div>"
                            )
                        parts.append("</details>")
                    parts.append("</details>")
                parts.append("</details>")

            # Total
            total_main = float(plat_series.mean()) if not plat_series.empty else float("nan")
            total_comp = float(comp_levels[1].mean()) if not comp_levels[1].empty else float("nan")
            parts.append(
                f"<div class='row total level-0'>"
                f"<span><span class='caret-empty'></span> "
                f"<span class='name'>Total</span></span>"
                f"{cells(total_main, total_comp)}</div>"
            )
            parts.append("</div>")
            st.markdown("".join(parts), unsafe_allow_html=True)


# ===========================================================================
# TAB 3 — AVAILABILITY
# ===========================================================================
with tab_availability:
    if avail_df is None or avail_df.empty:
        if _dd_load_error:
            st.error(f"Failed to load availability data: {_dd_load_error}")
        else:
            st.info("No availability data available. Upload the Data Dashboard file (.xlsx) via the sidebar.")
    else:
        st.markdown(
            "<div class='saudia-title' style='text-align:center;'>Availability</div>"
            "<div class='sec-sub' style='text-align:center;'>SKU availability % by Brand × Platform, with period comparison.</div>",
            unsafe_allow_html=True,
        )

        av_c1, av_c2, av_c3, av_c4, av_c5, av_c6 = st.columns([1, 1, 1, 1, 1.2, 1.2])
        with av_c1:
            av_platforms = ["All"] + sorted(avail_df["Platform"].dropna().astype(str).unique().tolist())
            av_f_plat = st.selectbox("Platform", av_platforms, index=0, key="av_plat")
        with av_c2:
            av_stores = ["All"] + sorted(avail_df["Store"].dropna().astype(str).unique().tolist())
            av_f_store = st.selectbox("Store", av_stores, index=0, key="av_store")
        with av_c3:
            av_cats = ["All"] + sorted(avail_df["Category"].dropna().astype(str).unique().tolist())
            av_f_cat = st.selectbox("Category", av_cats, index=0, key="av_cat")
        with av_c4:
            av_brands = ["All"] + sorted(avail_df["Brand"].dropna().astype(str).unique().tolist())
            av_f_brand = st.selectbox("Brand", av_brands, index=0, key="av_brand")
        with av_c5:
            av_min_date = avail_df["Date"].min().date() if avail_df["Date"].notna().any() else date.today()
            av_max_date = avail_df["Date"].max().date() if avail_df["Date"].notna().any() else date.today()
            av_date_from = st.date_input("Date from", value=av_min_date,
                                         min_value=av_min_date, max_value=av_max_date, key="av_dfrom")
        with av_c6:
            av_date_to = st.date_input("Date to", value=av_max_date,
                                       min_value=av_min_date, max_value=av_max_date, key="av_dto")

        # Build base mask vectorized
        avdates = avail_df["Date"].dt.date
        avbase_mask = pd.Series(True, index=avail_df.index)
        if av_f_plat != "All":  avbase_mask &= avail_df["Platform"].astype(str) == av_f_plat
        if av_f_store != "All": avbase_mask &= avail_df["Store"].astype(str) == av_f_store
        if av_f_cat != "All":   avbase_mask &= avail_df["Category"].astype(str) == av_f_cat
        if av_f_brand != "All": avbase_mask &= avail_df["Brand"].astype(str) == av_f_brand

        # Auto-derived periods (computed ONCE)
        range_days = (av_date_to - av_date_from).days + 1
        comp_from = av_date_from - timedelta(days=range_days)
        comp_to = av_date_from - timedelta(days=1)
        mtd_start = av_date_to.replace(day=1)
        ytd_start = av_date_to.replace(month=1, day=1)

        af_main = avail_df[avbase_mask & (avdates >= av_date_from) & (avdates <= av_date_to)]
        af_comp = avail_df[avbase_mask & (avdates >= comp_from)    & (avdates <= comp_to)]
        af_mtd  = avail_df[avbase_mask & (avdates >= mtd_start)    & (avdates <= av_date_to)]
        af_ytd  = avail_df[avbase_mask & (avdates >= ytd_start)    & (avdates <= av_date_to)]

        if af_main.empty:
            st.info("No availability data for the selected filters.")
        else:
            overall_avail = af_main["Availability"].mean() * 100
            st.markdown(
                f"<div style='text-align:center;margin:16px 0;'>"
                f"<span style='font-size:48px;font-weight:700;color:{NAVY_DARK}'>{overall_avail:.0f}%</span>"
                f"<br><span style='color:{MUTED};font-size:14px;'>Availability</span></div>",
                unsafe_allow_html=True,
            )

            has_store = "Store" in af_main.columns and af_main["Store"].notna().any()
            has_sku = "SKU" in af_main.columns and af_main["SKU"].notna().any()
            has_brand = "Brand" in af_main.columns and af_main["Brand"].notna().any()
            hierarchy = (["Platform", "Category"]
                         + (["Brand"] if has_brand else [])
                         + (["SKU"] if has_sku else [])
                         + (["Store"] if has_store else []))

            # ----- single-pass aggregates per period, per level -----
            main_lv = _hier_means(af_main, hierarchy, "Availability", multiplier=100.0)
            comp_lv = _hier_means(af_comp, hierarchy, "Availability", multiplier=100.0)
            mtd_lv  = _hier_means(af_mtd,  hierarchy, "Availability", multiplier=100.0)
            ytd_lv  = _hier_means(af_ytd,  hierarchy, "Availability", multiplier=100.0)

            def fmt_avail_pct(v):
                if pd.isna(v): return "<span style='color:#9ca3af'>—</span>"
                color = "#E00034" if v < 60 else ("#FF9800" if v < 80 else "#00A651")
                return f"<span style='color:{color};font-weight:600'>{v:.0f}%</span>"

            def fmt_vs(curr, prev):
                if pd.isna(curr) or pd.isna(prev):
                    return "<span style='color:#9ca3af'>—</span>"
                diff = curr - prev
                if diff > 0:
                    return f"<span style='color:#00A651;font-weight:600'>▲ {diff:+.0f}%</span>"
                elif diff < 0:
                    return f"<span style='color:#E00034;font-weight:600'>▼ {diff:+.0f}%</span>"
                return f"<span style='color:{MUTED}'>0%</span>"

            def cells4(level, key):
                m = _get_loc(main_lv[level], key)
                c = _get_loc(comp_lv[level], key) if level in comp_lv else float("nan")
                mt = _get_loc(mtd_lv[level], key) if level in mtd_lv else float("nan")
                yt = _get_loc(ytd_lv[level], key) if level in ytd_lv else float("nan")
                return (f"<span class='num'>{fmt_avail_pct(m)}</span>"
                        f"<span class='num'>{fmt_vs(m, c)}</span>"
                        f"<span class='num'>{fmt_avail_pct(mt)}</span>"
                        f"<span class='num'>{fmt_avail_pct(yt)}</span>")

            def _clean_store(s):
                return _esc(str(s).replace("_", " ").title())

            def _strip_pcz(s):
                s = str(s)
                return _esc(s.split(" PC: Z")[0] if " PC: Z" in s else s)

            # ----- build tree -----
            parts = ["<div class='drill-tree cols-5'>"]
            parts.append(
                "<div class='row header'>"
                "<span>Platform</span>"
                "<span class='num'>Availability</span>"
                "<span class='num'>vs Period</span>"
                "<span class='num'>MTD</span>"
                "<span class='num'>YTD</span>"
                "</div>"
            )

            plat_series = main_lv[1].sort_values(ascending=False) if not main_lv[1].empty else pd.Series(dtype=float)

            n_levels = len(hierarchy)
            # Hierarchy when fully populated:
            #   1=Platform, 2=Category, 3=Brand, 4=SKU, 5=Store
            for plat in plat_series.index:
                plat_label = _esc(plat)
                # Categories under platform
                cat_series = pd.Series(dtype=float)
                if n_levels >= 2 and not main_lv[2].empty:
                    try:
                        cat_series = main_lv[2].loc[plat]
                        if isinstance(cat_series, float):
                            cat_series = pd.Series(dtype=float)
                    except KeyError:
                        pass

                if cat_series.empty:
                    parts.append(
                        f"<div class='row level-0'>"
                        f"<span><span class='caret-empty'></span> "
                        f"<span class='name'>{plat_label}</span></span>"
                        f"{cells4(1, plat)}</div>"
                    )
                    continue

                parts.append(
                    f"<details><summary><div class='row level-0'>"
                    f"<span><span class='caret'></span> "
                    f"<span class='name'>{plat_label}</span></span>"
                    f"{cells4(1, plat)}</div></summary>"
                )

                for cat in cat_series.sort_values(ascending=False).index:
                    cat_label = _esc(cat)
                    # Brands under this category
                    brand_series = pd.Series(dtype=float)
                    if has_brand and n_levels >= 3 and not main_lv[3].empty:
                        try:
                            brand_series = main_lv[3].loc[(plat, cat)]
                            if isinstance(brand_series, float):
                                brand_series = pd.Series(dtype=float)
                        except KeyError:
                            pass

                    if brand_series.empty:
                        parts.append(
                            f"<div class='row level-1'>"
                            f"<span><span class='caret-empty'></span> "
                            f"<span class='name'>{cat_label}</span></span>"
                            f"{cells4(2, (plat, cat))}</div>"
                        )
                        continue

                    parts.append(
                        f"<details><summary><div class='row level-1'>"
                        f"<span><span class='caret'></span> "
                        f"<span class='name'>{cat_label}</span></span>"
                        f"{cells4(2, (plat, cat))}</div></summary>"
                    )

                    for brand in brand_series.sort_values(ascending=False).index:
                        brand_label = _esc(brand)
                        # SKUs under this brand
                        sku_series = pd.Series(dtype=float)
                        if has_sku and n_levels >= 4 and not main_lv[4].empty:
                            try:
                                sku_series = main_lv[4].loc[(plat, cat, brand)]
                                if isinstance(sku_series, float):
                                    sku_series = pd.Series(dtype=float)
                            except KeyError:
                                pass

                        if sku_series.empty:
                            parts.append(
                                f"<div class='row level-2'>"
                                f"<span><span class='caret-empty'></span> "
                                f"<span class='name'>{brand_label}</span></span>"
                                f"{cells4(3, (plat, cat, brand))}</div>"
                            )
                            continue

                        parts.append(
                            f"<details><summary><div class='row level-2'>"
                            f"<span><span class='caret'></span> "
                            f"<span class='name'>{brand_label}</span></span>"
                            f"{cells4(3, (plat, cat, brand))}</div></summary>"
                        )

                        for sku in sku_series.sort_values(ascending=False).index:
                            sku_label = _strip_pcz(sku)
                            # Stores under this SKU
                            store_series = pd.Series(dtype=float)
                            if has_store and n_levels >= 5 and not main_lv[5].empty:
                                try:
                                    store_series = main_lv[5].loc[(plat, cat, brand, sku)]
                                    if isinstance(store_series, float):
                                        store_series = pd.Series(dtype=float)
                                except KeyError:
                                    pass

                            if store_series.empty:
                                parts.append(
                                    f"<div class='row level-3'>"
                                    f"<span><span class='caret-empty'></span> "
                                    f"<span class='name'>{sku_label}</span></span>"
                                    f"{cells4(4, (plat, cat, brand, sku))}</div>"
                                )
                                continue

                            parts.append(
                                f"<details><summary><div class='row level-3'>"
                                f"<span><span class='caret'></span> "
                                f"<span class='name'>{sku_label}</span></span>"
                                f"{cells4(4, (plat, cat, brand, sku))}</div></summary>"
                            )

                            for store in store_series.sort_values(ascending=False).index:
                                parts.append(
                                    f"<div class='row level-4'>"
                                    f"<span><span class='caret-empty'></span> "
                                    f"<span class='name'>{_clean_store(store)}</span></span>"
                                    f"{cells4(5, (plat, cat, brand, sku, store))}</div>"
                                )
                            parts.append("</details>")
                        parts.append("</details>")
                    parts.append("</details>")
                parts.append("</details>")

            # Total
            if not plat_series.empty:
                ta = float(plat_series.mean())
                tc = float(comp_lv[1].mean()) if not comp_lv[1].empty else float("nan")
                tm = float(mtd_lv[1].mean()) if not mtd_lv[1].empty else float("nan")
                ty = float(ytd_lv[1].mean()) if not ytd_lv[1].empty else float("nan")
                parts.append(
                    f"<div class='row total level-0'>"
                    f"<span><span class='caret-empty'></span> "
                    f"<span class='name'>Total</span></span>"
                    f"<span class='num'>{fmt_avail_pct(ta)}</span>"
                    f"<span class='num'>{fmt_vs(ta, tc)}</span>"
                    f"<span class='num'>{fmt_avail_pct(tm)}</span>"
                    f"<span class='num'>{fmt_avail_pct(ty)}</span>"
                    f"</div>"
                )
            parts.append("</div>")
            st.markdown("".join(parts), unsafe_allow_html=True)

            # Platform bar chart
            st.markdown("<div class='sec-title' style='margin-top:24px;'>Availability by Platform</div>",
                        unsafe_allow_html=True)
            plat_avail = main_lv[1].round(1)
            if not plat_avail.empty:
                names = plat_avail.index.astype(str).tolist()
                fig = go.Figure(go.Bar(
                    x=names, y=plat_avail.values,
                    marker_color=[PLATFORM_COLORS.get(p, "#9CA3AF") for p in names],
                    text=[f"{v:.0f}%" for v in plat_avail.values],
                    textposition="outside",
                ))
                fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                                  plot_bgcolor="white",
                                  yaxis=dict(gridcolor="#e5e7eb", title="Availability %", range=[0, 105]),
                                  xaxis=dict(title=""))
                st.plotly_chart(fig, use_container_width=True)
