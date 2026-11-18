# Spotify Analytics: ETL Execution and Data Refresh

This guide describes how to recreate MySQL analytics using fresh Kaggle extracts **without confusing notebook output with warehouse output**. The website reads `spotify_analytics_dw`; replacing `data/raw/*.csv` does not update website results by itself.

## Pipeline

```text
Kaggle source CSVs
    ↓
etl/extracting/spotify_daily_charts_extraction.ipynb
    ↓
data/raw/ (4 output CSVs + extraction_manifest.json)
    ↓
etl/eda/ (4 dataset-specific notebooks)
    ↓
etl/cleaning/ (4 dataset-specific notebooks)
    ↓
etl/load.py → spotify_analytics_stg (4 clean_* tables)
    ↓
etl/sql/spotify_analytics_dw_load.sql → spotify_analytics_dw
    ↓
Django dashboards → local browser
```

**Important:** `etl/load.py` is imported and called by the final cells of the current cleaning notebooks. Running those cells loads staging data. `load.py` is not an independent command-line ETL job with automatic CSV discovery.

## Files and what each one does

| File or directory | Job |
| --- | --- |
| `extracting/spotify_daily_charts_extraction.ipynb` | Extract 365 calendar days for daily chart sources, latest 52 observed chart dates for weekly albums, copy artist master |
| `eda/` | Inspect row counts, nulls, duplicates, date coverage and chart distributions |
| `cleaning/` | Normalize individual datasets and call `load_dataframe()` to replace respective staging tables |
| `load.py` | Validates destination columns, inserts DataFrame rows in batches, checks row count, commits or rolls back a given staging table |
| `sql/spotify_analytics_stg_ddl.sql` | **Destructive** first-time staging schema setup (`DROP DATABASE`) |
| `sql/spotify_analytics_dw_ddl.sql` | **Destructive** full warehouse rebuild (`DROP DATABASE`) |
| `sql/spotify_analytics_dw_load.sql` | Populate dimensions, replace performance facts, refresh aggregations, set KPI threshold rules |
| `sql/album_artist_bridge.sql` | Add artist-album relationships with `INSERT IGNORE`; does not clear stale links |
| `sql/dashboard_indexes.sql` | Optional query-performance indexes; avoid rerunning existing CREATE INDEX statements |
| `sql/view_all_spotify_dw_tables.sql` | Inspect warehouse data for validation |

The source notebooks and staging SQL must agree on column names and types. Before executing destructive scripts, inspect your **current checked-in versions** and retain a backup.

## A. Initial setup when databases do not exist

1. Complete dataset extraction following [`../data/raw/README.md`](../data/raw/README.md).
2. Install root dependencies in the project's Python environment and configure project-root `.env` with `DB_*` and `DW_DB_*` credentials (see root README).
3. Run `sql/spotify_analytics_stg_ddl.sql` in MySQL Workbench **once for a fresh staging database**. This script drops any existing staging database; never run against staging you intend to retain.
4. Run each EDA notebook. Resolve each input to the new `data/raw/` path and verify date range and record counts.
5. Run each cleaning notebook from start to finish. The final cell calls `etl/load.py` to **DELETE and INSERT** within a transaction into exactly one named staging table.
6. Check all four staging table counts and date coverage using the queries below.
7. Run `sql/spotify_analytics_dw_ddl.sql` to create a new warehouse **only after accepting that it deletes any existing warehouse of that name**.
8. Run `sql/spotify_analytics_dw_load.sql` in its documented **Section 1 dimensions → Section 2 facts → Section 3 aggregations** order; inspect error/output messages after each section.
9. Run `sql/album_artist_bridge.sql` if the warehouse/dashboard needs artist-album relationships. Run `sql/dashboard_indexes.sql` once if necessary, after checking existing indexes.
10. Validate warehouse row counts, data periods and KPIs. Start Django and compare the dashboard with SQL outputs.

## B. Workflow after extracting a newer rolling window

### 1. Preserve a snapshot

Archive your previous CSVs and `extraction_manifest.json` outside the Git repository, labelled by extraction date. Back up the current MySQL staging and warehouse databases using MySQL Workbench Data Export before changing records. Keep the original extraction inputs if final-report reproducibility matters.

### 2. Replace the four raw files

Download the updated ZIP from Kaggle, extract it and place its four CSV files in `data/raw/` **using the same filenames**. Confirm the new manifest date range and row counts. Do not leave multiple old copies of identically named CSVs scattered through notebook working directories.

### 3. Repeat EDA and cleaning

Restart each Jupyter kernel and **Run All** in the EDA notebooks. Check printed absolute input path, earliest/latest dates, unique chart dates, missing fields and chart-key duplicates. Then run the four cleaning notebooks in the same fashion. Each successful final load cell transactionally **replaces one staging table**; verify all four have completed before touching the warehouse. Avoid rerunning `sql/spotify_analytics_stg_ddl.sql` for normal refreshes.

### 4. Verify the staging database

Run in MySQL Workbench:

```sql
USE spotify_analytics_stg;

SELECT 'songs' AS dataset, COUNT(*) AS rows_loaded FROM clean_songs_daily_365D
UNION ALL SELECT 'daily_artists', COUNT(*) FROM clean_artists_daily_365D
UNION ALL SELECT 'weekly_albums', COUNT(*) FROM clean_albums_weekly_52W
UNION ALL SELECT 'artist_master', COUNT(*) FROM clean_artists;

SELECT MIN(`date`) AS first_day, MAX(`date`) AS last_day,
       COUNT(DISTINCT `date`) AS observed_days
FROM clean_songs_daily_365D;

SELECT MIN(`date`) AS first_day, MAX(`date`) AS last_day,
       COUNT(DISTINCT `date`) AS observed_days
FROM clean_artists_daily_365D;

SELECT MIN(week_start_date) AS first_week, MAX(week_start_date) AS last_week,
       COUNT(DISTINCT week_start_date) AS observed_weeks
FROM clean_albums_weekly_52W;
```

For weekly staging, use `week_start_date`, **not** `date`. Expect around 52 distinct chart weeks if the extract and load completed correctly. Daily artists might have fewer observed dates than the 365-day period.

Check that loaded row counts match the cleaning notebooks. Investigate differences before running warehouse loads.

### 5. Update the warehouse safely

**Recommended for a fully replaced rolling-year dataset: controlled full warehouse rebuild.** This produces a clean dimensional snapshot without leaving old artist, track, album or bridge references from the prior window.

1. Export/back up `spotify_analytics_dw`.
2. Confirm all four staging tables contain the new cleaned dataset.
3. Review `sql/spotify_analytics_dw_ddl.sql`: it contains `DROP DATABASE IF EXISTS spotify_analytics_dw`. Execute **only when intentionally rebuilding**.
4. Run `sql/spotify_analytics_dw_load.sql` in its own prescribed order: dimensions, facts, KPI thresholds, aggregations. Do not skip the aggregation section.
5. Run `sql/album_artist_bridge.sql` if needed for artist-album attribution. Create dashboard indexes only when not already present.
6. Run the warehouse validation queries below.

**Alternative: in-place refresh for experienced maintainers.** The DW load uses `TRUNCATE` for fact tables and `DELETE`/reinsert for aggregations. `TRUNCATE` auto-commits in MySQL; do not assume a rollback restores prior facts. Dimension upserts and `INSERT IGNORE` bridge loads can **retain entities/links from old windows**. Only use an in-place process after auditing deletion rules, referential integrity, stale dimension/bridge rows and load order. Re-running the warehouse load blindly is **not a guaranteed clean rolling-window replacement**.

Do **not** rerun staging DDL for routine refresh. Do **not** rerun indexes without checking whether they already exist.

### 6. Validate the refreshed warehouse

```sql
USE spotify_analytics_dw;

SELECT 'songs' AS fact, COUNT(*) AS rows_loaded FROM fact_song_performance
UNION ALL SELECT 'daily_artists', COUNT(*) FROM fact_artists_performance
UNION ALL SELECT 'weekly_albums', COUNT(*) FROM fact_album_performance;

-- Date coverage uses the warehouse date dimension.
SELECT MIN(d.full_date) AS first_day, MAX(d.full_date) AS last_day,
       COUNT(DISTINCT d.full_date) AS observed_days
FROM fact_song_performance f
JOIN dim_date d ON d.date_id = f.date_id;

SELECT MIN(d.full_date) AS first_week, MAX(d.full_date) AS last_week,
       COUNT(DISTINCT d.full_date) AS observed_weeks
FROM fact_album_performance f
JOIN dim_date d ON d.date_id = f.date_id;

SELECT kpi_name, threshold_type, high_value, moderate_lower, moderate_upper, low_value
FROM fact_kpi_thresholds;
```

Confirm facts and aggregation tables contain expected records. Do not compare weekly album dates against daily song dates as if the same reporting calendar were required.

### 7. Test the website after refreshing MySQL

From your project root in PowerShell:

```powershell
.\backend\.venv\Scripts\Activate.ps1
cd backend
python manage.py check
python manage.py test
python manage.py runserver
```

Open http://127.0.0.1:8000/. Check all five analytical pages, especially filter behavior, date ranges, threshold colors, chart data and weekly album embeds. The site reflects database updates on fresh requests after the warehouse has been refreshed; **it does not schedule Kaggle downloads or run ETL automatically**.

## C. When something goes wrong

| Issue | Likely check |
| --- | --- |
| EDA shows previous dates | Print the path of the opened CSV, check its file timestamp and restart the notebook kernel |
| Jupyter hangs at extraction or processing | Run cells individually; check memory/CPU and any active MySQL transaction |
| Weekly SQL says unknown `date` column | Query staging `week_start_date` |
| Some dates absent in daily artists | Check source chart observations rather than filling with invented records |
| Newly cleaned data is invisible in Django | Confirm **DW facts and aggregates** were refreshed; staging updates alone are insufficient |
| KPI colors unexpected | Check `fact_kpi_thresholds` plus values/classifications returned by dashboard queries |
| Album images do not appear | Check valid album URI, browser connectivity and Spotify availability |
| SQL script fails midway | Do not repeatedly rerun destructive statements; inspect which sections committed and restore from backup if required |

## D. Academic reproducibility checklist

- [ ] Original Kaggle source title/URL and dataset version recorded.
- [ ] New `extraction_manifest.json` retained with the freeze date.
- [ ] Four raw CSV filenames and file counts verified.
- [ ] EDA and cleaning notebooks rerun from a restarted kernel.
- [ ] Staging rows and date coverage match cleaned data.
- [ ] Warehouse facts, aggregates and KPI thresholds validated.
- [ ] Dashboard filters, trends, album previews and KPI statuses checked.
- [ ] Final report names the specific frozen extraction window.

The warehouse contains the analytical data used by the website, while GitHub contains the reusable processing code and documentation.
