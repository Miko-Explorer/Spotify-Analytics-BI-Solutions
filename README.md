# Spotify Analytics

**Web-Based Spotify Business Intelligence Dashboard**  
University of Santo Tomas | College of Science | Department of Mathematics and Physics  
DSA 4157 – Business Intelligence | 1st Term, AY 2026–2027  
Group 2, 3DSA2

## 1. Project overview

Spotify Analytics is a local, web-based Business Intelligence (BI) application that transforms historical Spotify chart records into an interactive analytics experience. The project combines Python data preparation, MySQL staging and dimensional warehousing, a Django analytics backend, and JavaScript visualizations.

Instead of relying on individual chart snapshots, users explore changes in streaming volume, regional market differences, chart momentum and longevity, and artist performance. The interface uses a dark, glassmorphism-inspired design with context-aware KPI cards, filtered charts, searchable detail tables, and individual visualization zoom controls.

**Current implementation:** a locally operated historical analytics dashboard. The application is **not** connected to a live Spotify streaming API, and its historical coverage ends with the datasets loaded into MySQL. Dashboard figures should be considered validated only after comparison with the corresponding warehouse SQL results.

### Intended users

- Music-industry researchers, artist-and-repertoire (A&R) analysts, and label managers studying chart performance.
- Independent artists exploring credited-track performance and geographic chart reach.
- Students and music enthusiasts interested in how songs, artists, and albums move through charts.

### Questions addressed

- Which tracks receive the most chart-reported streams in a selected market and period?
- Which tracks are improving their chart position or maintaining long streaks?
- How does a country's chart activity compare with the source GLOBAL chart?
- Which artists, markets, and record labels have stronger representation?
- How do a selected artist's credited tracks perform across markets and time?
- Which albums show longer chart persistence, where artist–album attribution is available?

## 2. Project status and scope

| Area | Scope |
| --- | --- |
| Data sources | Downloaded Spotify chart CSVs: daily songs, daily artists, weekly albums, and artist master data |
| Data processing | Exploratory analysis and cleaning in Jupyter notebooks |
| Storage | MySQL 8.0 staging (`spotify_analytics_stg`) and warehouse (`spotify_analytics_dw`) |
| Web backend | Django, read-only SQL analytics queries, JSON endpoints |
| Frontend | Django templates, CSS, JavaScript, Chart.js, geographic visualizations where supported |
| Dashboard pages | Global Pulse; Regional Rhythms; Hit Velocity & Longevity; Artist Deep-Dive |
| UI features | Capability-aware filters, conditional KPI/chart presentation, per-chart zoom controls, detail-table tools |
| Runtime | Local development on Windows / VS Code; Python 3.13 used in development |
| Deployment | Production hosting is not established by the repository structure shown |

This README describes the project structure and implementation goals. Some features require browser and database verification on the developer's machine.

## 3. Data sources and coverage

The project's source dataset is the Kaggle collection **Spotify Charts Daily Updated**, attributed in the proposal to Gonzalo López Gil. Four working files are stored under `data/raw/`:

| File | Purpose | Granularity |
| --- | --- | --- |
| `charts_songs_daily_365D.csv` | Song positions, streams, status, longevity, metadata | Song × country/market × date |
| `charts_artists_daily_365D.csv` | Artist chart position and history | Artist × country/market × date |
| `charts_albums_weekly_52W.csv` | Album ranking, weeks on chart and release metadata | Album × country/market × week |
| `artists.csv` | Artist names and recorded monthly-listener / peak values | Artist master record |

The previously loaded dataset was reported as follows:

| Staging table | Loaded rows | Observed chart dates |
| --- | ---: | ---: |
| `clean_songs_daily_365D` | 5,124,654 | 365 |
| `clean_artists_daily_365D` | 4,923,470 | 353 |
| `clean_albums_weekly_52W` | 526,800 | 52 weekly dates |

