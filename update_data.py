#!/usr/bin/env python3
"""
update_data.py — EBA Credit Monitor Data Updater
=================================================
Fetches Stage 2 AND Stage 3 (NPL) data from the EBA EU-Wide Transparency
Exercise and updates data/stage2.json for the dashboard.
 
Usage:
    python update_data.py                  # Auto-download latest EBA data
    python update_data.py --force          # Re-download even if already current
    python update_data.py --file FILE.csv  # Use a manually downloaded EBA CSV
 
Requirements:
    pip install requests pandas
 
When to run:
    EBA publishes the Transparency Exercise once per year (November/December).
    Run this script after each publication.
 
Latest exercise: 2025 TE — published December 2025
Covers: Sep 2024, Dec 2024, Mar 2025, Jun 2025
"""
 
import json
import os
import sys
import io
import zipfile
import re
from pathlib import Path
from datetime import datetime
 
# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    print("❌  Missing: requests\n   Run: pip install requests pandas")
    sys.exit(1)
try:
    import pandas as pd
except ImportError:
    print("❌  Missing: pandas\n   Run: pip install requests pandas")
    sys.exit(1)
 
# ── Config ────────────────────────────────────────────────────────────────────
 
# EBA Transparency Exercise CSV download URLs
# The AQU template contains asset quality data (Stage 1 / 2 / 3)
EBA_URLS = {
    "2025": [
        "https://www.eba.europa.eu/assets/TE2025/Full_database/TE2025_AQU.csv",
        "https://www.eba.europa.eu/assets/TE2025/Full_database/TE2025_full_database.zip",
    ],
    "2024": [
        "https://www.eba.europa.eu/assets/TE2024/Full_database/TE2024_AQU.csv",
        "https://www.eba.europa.eu/assets/TE2024/Full_database/256109/TE2024_AQU.csv",
        "https://www.eba.europa.eu/assets/TE2024/Full_database/TE2024_full_database.zip",
    ],
}
 
DATA_FILE = Path(__file__).parent / "data" / "stage2.json"
DATA_FILE.parent.mkdir(exist_ok=True)
 
# EBA field label keywords for identification
STAGE1_KEYS  = ["stage 1", "performing", "no significant increase"]
STAGE2_KEYS  = ["stage 2", "significant increase in credit risk"]
STAGE3_KEYS  = ["stage 3", "non-performing", "credit-impaired", "npl"]
LOANS_KEYS   = ["loans and advances", "loans & advances"]
TOTAL_KEYS   = ["total", "gross carrying amount - total"]
 
# ── Logging ───────────────────────────────────────────────────────────────────
def log(msg, c=""):
    cs = {"g":"\033[92m","y":"\033[93m","r":"\033[91m","b":"\033[94m","":""};
    print(f"{cs.get(c,'')}{msg}\033[0m")
 
# ── HTTP download ─────────────────────────────────────────────────────────────
def download(url, year):
    log(f"  ↓  {year}: {url[:72]}…", "b")
    try:
        r = requests.get(url, timeout=90, headers={"User-Agent":"EBAMonitor/2.0"}, allow_redirects=True)
        r.raise_for_status()
        ct = r.headers.get("Content-Type","")
        content = r.content
 
        # Handle ZIP
        if "zip" in ct or url.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                # Prefer AQU (asset quality) file
                candidates = sorted(
                    [f for f in zf.namelist() if f.endswith(".csv")],
                    key=lambda f: (0 if "AQU" in f.upper() else 1, f)
                )
                if not candidates:
                    log("  ✗  No CSV in ZIP", "y"); return None
                with zf.open(candidates[0]) as f:
                    log(f"     Extracted: {candidates[0]}", "b")
                    return pd.read_csv(f, encoding="utf-8-sig", sep=None, engine="python", low_memory=False)
 
        # Handle raw CSV
        text = content.decode("utf-8-sig", errors="replace")
        # Detect separator
        sep = ";" if text.count(";") > text.count(",") else ","
        return pd.read_csv(io.StringIO(text), sep=sep, low_memory=False)
 
    except requests.HTTPError as e:
        log(f"  ✗  HTTP {e.response.status_code}", "y")
    except Exception as e:
        log(f"  ✗  {e}", "y")
    return None
 
 
# ── Column detection ──────────────────────────────────────────────────────────
def find_col(cols, keywords, require_all=False):
    cols_lower = [c.lower() for c in cols]
    for i, c in enumerate(cols_lower):
        hits = sum(1 for k in keywords if k in c)
        if require_all and hits == len(keywords): return cols[i]
        if not require_all and hits >= 1: return cols[i]
    return None
 
def contains_any(text, keywords):
    t = text.lower()
    return any(k in t for k in keywords)
 
