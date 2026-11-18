# Spotify Analytics

**Spotify Business Intelligence Dashboard | Final V10.8**  
University of Santo Tomas · College of Science · DSA 4157 Business Intelligence · AY 2026–2027  
**Group 2, 3DSA2**

## Project overview

Spotify Analytics is a locally hosted Business Intelligence website for exploring historical Spotify chart data. It combines a Kaggle extraction notebook, Python/Jupyter exploratory data analysis (EDA) and cleaning, MySQL staging and dimensional warehousing, and a Django dashboard built with Chart.js.

The website is intended for music listeners, artists, researchers, and business users who want understandable answers about chart performance, regional trends, rising hits, artist reach, and weekly album rankings. It is **not** a live Spotify listening tracker. Dashboard results represent the chart snapshots already processed and loaded into the local MySQL warehouse.

## Explore the website

The landing page (`/`) is a **Start Here / Dashboard Guide** explaining the measures and visualizations in plain language. Five analytical pages follow:

| Page | URL | Purpose |
| --- | --- | --- |
| Global Pulse | `/global-pulse/` | Streaming volume, leading tracks and daily chart activity |
| Regional Rhythms | `/regional-rhythms/` | Differences between country charts, markets, artists and labels |
| Hit Velocity & Longevity | `/hit-velocity/` | Song chart movement, ranking improvement and persistence |
| Artist Deep-Dive | `/artist-deep-dive/` | Selected artist's credited-track performance and major markets |
| Weekly Album Insights | `/weekly-albums/` | Weekly album rankings, longevity and chart-entry patterns |

### Final interface features

- Dark glassmorphism styling, distinct SVG sidebar icons, Outfit KPI typography and restrained animations.
- KPI status colors based on warehouse thresholds or meaningful supported classifications. Measures without suitable thresholds remain neutral.
- Filter-aware charts, visible data-point markers on line graphs, hover tooltips, chart zoom and reset controls.
- Searchable, sortable and paginated detail tables, including export of the current visible page.
- Dedicated weekly album analysis and official Spotify album embeds when valid album URIs and browser availability permit.
- Weekly Album Insights shows three general charts when no artist is selected: **New Albums on the Weekly Chart**, **Top 10 Album Staying Power Over Time**, and **Where Albums Rank on the Weekly Chart**. With an artist selected, it uses two artist-focused visualizations: **Top 10 Albums by Best Chart Position** and **Where Albums Rank on the Weekly Chart**. Empty results are hidden.
- Artist Deep-Dive requires explicit artist selection; it does not silently select an artist.

### Interpretation

Spotify source chart entries are historical observations rather than individual user listening histories. The `GLOBAL` chart is its own source market: do not add country-specific stream totals to derive a supposedly equivalent global total. Lower numeric chart ranks are better (rank 1 is strongest). Album charts are weekly, while song and artist charts are daily. Some daily artist dates have no observations.

## Dataset and reproducibility

The source is **Spotify Charts Daily Updated**, attributed to Gonzalo López Gil on Kaggle. The four required local files are:

| `data/raw/` filename | Description |
| --- | --- |
| `charts_songs_daily_365D.csv` | Latest 365-day window based on the song source's latest available date |
| `charts_artists_daily_365D.csv` | Latest 365-day window based on the artist-chart source's latest available date |
| `charts_albums_weekly_52W.csv` | Latest 52 *observed* weekly chart dates |
| `artists.csv` | Artist reference file copied unchanged from the Kaggle input |

Raw CSVs are excluded from Git because of their size. To recreate them, follow **[Raw Data Acquisition](data/raw/README.md)** using the extraction notebook in `etl/extracting/`. The extraction process also produces `extraction_manifest.json`, which records selected periods and row counts. Keep a dated copy of the inputs and manifest used for final capstone evaluation so results remain reproducible.

**Note:** `365D` specifies the intended calendar window, not 365 guaranteed chart observations; artist daily charts previously contained 353 distinct dates. Weekly start/end dates need not equal daily start/end dates.

## Project structure

```text
Spotify Analytics/
├── README.md
├── requirements.txt             # Combined Python/Jupyter/Django dependencies
├── .env                         # Local secrets: NEVER commit
├── .gitignore
├── data/
│   └── raw/
│       └── README.md            # Acquisition instructions; downloaded CSVs stay local
├── etl/
│   ├── README.md                # First setup and later refresh instructions
│   ├── extracting/
│   │   └── spotify_daily_charts_extraction.ipynb
│   ├── eda/                     # Four dataset-specific EDA notebooks
│   ├── cleaning/                # Four dataset-specific cleaning notebooks
│   ├── load.py                  # Shared cleaned-DataFrame staging loader
│   └── sql/
│       ├── spotify_analytics_stg_ddl.sql
│       ├── spotify_analytics_dw_ddl.sql
│       ├── spotify_analytics_dw_load.sql
│       ├── album_artist_bridge.sql
│       ├── dashboard_indexes.sql
│       └── view_all_spotify_dw_tables.sql
└── backend/
    ├── manage.py
    ├── requirements.txt
    ├── .venv/                   # Local environment: NEVER commit
    ├── analytics/               # Django views, SQL-backed queries, tests
    ├── config/                  # Settings and URL routes
    ├── templates/               # Guide and five dashboards
    └── static/                  # CSS, JS, charts and icons
```

Names reflect the project structure shown in the repository. If your local extraction notebook or SQL files have different names, use the actual checked-in names and update links accordingly.

## Requirements

- Python 3.13 (project development version).
- MySQL 8.0+ and MySQL Workbench.
- VS Code with Python/Jupyter support or another Jupyter-compatible environment.
- Browser with JavaScript enabled; internet access for Spotify embeds.
- Kaggle account for the source dataset and hosted extraction notebook.