Daily songs and artists span **2025-11-11 through 2026-11-10**. The daily artists source covers **353 observed dates**, so its date series has gaps. Weekly album records start earlier and use the `week_start_date` field. The source `GLOBAL` market is a separate chart; do not calculate its total by summing all country charts.

**These counts are the last confirmed local load results, not continuously updated counts.** Recheck them after any data refresh.

## 4. Repository layout

```text
Spotify Analytics/
├── .env                         # Local secrets; not committed
├── .gitignore
├── README.md                    # This file
├── requirements.txt             # Combined ETL/notebook + Django dependencies
│
├── backend/
│   ├── .venv/                   # Local virtual environment; do not commit
│   ├── manage.py
│   ├── requirements.txt         # Smaller backend-only dependency list
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── queries.py           # KPI and chart SQL queries
│   │   ├── detail_tables.py     # Bounded paginated table queries
│   │   ├── views.py             # Page and JSON API views
│   │   └── tests.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py          # Loads root .env and database configuration
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── analytics/
│   │   │   ├── global_pulse.html
│   │   │   ├── regional_rhythms.html
│   │   │   ├── hit_velocity.html
│   │   │   └── artist_deep_dive.html
│   │   └── partials/
│   │       ├── chart.html
│   │       ├── date_filters.html
│   │       ├── detail_table.html
│   │       └── table.html
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/
│   │       ├── charts.js
│   │       ├── detail-table.js
│   │       ├── filters.js
│   │       ├── main.js
│   │       └── visual-zoom.js
│   └── tests/                   # Additional backend tests
│
├── data/
│   └── raw/                     # Four original input CSVs
│
├── etl/
│   ├── eda/                     # Four exploratory notebooks
│   ├── cleaning/                # Four cleaning notebooks
│   ├── sql/
│   │   ├── spotify_analytics_stg_ddl.sql
│   │   ├── spotify_analytics_dw_ddl.sql
│   │   ├── spotify_analytics_stg_load.sql
│   │   ├── spotify_analytics_dw_load.sql
│   │   ├── album_artist_bridge.sql
│   │   ├── dashboard_indexes.sql
│   │   └── view_all_spotify_dw_tables.sql
│   └── load.py                  # Shared DataFrame-to-staging loader
│
└── test/
    └── test_etl.py
```

`__pycache__/`, `.venv/`, IDE caches, and local output files are generated artifacts rather than source code. Additional files might exist depending on the local branch.

## 5. Technology and dependencies

| Layer | Technologies |
| --- | --- |
| Language | Python 3.13 (local development) |
| Notebook environment | JupyterLab / Jupyter kernel |
| Data processing | pandas, NumPy |
| Exploratory visualization | Matplotlib, Seaborn |
| MySQL connectivity | PyMySQL for Django; MySQL Connector/Python included for compatible ETL loaders |
| Configuration | python-dotenv and project-root `.env` |
| Web framework | Django |
| Country metadata | pycountry |
| Browser visualization | JavaScript, Chart.js; map/visualization dependencies supplied through frontend assets where configured |
| Database | MySQL Server 8.0+ / MySQL Workbench |

The root `requirements.txt` installs a combined working environment. The existing `backend/requirements.txt` installs only the web application's Python dependencies. Browser-side JavaScript libraries are not installed by `pip`.

### Root versus backend requirements

- Use **root `requirements.txt`** when one Python environment will run notebooks, ETL, and Django.
- Use **`backend/requirements.txt`** when setting up only the website. This is lighter and fits the existing `backend/.venv` layout.
- Do not install both files separately into the same environment unless needed. Root requirements already include the backend's primary packages.
- The exact driver used by `etl/load.py` should be checked before running it. This README does not presume a particular loader command-line interface.

## 6. First-time setup on Windows

### Prerequisites

1. Install **Python 3.13** and ensure `py -3.13` works in PowerShell.
2. Install **MySQL Server 8.0+** and **MySQL Workbench**.
3. Install **VS Code** with the Python and Jupyter extensions.
4. Obtain the four CSV inputs and place them in `data/raw/`.
5. Ensure the MySQL service is running.