def contains_all(text, *keyword_lists):
    t = text.lower()
    return all(any(k in t for k in kl) for kl in keyword_lists)
 
 
# ── Parse EBA long-format CSV ─────────────────────────────────────────────────
def parse_long_format(df):
    """
    EBA AQU CSV is typically long-format:
    columns: LEI/BankID, BankName, Country, Period, Label, Amount
    Each row = one metric for one bank at one period.
    """
    df.columns = [c.strip() for c in df.columns]
 
    id_col      = find_col(df.columns, ["lei", "bank_id", "bankid"]) or df.columns[0]
    name_col    = find_col(df.columns, ["bank_name", "bankname", "name", "institution"])
    country_col = find_col(df.columns, ["country_code", "country", "cntry"])
    period_col  = find_col(df.columns, ["period", "reference_date", "ref_date", "date"])
    label_col   = find_col(df.columns, ["label", "item", "indicator", "variable"])
    amount_col  = find_col(df.columns, ["amount", "value", "figure", "data"])
 
    if not all([id_col, period_col, label_col, amount_col]):
        log("  ℹ  Columns not identified for long-format; trying wide-format…", "b")
        return parse_wide_format(df)
 
    result = {}
 
    for _, row in df.iterrows():
        bid     = str(row.get(id_col, "")).strip()
        period  = str(row.get(period_col, "")).strip()
        label   = str(row.get(label_col, "")).strip()
        try:
            amount = float(str(row.get(amount_col, 0)).replace(",", "").replace(" ", "") or 0)
        except (ValueError, TypeError):
            amount = 0.0
 
        if not bid or not period or not label:
            continue
 
        # Normalise period to YYYY-MM-DD
        period = normalise_period(period)
        if not period:
            continue
 
        if bid not in result:
            result[bid] = {
                "name":    str(row.get(name_col, bid)).strip() if name_col else bid,
                "country": str(row.get(country_col, "")).strip()[:2].upper() if country_col else "",
                "periods": {}
            }
        if period not in result[bid]["periods"]:
            result[bid]["periods"][period] = {"s1": 0.0, "s2": 0.0, "s3": 0.0, "total": 0.0}
 
        pd_data = result[bid]["periods"][period]
        lbl = label.lower()
 
        # Classify: must mention loans AND stage
        if not contains_any(lbl, LOANS_KEYS):
            continue
 
        if contains_any(lbl, STAGE3_KEYS) and not "coverage" in lbl:
            pd_data["s3"] += amount / 1_000   # EUR thousands → billions
        elif contains_any(lbl, STAGE2_KEYS):
            pd_data["s2"] += amount / 1_000
        elif contains_any(lbl, STAGE1_KEYS):
            pd_data["s1"] += amount / 1_000
        elif contains_any(lbl, TOTAL_KEYS):
            pd_data["total"] += amount / 1_000
 
    return result
 
 
def parse_wide_format(df):
    """
    Wide-format: each row = one bank/period, columns = metrics.
    """
    result = {}
    id_col = df.columns[0]
    name_col = find_col(df.columns, ["name", "bank"])
    period_col = find_col(df.columns, ["period", "date"])
    country_col = find_col(df.columns, ["country"])
 
    s1_cols = [c for c in df.columns if contains_any(c, STAGE1_KEYS) and contains_any(c, LOANS_KEYS)]
    s2_cols = [c for c in df.columns if contains_any(c, STAGE2_KEYS) and contains_any(c, LOANS_KEYS)]
    s3_cols = [c for c in df.columns if contains_any(c, STAGE3_KEYS) and contains_any(c, LOANS_KEYS) and "coverage" not in c.lower()]
    tot_cols= [c for c in df.columns if contains_any(c, TOTAL_KEYS) and contains_any(c, LOANS_KEYS)]
 
    def safe_sum(cols, row):
        s = 0.0
        for c in cols:
            try: s += float(str(row.get(c,0)).replace(",","") or 0)
            except: pass
        return s / 1_000
 
    for _, row in df.iterrows():
        bid = str(row.get(id_col, "")).strip()
        period = normalise_period(str(row.get(period_col, "")).strip()) if period_col else "latest"
        if not bid or not period: continue
        if bid not in result:
            result[bid] = {"name": str(row.get(name_col, bid)).strip() if name_col else bid,
                           "country": str(row.get(country_col,"")).strip()[:2].upper() if country_col else "",
                           "periods": {}}
        result[bid]["periods"][period] = {
            "s1": safe_sum(s1_cols, row),
            "s2": safe_sum(s2_cols, row),
            "s3": safe_sum(s3_cols, row),
            "total": safe_sum(tot_cols, row),
        }
    return result
 
 
