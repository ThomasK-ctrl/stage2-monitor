# EBA Credit Monitor
### Stage 2 & Stage 3 (NPL) Tracker for European Banks

A free, shareable dashboard tracking IFRS 9 credit deterioration across ~120 European banks.
Built on official EBA Transparency Exercise data. Updated with one Python command.

---

## Your Files

```
stage2-monitor/
├── index.html          ← The dashboard (open in any browser)
├── data/
│   └── stage2.json     ← The data (updated by the Python script)
├── update_data.py      ← Run this to refresh data
└── README.md           ← This file
```

---

## STEP 1 — View It Now

**Download all files. Keep the folder structure (data/ subfolder must stay next to index.html).**

Then double-click `index.html` — it opens in your browser immediately.

> The dashboard has two pages (tabs at the top):
> - **Stage 2** — credit deterioration leading indicator
> - **Stage 3** — current NPL stock

---

## STEP 2 — Put It Online (GitHub Pages, Free, ~10 minutes)

### Create a GitHub account
1. Go to **github.com**
2. Click **Sign up** → enter email, password, username
3. Verify your email

### Create a repository
1. Click **+** (top right) → **New repository**
2. Name: `stage2-monitor`
3. Set to **Public**
4. Leave everything else blank → **Create repository**

### Upload your files
1. On the empty repo page, click **uploading an existing file**
2. Drag and drop: `index.html`, the `data/` folder, `update_data.py`, `README.md`
3. Write a commit message: `Initial upload`
4. Click **Commit changes**

### Enable GitHub Pages
1. Click **Settings** tab → **Pages** (left sidebar)
2. Source: **Deploy from a branch**
3. Branch: **main** / **/ (root)**
4. Click **Save**
5. Wait 2–3 minutes
6. Your URL: `https://YOUR-USERNAME.github.io/stage2-monitor`

**Share that URL.** Anyone can open it. Free forever.

---

## STEP 3 — Install Python (one-time setup)

### Do I already have Python?
Open Terminal (Mac: Cmd+Space → "Terminal") or Command Prompt (Windows: Win+R → "cmd") and type:
```
python --version
```
If you see `Python 3.x.x` you're ready. Skip to Step 4.

### Installing Python
1. Go to **python.org/downloads**
2. Download Python 3.11 or newer
3. Run the installer
4. **IMPORTANT (Windows):** Tick **"Add Python to PATH"** before clicking Install
5. Click Install Now

### Install the two required libraries (one-time)
In Terminal / Command Prompt:
```
pip install requests pandas
```
Wait for it to finish. You'll see text scrolling. This takes 30–60 seconds.

---

## STEP 4 — Update the Data

EBA publishes a new Transparency Exercise every year in **November/December**.
When that happens, run:

### Navigate to your project folder
**Mac/Linux:**
```bash
cd ~/Desktop/stage2-monitor
```
**Windows:**
```
cd C:\Users\YourName\Desktop\stage2-monitor
```
(Replace the path with wherever you saved the folder)

### Run the update
```
python update_data.py
```

**What it does:**
1. Checks EBA's website for the latest Transparency Exercise CSV
2. Downloads and parses Stage 2 and Stage 3 data for all banks
3. Updates `data/stage2.json`
4. Prints a summary of changes

**Example output:**
```
EBA Credit Monitor — Data Updater v2

  ↓  2025: https://www.eba.europa.eu/assets/TE2025/...
  ✓  Downloaded 2025 data (52,840 rows)

════════════════════════════════════════════════════════
  EBA CREDIT MONITOR — DATA UPDATE SUMMARY
════════════════════════════════════════════════════════
  Banks updated:        119
  Latest period:        2025-06-30
  Total Stage 2:        €1,842bn  (avg ratio: 9.1%)
  Total Stage 3 (NPL):  €371bn    (avg ratio: 2.1%)
  High Stage 2 (≥12%):  14 banks
  High NPL    (≥ 4%):   11 banks

  ✓  Saved → data/stage2.json
  ✓  Reload the dashboard in your browser.
```

### Push to GitHub so your live URL updates

**Option A — Website (easiest):**
1. Go to your repo on github.com
2. Click `data/` folder → `stage2.json`
3. Click the pencil icon ✏️
4. Select all (Ctrl+A), delete, paste new content from your updated local file
5. Click **Commit changes**

**Option B — Terminal (faster once set up):**
```bash
git add data/stage2.json
git commit -m "Update: EBA 2025 Transparency Exercise data"
git push
```
Your live URL updates within 2 minutes.

---

## If Automatic Download Fails

EBA occasionally restructures their website. If the script can't find the file:

1. Go to: **https://www.eba.europa.eu/eu-wide-transparency-exercise-0**
2. Click the latest Transparency Exercise
3. Download the **full database CSV** (ZIP file, ~15MB)
4. Unzip — find the file named `TE20XX_AQU.csv` (AQU = Asset Quality)
5. Copy it into your `stage2-monitor` folder
6. Run:
```
python update_data.py --file TE20XX_AQU.csv
```

---

## Understanding the Two Pages

### Stage 2 Page
Tracks loans with a *significant increase in credit risk* since origination.
Still performing, but deteriorating. This is the **leading indicator** of future NPLs.

- Stage 2 ratio > 10% → Monitor
- Stage 2 ratio > 12% → Elevated NPL supply risk
- Stage 2 ratio > 15% → Strong NPL supply signal

Rising Stage 2 historically precedes NPL increases by **6–18 months**.

### Stage 3 Page (NPL)
Tracks loans that are non-performing — 90+ days past due or credit-impaired.
This is the **current NPL stock** — what's available to buy now.

- EU/EEA aggregate NPL ratio: **1.84%** at Jun 2025 (EBA Risk Dashboard)
- Total EU/EEA NPLs: **~€373bn**
- Key trend: Southern Europe reducing (IT, ES, GR, PT, CY down); Germany and France increasing

### The Stage 2 vs Stage 3 Scatter (Stage 2 page)
Shows each bank plotted by Stage 2 ratio (x-axis) and NPL ratio (y-axis).
Banks in the upper-right quadrant have both elevated current NPLs and rising credit risk.
These are priority candidates for NPL deal flow monitoring.

---

## Data Source

All data: **EBA EU-Wide Transparency Exercise**
- Free, openly licensed
- Official supervisory data reported by banks to EBA via EUCLID
- ~120 banks across 25 EU/EEA countries
- Published annually (November/December)
- Latest: **2025 TE** — covers Sep 2024, Dec 2024, Mar 2025, Jun 2025

EBA website: https://www.eba.europa.eu/eu-wide-transparency-exercise-0