### Option A: Existing backend environment (recommended for the website)

From the project root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py check
python manage.py test analytics
python manage.py runserver
```

If `backend/.venv` does not exist, create it before activation:

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Open **http://127.0.0.1:8000/**. Stop the server using **Ctrl+C**. Use `deactivate` only when you want to leave the virtual environment.

### Option B: One environment for the entire project

From the project root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ipykernel install --user --name spotify-analytics --display-name "Python (Spotify Analytics)"
```

Select the `Python (Spotify Analytics)` kernel in VS Code or Jupyter. To start Django using the same root environment:

```powershell
cd backend
python manage.py check
python manage.py runserver
```

**Use either Option A or Option B consistently.** The existing project screenshot shows a backend-local `.venv`, so Option A is the least disruptive.

## 7. Environment configuration

Create one private `.env` at the **project root**, next to `README.md`. The supplied `backend/config/settings.py` loads this location.

```dotenv
# Django
DJANGO_SECRET_KEY=replace-with-a-generated-private-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# MySQL data warehouse for Django
DW_DB_NAME=spotify_analytics_dw
DW_DB_HOST=127.0.0.1
DW_DB_PORT=3306
DW_DB_USER=spotify_reader
DW_DB_PASSWORD=replace-with-your-password

# Optional staging settings for ETL scripts using these variable names
DB_NAME=spotify_analytics_stg
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=replace-with-your-staging-user
DB_PASSWORD=replace-with-your-staging-password
```

Generate a Django secret key after installing Django:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the generated key into the root `.env` file. Never commit `.env`, hard-code secrets, or publish a screenshot containing passwords. `DW_DB_USER=spotify_reader` is an example account name; create it in MySQL or use a valid local account. A read-only database account is preferred for the website.

### Django database behavior

`backend/config/settings.py` uses `django.db.backends.mysql` with a PyMySQL compatibility adapter (`pymysql.install_as_MySQLdb()`). This avoids the `mysqlclient` native DLL problem encountered on some managed Windows installations. It loads `DW_DB_*` variables first, with selected `DB_*` fallbacks for credentials/host/port. Verify the final database is `spotify_analytics_dw`, not the staging database.

## 8. Data engineering workflow

### Step 1. Exploratory data analysis

Open the four notebooks under `etl/eda/`. They examine dataset structure, null patterns, duplicates, distributions, chart rankings, streams, and temporal behavior. Their core Python libraries are pandas, NumPy, Matplotlib, and Seaborn.

### Step 2. Data cleaning

Run the corresponding notebooks under `etl/cleaning/`:

- `clean_songs_daily_365D.ipynb`
- `clean_artists_daily_365D.ipynb`
- `clean_albums_weekly_52W.ipynb`
- `clean_artists.ipynb`

The cleaning workflow standardizes source fields, retains essential chart identifiers and dates, handles missing optional measurements without inventing zero streams, and removes duplicates at the intended observation grain. Verify notebook paths and outputs before execution; do not assume all notebook cells can be executed in arbitrary order.

### Step 3. Stage cleaned records

The staging database is `spotify_analytics_stg`, with four cleaned source tables. The shared loader is `etl/load.py` and is intended to transfer cleaned DataFrames to MySQL.

**Safety:** `etl/sql/spotify_analytics_stg_ddl.sql` contains `DROP DATABASE IF EXISTS spotify_analytics_stg`. Do **not** rerun it against the populated database for ordinary website testing. The staging load script is also not necessary when the data is already present.

### Step 4. Load and maintain the warehouse

The database `spotify_analytics_dw` uses dimensional and fact tables together with materialized analytical aggregations.