def normalise_period(s):
    """Convert various date formats to YYYY-MM-DD."""
    s = s.strip().replace("/", "-").replace(".", "-")
    # Already YYYY-MM-DD
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    # YYYYMM
    m = re.match(r"(\d{4})(\d{2})", s)
    if m:
        y, mo = m.group(1), m.group(2)
        # Last day of month
        days = {"01":"31","02":"28","03":"31","04":"30","05":"31","06":"30",
                "07":"31","08":"31","09":"30","10":"31","11":"30","12":"31"}
        return f"{y}-{mo}-{days.get(mo,'30')}"
    # MM-YYYY or MM/YYYY
    m = re.match(r"(\d{2})-(\d{4})", s)
    if m:
        mo, y = m.group(1), m.group(2)
        days = {"01":"31","02":"28","03":"31","04":"30","05":"31","06":"30",
                "07":"31","08":"31","09":"30","10":"31","11":"30","12":"31"}
        return f"{y}-{mo}-{days.get(mo,'30')}"
    return None
 
 
# ── Build output JSON ─────────────────────────────────────────────────────────
def build_json(raw_data, year):
    existing = load_existing()
    existing_map = {b["id"]: b for b in existing.get("banks", [])}
    banks_out = []
 
    for bid, data in raw_data.items():
        periods_sorted = sorted(data["periods"].keys())
        if not periods_sorted:
            continue
 
        history = []
        for period in periods_sorted:
            pd = data["periods"][period]
            s2 = pd["s2"]; s3 = pd["s3"]; s1 = pd["s1"]
            total = pd["total"] if pd["total"] > 0 else (s1 + s2 + s3)
            if total <= 0:
                continue
            history.append({
                "period":       period,
                "stage1_bn":    round(s1, 2),
                "stage2_bn":    round(s2, 2),
                "stage2_ratio": round(s2/total*100, 2),
                "stage3_bn":    round(s3, 2),
                "npl_ratio":    round(s3/total*100, 2),
                "total_loans_bn": round(total, 2),
            })
 
        if not history:
            continue
 
        ex = existing_map.get(bid)
        banks_out.append({
            "id":             bid,
            "name":           ex["name"] if ex else data["name"],
            "country":        ex["country"] if ex else data["country"],
            "country_name":   ex.get("country_name", data["country"]) if ex else data["country"],
            "total_assets_bn": ex.get("total_assets_bn", 0) if ex else 0,
            "history":        history,
        })
 
    periods   = sorted({h["period"] for b in banks_out for h in b["history"]})
    pl_months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    period_labels = []
    for p in periods:
        try:
            d = datetime.strptime(p, "%Y-%m-%d")
            period_labels.append(f"{pl_months[d.month-1]} {d.year}")
        except:
            period_labels.append(p)
 
    latest_period = max(periods) if periods else ""
 
    return {
        "meta": {
            "source":        f"EBA EU-Wide Transparency Exercise {year}",
            "description":   "IFRS 9 Stage 2 and Stage 3 (NPL) loan data",
            "exercise_year": str(year),
            "periods":       periods,
            "period_labels": period_labels,
            "last_updated":  latest_period,
            "published_by_eba": f"{year}-12",
            "notes":         "Values in EUR billions. Stage 2 ratio = Stage 2 / Total Loans. NPL ratio = Stage 3 / Total Loans.",
            "eba_url":       "https://www.eba.europa.eu/eu-wide-transparency-exercise-0",
            "latest_eba_aggregate": {
                "npl_ratio_pct":  1.84,
                "stage2_ratio_pct": 9.1,
                "total_npl_bn":   373,
                "reference":      "Q3/Q4 2025 EBA Risk Dashboard"
            },
            "refreshed_at": datetime.now().isoformat(),
        },
        "banks": banks_out,
    }
 
 
