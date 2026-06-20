#!/usr/bin/env python3
"""
Market & Economic Dashboard
Generates an Excel workbook with:
  Sheet 1 – Global & US Market Performance (Yahoo Finance, no key needed)
  Sheet 2 – Economic Indicators (FRED API – free key at fred.stlouisfed.org/docs/api)

Usage:
  python market_dashboard.py
  python market_dashboard.py --fred-key YOUR_KEY_HERE
"""

import argparse
import warnings
warnings.filterwarnings("ignore")

import os
import sys
import requests
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── colour palette ────────────────────────────────────────────────────────────
C_DARK_BLUE  = "1F3864"
C_MID_BLUE   = "2E75B6"
C_WHITE      = "FFFFFF"
C_LIGHT_GREY = "F2F2F2"
C_DARK_GREEN = "375623"
C_DARK_RED   = "C00000"

# ── style helpers ─────────────────────────────────────────────────────────────

def thin_border():
    s = Side(border_style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def solid_fill(hex_color):
    return PatternFill(fill_type="solid", fgColor=hex_color)

def style_title(cell, text):
    cell.value = text
    cell.font = Font(bold=True, size=14, color=C_WHITE, name="Calibri")
    cell.fill = solid_fill(C_DARK_BLUE)
    cell.alignment = Alignment(horizontal="center", vertical="center")

def style_section(cell, text):
    cell.value = text
    cell.font = Font(bold=True, size=10, color=C_WHITE, name="Calibri")
    cell.fill = solid_fill(C_MID_BLUE)
    cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    cell.border = thin_border()

def style_col_header(cell, text):
    cell.value = text
    cell.font = Font(bold=True, size=10, color=C_WHITE, name="Calibri")
    cell.fill = solid_fill(C_DARK_BLUE)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = thin_border()

def style_data(cell, value, align="center", indent=0):
    cell.value = value
    cell.font = Font(name="Calibri", size=10)
    cell.alignment = Alignment(horizontal=align, vertical="center", indent=indent)
    cell.border = thin_border()

def colour_by_sign(cell, value):
    if value is None:
        return
    if value > 0:
        cell.font = Font(name="Calibri", size=10, bold=True, color=C_DARK_GREEN)
    elif value < 0:
        cell.font = Font(name="Calibri", size=10, bold=True, color=C_DARK_RED)

def pct_change(new, old):
    try:
        if old and old != 0:
            return (new - old) / abs(old)
    except Exception:
        pass
    return None

# ── market data (Yahoo Finance) ───────────────────────────────────────────────

def fetch_market(symbol, name):
    try:
        hist = yf.Ticker(symbol).history(period="1y")
        if hist.empty:
            return None
        close = hist["Close"]
        price = close.iloc[-1]

        prev_close = close.iloc[-2] if len(close) >= 2 else close.iloc[0]
        week_ago   = close.iloc[-6] if len(close) >= 6 else close.iloc[0]
        month_ago  = close.iloc[-22] if len(close) >= 22 else close.iloc[0]

        ytd_mask  = hist.index >= str(datetime(datetime.now().year, 1, 1))
        ytd_start = close[ytd_mask].iloc[0] if ytd_mask.any() else close.iloc[0]

        high_52w = hist["High"].max()
        low_52w  = hist["Low"].min()
        volume   = hist["Volume"].iloc[-1]

        return {
            "name":   name,
            "symbol": symbol,
            "price":  round(price, 4),
            "1d":     pct_change(price, prev_close),
            "1w":     pct_change(price, week_ago),
            "1m":     pct_change(price, month_ago),
            "ytd":    pct_change(price, ytd_start),
            "high52": round(high_52w, 4),
            "low52":  round(low_52w, 4),
            "vhigh":  pct_change(price, high_52w),
            "volume": int(volume),
        }
    except Exception as e:
        print(f"[warn] {symbol}: {e}")
        return None

# ── market sections ───────────────────────────────────────────────────────────

MARKET_SECTIONS = [
    ("US Equity Indices", [
        ("S&P 500",           "^GSPC"),
        ("Dow Jones",         "^DJI"),
        ("NASDAQ Composite",  "^IXIC"),
        ("Russell 2000",      "^RUT"),
    ]),
    ("Global Equity Indices", [
        ("FTSE 100 (UK)",          "^FTSE"),
        ("DAX (Germany)",          "^GDAXI"),
        ("CAC 40 (France)",        "^FCHI"),
        ("EURO STOXX 50",          "^STOXX50E"),
        ("IBEX 35 (Spain)",        "^IBEX"),
        ("Nikkei 225 (Japan)",     "^N225"),
        ("Hang Seng (Hong Kong)",  "^HSI"),
        ("Shanghai Comp. (China)", "000001.SS"),
        ("ASX 200 (Australia)",    "^AXJO"),
        ("BSE Sensex (India)",     "^BSESN"),
    ]),
    ("Volatility", [
        ("CBOE VIX (S&P 500)",  "^VIX"),
        ("VXN (NASDAQ 100)",    "^VXN"),
    ]),
    ("US Treasury Yields", [
        ("3-Month T-Bill",  "^IRX"),
        ("2-Year Note",     "^FVX"),
        ("10-Year Note",    "^TNX"),
        ("30-Year Bond",    "^TYX"),
    ]),
    ("Commodities", [
        ("Gold ($/oz)",         "GC=F"),
        ("Silver ($/oz)",       "SI=F"),
        ("WTI Crude ($/bbl)",   "CL=F"),
        ("Brent Crude ($/bbl)", "BZ=F"),
        ("Copper ($/lb)",       "HG=F"),
        ("Natural Gas",         "NG=F"),
        ("Corn",                "ZC=F"),
        ("Wheat",               "ZW=F"),
    ]),
    ("Currencies (vs USD)", [
        ("EUR/USD",   "EURUSD=X"),
        ("GBP/USD",   "GBPUSD=X"),
        ("USD/JPY",   "JPY=X"),
        ("USD/CHF",   "CHF=X"),
        ("USD/CNY",   "CNY=X"),
        ("AUD/USD",   "AUDUSD=X"),
        ("USD/CAD",   "CAD=X"),
        ("USD Index", "DX-Y.NYB"),
    ]),
    ("US Sector ETFs (S&P 500)", [
        ("Technology",             "XLK"),
        ("Financials",             "XLF"),
        ("Health Care",            "XLV"),
        ("Energy",                 "XLE"),
        ("Communication Svcs",     "XLC"),
        ("Industrials",            "XLI"),
        ("Consumer Discretionary", "XLY"),
        ("Consumer Staples",       "XLP"),
        ("Materials",              "XLB"),
        ("Real Estate",            "XLRE"),
        ("Utilities",              "XLU"),
    ]),
    ("Broad Market ETFs", [
        ("S&P 500 (SPY)",          "SPY"),
        ("NASDAQ 100 (QQQ)",       "QQQ"),
        ("Total World (VT)",       "VT"),
        ("Emerging Markets (EEM)", "EEM"),
        ("Developed Mkts (EFA)",   "EFA"),
        ("Aggregate Bonds (AGG)",  "AGG"),
        ("High Yield Bonds (HYG)", "HYG"),
        ("Gold ETF (GLD)",         "GLD"),
    ]),
]

MKT_COLS   = ["Name", "Symbol", "Last Price", "1D Chg%", "1W Chg%",
               "1M Chg%", "YTD Chg%", "52W High", "52W Low", "vs 52W High", "Volume"]
MKT_WIDTHS = [30, 12, 13, 11, 11, 11, 11, 13, 13, 13, 15]


def build_market_sheet(wb):
    ws = wb.create_sheet("Market Overview")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"

    ncols = len(MKT_COLS)
    span  = get_column_letter(ncols)

    ws.merge_cells(f"A1:{span}1")
    style_title(ws["A1"], f"Global & US Market Performance  —  {datetime.now().strftime('%B %d, %Y')}")
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 5

    for i, (h, w) in enumerate(zip(MKT_COLS, MKT_WIDTHS), 1):
        style_col_header(ws.cell(row=3, column=i), h)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[3].height = 34

    row = 4
    for section_name, tickers in MARKET_SECTIONS:
        ws.merge_cells(f"A{row}:{span}{row}")
        style_section(ws.cell(row=row, column=1), section_name)
        ws.row_dimensions[row].height = 20
        row += 1

        for name, symbol in tickers:
            print(f"  {symbol} …", end=" ", flush=True)
            d = fetch_market(symbol, name)
            print("ok" if d else "skip")
            if d is None:
                continue

            bg = solid_fill(C_LIGHT_GREY if row % 2 == 0 else C_WHITE)
            vals = [d["name"], d["symbol"], d["price"],
                    d["1d"], d["1w"], d["1m"], d["ytd"],
                    d["high52"], d["low52"], d["vhigh"], d["volume"]]

            for ci, v in enumerate(vals, 1):
                c = ws.cell(row=row, column=ci)
                style_data(c, v, align="left" if ci == 1 else "center",
                           indent=1 if ci == 1 else 0)
                c.fill = bg
                if ci == 2:
                    c.font = Font(name="Calibri", size=10, color="808080")
                if ci in (3, 8, 9):
                    c.number_format = "#,##0.00"
                if ci in (4, 5, 6, 7, 10):
                    c.number_format = "0.00%"
                    colour_by_sign(c, v)
                if ci == 11:
                    c.number_format = "#,##0"

            ws.row_dimensions[row].height = 18
            row += 1

        row += 1

    ws.merge_cells(f"A{row}:{span}{row}")
    note = ws.cell(row=row, column=1,
                   value="Source: Yahoo Finance via yfinance  |  Prices may be delayed ~15 min")
    note.font = Font(italic=True, size=9, color="808080", name="Calibri")
    note.alignment = Alignment(horizontal="left")


# ── FRED API (economic data) ──────────────────────────────────────────────────

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

def fetch_fred(series_id, fred_key, n=7):
    """Return the last n observations for a FRED series."""
    try:
        end   = datetime.today().strftime("%Y-%m-%d")
        start = (datetime.today() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        r = requests.get(FRED_BASE, params={
            "series_id":    series_id,
            "api_key":      fred_key,
            "file_type":    "json",
            "observation_start": start,
            "observation_end":   end,
            "sort_order":   "asc",
        }, timeout=10)
        r.raise_for_status()
        obs = [o for o in r.json()["observations"] if o["value"] != "."]
        if not obs:
            return None
        df = pd.DataFrame(obs[-(n + 6):])   # fetch a few extra for trend
        df["date"]  = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"])
        df = df.set_index("date")[["value"]]
        return df
    except Exception as e:
        print(f"[warn] FRED {series_id}: {e}")
        return None

# ── economic indicator definitions ────────────────────────────────────────────
# Each entry: (display label, FRED series ID, subsection)

MONTHLY_INDICATORS = [
    # Inflation
    ("CPI – All Items (Index)",          "CPIAUCSL",       "Inflation"),
    ("Core CPI excl. Food & Energy",     "CPILFESL",       "Inflation"),
    ("PCE Price Index",                  "PCEPI",          "Inflation"),
    ("Core PCE Price Index",             "PCEPILFE",       "Inflation"),
    ("PPI – Final Demand",               "PPIFID",         "Inflation"),
    ("5-Yr Breakeven Inflation (%)",     "T5YIE",          "Inflation"),
    ("10-Yr Breakeven Inflation (%)",    "T10YIE",         "Inflation"),
    # Labour Market
    ("Unemployment Rate (%)",            "UNRATE",         "Labour Market"),
    ("U-6 Underemployment Rate (%)",     "U6RATE",         "Labour Market"),
    ("Nonfarm Payrolls (000s)",          "PAYEMS",         "Labour Market"),
    ("Initial Jobless Claims",           "ICSA",           "Labour Market"),
    ("Continuing Jobless Claims",        "CCSA",           "Labour Market"),
    ("JOLTS Job Openings (000s)",        "JTSJOL",         "Labour Market"),
    ("Labour Force Participation (%)",   "CIVPART",        "Labour Market"),
    # Monetary Policy
    ("Federal Funds Rate (%)",           "FEDFUNDS",       "Monetary Policy"),
    ("SOFR (%)",                         "SOFR",           "Monetary Policy"),
    ("M2 Money Supply ($bn)",            "M2SL",           "Monetary Policy"),
    ("Bank Credit ($bn)",                "TOTBKCR",        "Monetary Policy"),
    # Yield Curve
    ("10Y-2Y Spread (%)",                "T10Y2Y",         "Yield Curve"),
    ("10Y-3M Spread (%)",                "T10Y3M",         "Yield Curve"),
    ("30-Year Mortgage Rate (%)",        "MORTGAGE30US",   "Yield Curve"),
    # Housing
    ("Housing Starts (000s)",            "HOUST",          "Housing"),
    ("Building Permits (000s)",          "PERMIT",         "Housing"),
    ("Existing Home Sales (mn)",         "EXHOSLUSM495S",  "Housing"),
    ("S&P/CS Home Price Index",          "CSUSHPISA",      "Housing"),
    # Consumer & Retail
    ("Retail & Food Services ($mn)",     "RSAFS",          "Consumer & Retail"),
    ("Personal Consumption ($bn)",       "PCE",            "Consumer & Retail"),
    ("Consumer Sentiment (U Mich)",      "UMCSENT",        "Consumer & Retail"),
    ("Personal Savings Rate (%)",        "PSAVERT",        "Consumer & Retail"),
    # Manufacturing
    ("Industrial Production (Index)",    "INDPRO",         "Manufacturing"),
    ("Capacity Utilisation (%)",         "TCU",            "Manufacturing"),
    ("Durable Goods Orders ($mn)",       "DGORDER",        "Manufacturing"),
    # Trade & Credit
    ("Trade Balance ($mn)",              "BOPGSTB",        "Trade & Credit"),
    ("TED Spread (bp)",                  "TEDRATE",        "Trade & Credit"),
]

QUARTERLY_INDICATORS = [
    ("Real GDP ($bn, 2017 chained)",     "GDP",            "Growth"),
    ("Real GDP Per Capita ($)",          "A939RX0Q048SBEA","Growth"),
    ("Exports of Goods & Services",      "EXPGS",          "Trade"),
    ("Imports of Goods & Services",      "IMPGS",          "Trade"),
    ("Credit Card Delinquency Rate (%)", "DRCCLACBS",      "Credit"),
]

# ── date period helpers ───────────────────────────────────────────────────────

def monthly_periods(n=6):
    """Last n calendar months as (year, month, label), oldest first."""
    today = datetime.today()
    result = []
    for i in range(n - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        result.append((y, m, datetime(y, m, 1).strftime("%b '%y")))
    return result

def quarterly_periods(n=6):
    """Last n quarters as (year, q_start_month, q_num, label), oldest first."""
    today = datetime.today()
    cur_q = (today.month - 1) // 3
    result = []
    for i in range(n - 1, -1, -1):
        q = cur_q - i
        y = today.year
        while q < 0:
            q += 4
            y -= 1
        m = q * 3 + 1
        result.append((y, m, q + 1, f"Q{q + 1} '{str(y)[2:]}"))
    return result

def val_for_month(df, year, month):
    if df is None:
        return None
    sub = df[(df.index.year == year) & (df.index.month == month)]
    return round(float(sub.iloc[-1, 0]), 2) if not sub.empty else None

def val_for_quarter(df, year, q_start_month):
    if df is None:
        return None
    sub = df[(df.index.year == year) &
             (df.index.month >= q_start_month) &
             (df.index.month <= q_start_month + 2)]
    return round(float(sub.iloc[-1, 0]), 2) if not sub.empty else None

# ── sheet builder helpers ─────────────────────────────────────────────────────

C_SUBSECTION = "4472C4"   # lighter blue for topic sub-headers

def write_freq_headers(ws, row, period_labels, ncols):
    """Write the column header row: Indicator | p1 | p2 … p6 | Chg."""
    span = get_column_letter(ncols)
    headers = ["Indicator"] + list(period_labels) + ["Chg"]
    for ci, h in enumerate(headers, 1):
        style_col_header(ws.cell(row=row, column=ci), h)
    ws.row_dimensions[row].height = 28

def write_subsection(ws, row, text, ncols):
    span = get_column_letter(ncols)
    ws.merge_cells(f"A{row}:{span}{row}")
    c = ws.cell(row=row, column=1)
    c.value = text
    c.font = Font(bold=True, size=10, color=C_WHITE, name="Calibri")
    c.fill = solid_fill(C_SUBSECTION)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=2)
    c.border = thin_border()
    ws.row_dimensions[row].height = 17

def write_data_row(ws, row, label, period_vals, ncols):
    bg = solid_fill(C_LIGHT_GREY if row % 2 == 0 else C_WHITE)
    non_none = [v for v in period_vals if v is not None]
    change = round(non_none[-1] - non_none[-2], 2) if len(non_none) >= 2 else None

    all_vals = [label] + list(period_vals) + [change]
    for ci, v in enumerate(all_vals, 1):
        c = ws.cell(row=row, column=ci)
        style_data(c, v, align="left" if ci == 1 else "center",
                   indent=1 if ci == 1 else 0)
        c.fill = bg
        if ci > 1 and isinstance(v, (int, float)):
            c.number_format = "#,##0.00"
        if ci == ncols and isinstance(v, (int, float)):
            colour_by_sign(c, v)
    ws.row_dimensions[row].height = 17


def build_econ_sheet(wb, fred_key):
    ws = wb.create_sheet("Economic Indicators")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B3"   # freeze col A (indicator names) + rows 1-2

    # 8 columns: Indicator + 6 periods + Change
    NCOLS = 8
    SPAN  = get_column_letter(NCOLS)

    ws.column_dimensions["A"].width = 36
    for i in range(2, NCOLS):           # B–G = 6 period columns
        ws.column_dimensions[get_column_letter(i)].width = 10
    ws.column_dimensions[get_column_letter(NCOLS)].width = 10  # H = Chg

    # Title
    ws.merge_cells(f"A1:{SPAN}1")
    style_title(ws["A1"], f"US Economic Indicators  —  {datetime.now().strftime('%B %d, %Y')}")
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 5

    if not fred_key:
        ws.merge_cells(f"A3:{SPAN}5")
        msg = ws.cell(row=3, column=1)
        msg.value = (
            "FRED API key required for economic data.\n"
            "Get a free key at: fred.stlouisfed.org/docs/api/api_key.html\n"
            "Then run:  python market_dashboard.py --fred-key YOUR_KEY"
        )
        msg.font = Font(name="Calibri", size=11, color=C_DARK_RED)
        msg.alignment = Alignment(horizontal="left", vertical="center",
                                  wrap_text=True, indent=1)
        msg.fill = solid_fill("FFF2CC")
        ws.row_dimensions[3].height = 60
        return

    mon_periods = monthly_periods(6)
    qtr_periods = quarterly_periods(6)

    # Fetch all series up front
    print("  Fetching monthly series …")
    mon_cache = {}
    for label, sid, _ in MONTHLY_INDICATORS:
        print(f"    FRED:{sid} …", end=" ", flush=True)
        mon_cache[sid] = fetch_fred(sid, fred_key, n=30)
        print("ok" if mon_cache[sid] is not None else "skip")

    print("  Fetching quarterly series …")
    qtr_cache = {}
    for label, sid, _ in QUARTERLY_INDICATORS:
        print(f"    FRED:{sid} …", end=" ", flush=True)
        qtr_cache[sid] = fetch_fred(sid, fred_key, n=12)
        print("ok" if qtr_cache[sid] is not None else "skip")

    row = 3

    # ── Monthly section ───────────────────────────────────────────────────────
    ws.merge_cells(f"A{row}:{SPAN}{row}")
    c = ws.cell(row=row, column=1)
    c.value = "MONTHLY INDICATORS"
    c.font  = Font(bold=True, size=12, color=C_WHITE, name="Calibri")
    c.fill  = solid_fill(C_DARK_BLUE)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 22
    row += 1

    write_freq_headers(ws, row, [p[2] for p in mon_periods], NCOLS)
    row += 1

    cur_sub = None
    for label, sid, subsection in MONTHLY_INDICATORS:
        if subsection != cur_sub:
            write_subsection(ws, row, subsection, NCOLS)
            row += 1
            cur_sub = subsection
        period_vals = [val_for_month(mon_cache.get(sid), y, m)
                       for y, m, _ in mon_periods]
        write_data_row(ws, row, label, period_vals, NCOLS)
        row += 1

    row += 1  # gap between sections

    # ── Quarterly section ─────────────────────────────────────────────────────
    ws.merge_cells(f"A{row}:{SPAN}{row}")
    c = ws.cell(row=row, column=1)
    c.value = "QUARTERLY INDICATORS"
    c.font  = Font(bold=True, size=12, color=C_WHITE, name="Calibri")
    c.fill  = solid_fill(C_DARK_BLUE)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 22
    row += 1

    write_freq_headers(ws, row, [p[3] for p in qtr_periods], NCOLS)
    row += 1

    cur_sub = None
    for label, sid, subsection in QUARTERLY_INDICATORS:
        if subsection != cur_sub:
            write_subsection(ws, row, subsection, NCOLS)
            row += 1
            cur_sub = subsection
        period_vals = [val_for_quarter(qtr_cache.get(sid), y, m)
                       for y, m, _, __ in qtr_periods]
        write_data_row(ws, row, label, period_vals, NCOLS)
        row += 1

    row += 1
    ws.merge_cells(f"A{row}:{SPAN}{row}")
    note = ws.cell(row=row, column=1,
                   value=("Source: Federal Reserve Bank of St. Louis (FRED)  |  "
                          "Columns = last 6 periods, oldest → newest  |  "
                          "Chg = latest minus prior period"))
    note.font = Font(italic=True, size=9, color="808080", name="Calibri")
    note.alignment = Alignment(horizontal="left")


# ── entry point ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Generate Market & Economic Dashboard Excel")
    p.add_argument("--fred-key", default=os.environ.get("FRED_API_KEY", ""),
                   help="FRED API key (or set FRED_API_KEY env var)")
    p.add_argument("--output", default="",
                   help="Output filename (default: market_dashboard_YYYYMMDD.xlsx)")
    return p.parse_args()


def main():
    args = parse_args()
    fred_key = args.fred_key.strip()
    filename = args.output or f"market_dashboard_{datetime.now().strftime('%Y%m%d')}.xlsx"

    print("=" * 60)
    print("  Market & Economic Dashboard Generator")
    print("=" * 60)
    if not fred_key:
        print("  [info] No FRED key — Sheet 2 will show setup instructions.")
        print("         Get a free key: fred.stlouisfed.org/docs/api/api_key.html")
    print()

    wb = Workbook()
    wb.remove(wb.active)

    print("[Sheet 1] Fetching market data from Yahoo Finance …")
    build_market_sheet(wb)

    print("\n[Sheet 2] Fetching economic data from FRED …")
    build_econ_sheet(wb, fred_key)

    wb.save(filename)
    print(f"\nSaved → {filename}")


if __name__ == "__main__":
    main()