- Eight dimensions: `dim_date`, `dim_geography`, `dim_artists`, `dim_track`, `dim_album`, `dim_label`, `dim_chart_type`, `dim_entry_status`.
- Main track-artist bridge: `bridge_track_artist`.
- Three performance facts: `fact_song_performance`, `fact_artists_performance`, `fact_album_performance`.
- KPI configuration fact: `fact_kpi_thresholds`.
- Nine aggregation tables: `agg_daily_global_summary`, `agg_country_share`, `agg_artist_momentum`, `agg_label_market_share`, `agg_track_velocity`, `agg_longevity_benchmarks`, `agg_new_entry_baseline`, `agg_regional_diversity`, `agg_artist_reach`.

The optional `bridge_album_artist` relationship is a separate extension for artist-specific album comparison.

**Safety:** `etl/sql/spotify_analytics_dw_ddl.sql` contains `DROP DATABASE IF EXISTS spotify_analytics_dw`. It is a destructive setup script, not a routine maintenance command. The website reads the existing populated warehouse and does not require running this DDL or reloading 10+ million fact records.

### Optional SQL extensions

| File | Role | When to execute |
| --- | --- | --- |
| `etl/sql/album_artist_bridge.sql` | Associate albums with credited artists | After backing up and validating source artist identifiers; needed for artist-specific album comparison |
| `etl/sql/dashboard_indexes.sql` | Add selected indexes on large fact tables | Only after reviewing existing indexes and confirming a query-performance need |
| `etl/sql/view_all_spotify_dw_tables.sql` | Inspect warehouse tables | Read-only inspection; review script contents before running |

Use MySQL Workbench → **File → Open SQL Script**, review the SQL, execute, and validate the results. Do not execute every SQL file in the folder indiscriminately.

## 9. Analytics dashboards

### Global Pulse

Purpose: market-wide streaming trends and chart freshness.

- KPI definitions: Total Streams vs Previous Period; Top 10 Chart Strength; New Entries vs Historical Baseline; Stream Momentum.
- Main visuals: top-track streams, daily stream trend, calendar heatmap, new/returning chart share.
- Filters: market, valid dates, and supported artist context.
- Detail table: track-level performance information appropriate to the chosen scope.

### Regional Rhythms

Purpose: regional comparison, label concentration, and local chart strength.

- Original KPIs: Leading Artist Volume; Unique Artist Count (Top 50); Change in Country Share.
- Supplementary KPI: Leading Record Label Market Share.
- Main visuals: strongest artists, label distribution, local/global track comparison, geographic view.
- Detail table: label and market-share information, with relevant filter context.

### Hit Velocity & Longevity

Purpose: climbing speed, chart persistence, and rank movement.

- Original KPIs: Average Chart Position Improvement; Maximum Track Longevity; Daily Rank Change.
- Supplementary KPI: Average Consecutive Chart Streak.
- Main visuals: entry-rank-versus-peak-rank scatter, longevity distribution by label, streak histogram, and rank movement over time.
- Detail table: entry/peak ranks, improvement, longevity and streak measures.

### Artist Deep-Dive

Purpose: one explicitly selected artist's listener peak, chart reach, credited-track streams, and album history.

- Original KPIs: Maximum Monthly Listeners; Distinct Country Count; Artist Stream Growth Rate.
- Supplementary KPI: Total Artist Streams.
- Main visuals: geographic footprint, daily stream trend, album longevity comparison.
- Detail table: artist's credited tracks and albums, depending on available relationships.
- **No artist is selected automatically.** The page prompts for a selection and displays artist-specific results only afterward.

**KPI and chart presence is conditional on supported data and filters.** The application may hide metrics without valid measurements or explain why a view is unavailable. Four KPIs per page represent the intended definitions, not a guarantee of four numeric values for every selection.

## 10. Interface and filter behavior

The current frontend design uses a black background with restrained glass panels and subtle green accents. Status-based KPI styling differentiates rising, falling, and stable performance. Individual KPI icons explain metric types. Charts have zoom controls and a reset function. Detail tables support bounded searches, sorting, pagination, and CSV export of the visible page.

### Capability-aware filters