def load_existing():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"banks": []}
 
 
def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
 
 
# ── Summary ───────────────────────────────────────────────────────────────────
def print_summary(data):
    banks = data["banks"]
    if not banks:
        log("⚠  No bank data — file not updated.", "y"); return
 
    latest = data["meta"]["last_updated"]
    total_s2 = sum(b["history"][-1]["stage2_bn"] for b in banks)
    total_s3 = sum(b["history"][-1]["stage3_bn"] for b in banks)
    avg_s2   = sum(b["history"][-1]["stage2_ratio"] for b in banks) / len(banks)
    avg_npl  = sum(b["history"][-1]["npl_ratio"] for b in banks) / len(banks)
    hi_s2    = [b for b in banks if b["history"][-1]["stage2_ratio"] >= 12]
    hi_npl   = [b for b in banks if b["history"][-1]["npl_ratio"] >= 4]
    rising   = [b for b in banks if b["history"][-1]["stage2_ratio"] > b["history"][0]["stage2_ratio"] + 1.0]
 
    print()
    log("═"*60, "g")
    log("  EBA CREDIT MONITOR — DATA UPDATE SUMMARY", "g")
    log("═"*60, "g")
    print(f"  Banks updated:        {len(banks)}")
    print(f"  Latest period:        {latest}")
    print(f"  Total Stage 2:        €{total_s2:.0f}bn  (avg ratio: {avg_s2:.1f}%)")
    print(f"  Total Stage 3 (NPL):  €{total_s3:.0f}bn  (avg ratio: {avg_npl:.1f}%)")
    print(f"  High Stage 2 (≥12%):  {len(hi_s2)} banks")
    print(f"  High NPL    (≥ 4%):   {len(hi_npl)} banks")
    print(f"  Rising Stage 2:       {rising and len(rising) or 0} banks (>1pp increase)")
    print()
 
    if hi_s2:
        log("  TOP STAGE 2 BANKS:", "y")
        for b in sorted(hi_s2, key=lambda x: -x["history"][-1]["stage2_ratio"])[:5]:
            r = b["history"][-1]["stage2_ratio"]
            print(f"    {b['name'][:38]:<38}  S2: {r:.1f}%")
    print()
    if hi_npl:
        log("  TOP NPL BANKS:", "r")
        for b in sorted(hi_npl, key=lambda x: -x["history"][-1]["npl_ratio"])[:5]:
            r = b["history"][-1]["npl_ratio"]
            print(f"    {b['name'][:38]:<38}  NPL: {r:.1f}%")
    print()
    log(f"  ✓  Saved → {DATA_FILE}", "g")
    log("  ✓  Reload the dashboard in your browser.", "g")
    log("═"*60, "g")
    print()
 
 
MANUAL_GUIDE = """
══════════════════════════════════════════════════════════════
  MANUAL UPDATE — if automatic download fails
══════════════════════════════════════════════════════════════
 
  1. Go to:
     https://www.eba.europa.eu/eu-wide-transparency-exercise-0
 
  2. Click the latest Transparency Exercise (e.g. 2025 TE)
 
  3. Download the full CSV database (ZIP, ~15MB)
 
  4. Unzip it — find the file:  TE20XX_AQU.csv
     (AQU = Asset Quality template = Stage 1/2/3 data)
 
  5. Place it in the same folder as this script
 
  6. Run:
     python update_data.py --file TE20XX_AQU.csv
 
══════════════════════════════════════════════════════════════
"""
 
 
# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print()
    log("EBA Credit Monitor — Data Updater v2", "b")
    log("Stage 2 & Stage 3 (NPL) · EBA Transparency Exercise", "b")
    print()
 
    # --file mode
    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        if idx+1 < len(sys.argv):
            fp = sys.argv[idx+1]
            log(f"  Loading from file: {fp}", "b")
            try:
                sep = None
                with open(fp, "r", encoding="utf-8-sig", errors="replace") as f:
                    sample = f.read(2000)
                sep = ";" if sample.count(";") > sample.count(",") else ","
                df = pd.read_csv(fp, encoding="utf-8-sig", sep=sep, low_memory=False)
                raw = parse_long_format(df)
                if not raw:
                    log("❌  No data found in file.", "r")
                    print(MANUAL_GUIDE); sys.exit(1)
                data = build_json(raw, "manual")
                if not data["banks"]:
                    log("❌  Parsed but found no bank records.", "r")
                    print(MANUAL_GUIDE); sys.exit(1)
                save(data); print_summary(data)
            except Exception as e:
                log(f"❌  Error: {e}", "r"); sys.exit(1)
        else:
            log("❌  --file requires a path", "r"); sys.exit(1)
        return
 
    # Auto-download mode
    existing = load_existing()
    existing_year = existing.get("meta", {}).get("exercise_year", "")
    if existing_year:
        log(f"  Current data: EBA {existing_year} exercise", "b")
 
    success = False
    for year in sorted(EBA_URLS.keys(), reverse=True):
        if year == existing_year and "--force" not in sys.argv:
            log(f"  ℹ  Already have {year} data. Use --force to re-download.", "y")
            continue
        for url in EBA_URLS[year]:
            df = download(url, year)
            if df is not None and not df.empty:
                log(f"  ✓  Downloaded {year} data ({len(df):,} rows)", "g")
                raw = parse_long_format(df)
                if raw:
                    data = build_json(raw, year)
                    if data["banks"]:
                        save(data); print_summary(data)
                        success = True; break
                    else:
                        log(f"  ✗  Parsed but no bank records found for {year}", "y")
            if success: break
        if success: break
 
    if not success:
        log("⚠  Automatic download did not find new data.", "y")
        print()
        if existing_year:
            log(f"  Your current data ({existing_year}) is intact.", "b")
            print_summary(existing)
        print(MANUAL_GUIDE)
 
 
if __name__ == "__main__":
    main()