The combined root `requirements.txt` installs pandas, notebook libraries, MySQL Connector/Python, Django and PyMySQL. Django uses PyMySQL, while the ETL loader uses `mysql.connector`.

## First-time local setup

Open PowerShell from the project root:

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create `Spotify Analytics/.env`, using `backend/.env.example` as a reference. Example variable names (replace placeholders with your own values):

```dotenv
DJANGO_SECRET_KEY=replace-with-a-private-random-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_staging_mysql_user
DB_PASSWORD=your_staging_mysql_password
DW_DB_HOST=127.0.0.1
DW_DB_PORT=3306
DW_DB_NAME=spotify_analytics_dw
DW_DB_USER=your_warehouse_read_only_user
DW_DB_PASSWORD=your_warehouse_password
```

Keep `.env` private. The staging loader uses `DB_USER` / `DB_PASSWORD`; the Django application prefers `DW_DB_*` credentials and reads the warehouse `spotify_analytics_dw`. A read-only warehouse user is recommended for the website.

### Build the data pipeline once

1. Use `etl/extracting/spotify_daily_charts_extraction.ipynb` in Kaggle. Place its four output CSVs in `data/raw/`.
2. Run all four notebooks in `etl/eda/` and check filenames, source paths, date coverage and missing values.
3. In MySQL Workbench, run `etl/sql/spotify_analytics_stg_ddl.sql` **only when initializing an empty staging database**. This script drops and recreates `spotify_analytics_stg`.
4. Run each notebook in `etl/cleaning/`. Their final loading cells call `etl/load.py` and replace the corresponding staging table with the cleaned DataFrame. **Do not run the loader a second time unless intentionally reloading.**
5. Verify all four staging tables, row counts and date coverage.
6. Back up any existing warehouse, then run `etl/sql/spotify_analytics_dw_ddl.sql` **only for an intentional full warehouse rebuild**. It drops and recreates `spotify_analytics_dw`.
7. Execute `etl/sql/spotify_analytics_dw_load.sql` in the documented dimension → fact → aggregation sequence. Review section output before proceeding; some fact loading operations use irreversible MySQL `TRUNCATE`.
8. Run `etl/sql/album_artist_bridge.sql` if artist-album relationships are needed, and apply `etl/sql/dashboard_indexes.sql` **once** if those indexes do not already exist. Inspect data with `etl/sql/view_all_spotify_dw_tables.sql`.
9. Validate dashboard counts and charts against the corresponding warehouse queries.

For the safe procedure after extracting newer data, read **[ETL Refresh and Validation](etl/README.md)**. Do not repeat the destructive DDL steps merely to restart the website.

## Running the website

From the repository root in PowerShell:

```powershell
.\backend\.venv\Scripts\Activate.ps1
cd backend
python manage.py check
python manage.py test
python manage.py runserver
```

Open **http://127.0.0.1:8000/**. The `/` route opens the dashboard guide. Use `Ctrl + C` to stop the server. Refresh with `Ctrl + F5` after changing CSS or JavaScript.

The test suite checks backend behavior but does not independently certify the contents of the current MySQL warehouse. Verify SQL results against the refreshed source extracts.

## Maintaining up-to-date data

Replacing raw CSVs alone does **not** update the website. Re-extract → rerun EDA/cleaning → replace staging → refresh or rebuild the warehouse → validate → reload the website. The site reads the warehouse; it does not download Kaggle files in the background.

A full rebuild is the documented reproducible approach for a complete rolling-window replacement, **after backing up the warehouse**. In-place refresh requires reviewing dimension and bridge retention as well as fact and aggregation replacement. See `etl/README.md` for both safety notes and validation queries.

## Common problems

| Symptom | What to check |
| --- | --- |
| `No module named django` | Activate `backend/.venv` and install project dependencies |
| Notebook still reports old dates | Verify printed CSV path, replace the file in `data/raw/`, restart the kernel and rerun cells |
| `Unknown column 'date'` for weekly albums | Cleaned weekly staging uses `week_start_date`; daily staging uses `date` |
| Empty or hidden charts | Check selected artist, market/date filters, available records and warehouse refresh |
| Album artwork unavailable | Confirm album URI, Spotify embedding availability and browser connectivity |
| Django test fails but server starts | Review the specific test traceback; a passing system check does not guarantee test success |
| Unchanged dashboard after ETL | Confirm the **warehouse**, not only the staging tables, was refreshed |

## GitHub repository and data policy

- Commit source code, notebooks, SQL, documentation and dependency files.
- Exclude `.env`, `.venv`, caches, local database exports, raw CSVs and large extracted archives.
- Ensure `.gitignore` includes:

```gitignore
/data/raw/*
!/data/raw/README.md
.env
.venv/
__pycache__/
*.pyc
```

Avoid uploading Kaggle API credentials or redistributing source data without checking the source license. The dataset source is external; this repository documents reproducible extraction rather than distributing the large source files.

## Limitations and attribution

The project is a local, historical BI application. Its results change when source charts change and the ETL pipeline is rerun. Artist streams and chart positions represent the available chart dataset, not unrestricted Spotify account data. Weekly album analysis does not imply daily album stream counts. Spotify album artwork is presented through official embeds when possible and is governed by Spotify's embed terms and content availability.

**Data attribution:** Gonzalo López Gil, *Spotify Charts Daily Updated*, Kaggle. The extraction instructions in `data/raw/README.md` explain how to locate the source and record the exact dataset version. Review source licensing before reuse or republication.