- Only supported market and scope options should be available for the active page.
- Changing an artist updates available countries based on the observed chart history.
- Unsupported selections are reset rather than silently leaving stale charts on screen.
- Dates are constrained to relevant loaded periods.
- Artist Dedication Mode follows the selected artist; Artist Deep-Dive does not default to an arbitrary artist.
- Empty/unsupported visuals are not represented as zero or fabricated KPI values.
- The filters panel can be collapsed while retaining context.

### Important analytical distinctions

1. Source `GLOBAL` charts are distinct observations, **not** an addition of all country streams.
2. Some credited-artist stream measures allocate track streams **equally among credited artists**. They are derived attribution estimates, not Spotify-provided artist payments or individual audience counts.
3. The artist master table supplies recorded monthly-listener and peak fields, **not** a full monthly-listener time series; historical monthly-listener trends and percentile claims are unsupported without new data.
4. Weekly album charts contain rankings and weeks-on-chart but **no album stream counts** in the current staging schema.
5. A missing chart observation must not be interpreted automatically as zero activity.
6. Percent change requires a nonzero comparable previous period. When unavailable, explain the absence instead of assigning a misleading growth rate.

## 11. Main website routes and APIs

Run Django locally and use the following routes:

| Path | Description |
| --- | --- |
| `/` or `/global-pulse/` | Global Pulse |
| `/regional-rhythms/` | Regional Rhythms |
| `/hit-velocity/` | Hit Velocity & Longevity |
| `/artist-deep-dive/` | Artist Deep-Dive |
| `/api/global/` | Global Pulse JSON |
| `/api/regional/` | Regional Rhythms JSON |
| `/api/velocity/` | Velocity and longevity JSON |
| `/api/artist/` | Selected-artist JSON |
| `/api/table/<page>/` | Bounded detail-table JSON |
| `/api/artists/` | Artist name search |
| `/api/markets/` | Market lookup |
| `/api/filter-options/<page>/` | Capability-aware filter options |
| `/api/metadata/` | Date bounds and metadata |
| `/health/` | Basic application/database health response |

Endpoints and supported query parameters are implemented in `backend/config/urls.py` and `backend/analytics/views.py`. Use the browser's Network tab for actual request parameters. The APIs are for this site's local use; no authentication or public rate-limiting layer is documented here.

## 12. Testing and validation

### A. Application checks

From `backend/` with the correct environment active:

```powershell
python manage.py check
python manage.py test analytics
python manage.py runserver
```

`System check identified no issues` is a configuration check, not proof of correct business metrics. Django tests validate only assertions actually present in the test suite.

### B. Browser checks

1. Open all four pages and confirm navigation.
2. Select each supported filter; inspect KPI values, charts, and detail tables.
3. Clear artist selection; Artist Deep-Dive should show an intentional selection state.
4. Check supported KPI colors and visual icons.
5. Verify zoom slider and reset behavior in each visualization.
6. Expand a detail table; test search, sort, pagination and visible-page CSV export.
7. Use **F12 → Console and Network** to check JavaScript errors and failed API requests.
8. Test desktop and narrow browser widths.

### C. Warehouse reconciliation

```sql
USE spotify_analytics_dw;

SELECT COUNT(*) AS song_facts FROM fact_song_performance;
SELECT COUNT(*) AS artist_facts FROM fact_artists_performance;
SELECT COUNT(*) AS album_facts FROM fact_album_performance;

SELECT MIN(summary_date) AS first_day,
       MAX(summary_date) AS last_day,
       COUNT(*) AS observed_days
FROM agg_daily_global_summary;

SELECT SUM(total_streams) AS global_streams
FROM agg_daily_global_summary;
```

The previous fact-load reconciliation reported 5,124,654 song facts, 4,923,470 artist facts, and 526,800 album facts. These comparisons establish basic loading coverage, **not** full KPI correctness. For each KPI, reproduce its exact filters, status mapping, date range, and attribution rule in an independent SQL query.

### D. Testing evidence for the manuscript

Record the environment, test date, expected result, actual result, pass/fail status, screenshots, and any corrective action. Include test cases for absent previous periods, no selected artist, unsupported country selections, missing album bridge, and incomplete time coverage.

## 13. Common troubleshooting

| Symptom | Likely cause and first action |
| --- | --- |
| `No module named 'django'` | Activate the intended environment and install its requirements |
| `No module named 'pycountry'` | Install from `backend/requirements.txt` or root requirements |
| `No module named 'config.settings'` | Check `backend/config/settings.py` and `backend/config/__init__.py` |
| `DLL load failed ... MySQLdb` | Check that `settings.py` retains the PyMySQL compatibility setup; do not assume reinstalling a blocked native DLL solves the issue |
| `Access denied for user` | Verify warehouse credentials, host, and MySQL account grants in root `.env` |
| `/api/...` returns HTTP 500 | Read Django terminal traceback; check SQL schema and backend query |
| Charts missing despite page loading | Use DevTools Network/Console; verify API JSON, dates, and permitted filter combination |
| Empty album comparison for an artist | Verify `bridge_album_artist` exists and has validated relationships |
| Unsupported historical monthly KPI | The current artist master is not a monthly time series |
| Visual changes not showing | Hard-refresh browser with `Ctrl+Shift+R` after modifying static files |
| Workbench query takes too long | Check indexes and query plans; avoid scanning facts unnecessarily |
| Import paths broken in notebooks | Open the notebook in the intended working directory; inspect relative paths before rerunning |

## 14. Security, backup, and data handling

- Never commit `.env`, passwords, `.venv/`, caches, or generated data exports.
- Consider excluding large `data/raw/*.csv` files from Git or distributing them through a documented external source, depending on your team's agreed repository policy and licensing.
- Back up the populated warehouse through MySQL Workbench before changing schema or indexes.
- Review SQL scripts before execution. Both supplied *DDL* scripts include destructive `DROP DATABASE` statements.
- Use a dedicated read-only MySQL account for Django where practical.
- `DJANGO_DEBUG=True` is suitable only for local development. For deployment, configure a unique secret, explicit allowed hosts, static asset hosting, HTTPS, appropriate database permissions, and a production WSGI/ASGI server.
- Do not publish local debugging endpoints or database credentials on a publicly reachable server without an explicit security review.

## 15. Known limits and future work

The application analyzes chart-reported historical performance rather than Spotify's complete streaming universe. Country chart counts should be interpreted as chart appearances, not proof of listening activity in every region. Monthly-listener history is not present; album-to-artist attribution depends on an optional relationship table. Artist allocation across multiple credits is an analytical assumption. Some chart scopes and filter combinations cannot support every KPI.

Potential future work includes: validated time-series listener history, automated incremental loads, better market reference metadata, a documented data-quality scorecard, API authentication for public deployment, performance benchmarking, accessibility audits, and a formal usability study.

## 16. Manuscript and academic documentation

The original *Web-Based Spotify Analytics Dashboard* proposal documents four business problems and four planned pages. The final report should be updated **after** dashboard validation to include actual dates and record counts, the warehouse design, KPI formulas and caveats, capability-aware filters, screenshots, implementation evidence, test results, observed analytical findings, and limitations. The three supplementary KPIs should be documented separately from the original thirteen.

### Team

- Benedict S. Caliba
- Enrico Miguel Veloso
- John Dennis V. Vergara

**Institution:** University of Santo Tomas, College of Science, Department of Mathematics and Physics.  
**Course:** DSA 4157 – Business Intelligence.  
**Academic term:** 1st Term, AY 2026–2027.

## 17. Licensing and attribution

Source data is attributed to the Kaggle dataset **Spotify Charts Daily Updated** by Gonzalo López Gil, as identified in the project's proposal. Review its current licensing and permitted redistribution before publishing raw CSVs. Spotify and other third-party names or marks belong to their respective owners. A software license for the project itself has not been specified in the supplied materials; add a `LICENSE` file only after the team chooses one.
