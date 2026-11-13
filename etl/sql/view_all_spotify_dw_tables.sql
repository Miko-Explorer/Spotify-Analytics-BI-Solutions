-- Spotify Analytics | Data Warehouse Table Viewer
-- Purpose: list and preview all warehouse tables in MySQL Workbench.
-- Read-only: no data is inserted, updated, or deleted.
-- Each SELECT produces a separate Result Grid (up to 10 rows per table).

USE spotify_analytics_dw;

-- 1. List every table in the warehouse
SHOW FULL TABLES;

-- 2. Optional lightweight size overview (InnoDB row counts are ESTIMATES)
SELECT
    TABLE_NAME AS table_name,
    TABLE_ROWS AS estimated_rows
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'spotify_analytics_dw'
  AND TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;

-- 3. Dimension table previews
SELECT * FROM dim_date LIMIT 10;
SELECT * FROM dim_geography LIMIT 10;
SELECT * FROM dim_artists LIMIT 10;
SELECT * FROM dim_track LIMIT 10;
SELECT * FROM dim_album LIMIT 10;
SELECT * FROM dim_label LIMIT 10;
SELECT * FROM dim_chart_type LIMIT 10;
SELECT * FROM dim_entry_status LIMIT 10;

-- 4. Track-artist relationship preview
SELECT * FROM bridge_track_artist LIMIT 10;

-- 5. Fact table previews
SELECT * FROM fact_song_performance LIMIT 10;
SELECT * FROM fact_artists_performance LIMIT 10;
SELECT * FROM fact_album_performance LIMIT 10;
SELECT * FROM fact_kpi_thresholds LIMIT 10;

-- 6. Dashboard aggregation previews
SELECT * FROM agg_daily_global_summary LIMIT 10;
SELECT * FROM agg_country_share LIMIT 10;
SELECT * FROM agg_artist_momentum LIMIT 10;
SELECT * FROM agg_label_market_share LIMIT 10;
SELECT * FROM agg_track_velocity LIMIT 10;
SELECT * FROM agg_longevity_benchmarks LIMIT 10;
SELECT * FROM agg_new_entry_baseline LIMIT 10;
SELECT * FROM agg_regional_diversity LIMIT 10;
SELECT * FROM agg_artist_reach LIMIT 10;

-- 7. Optional: see the CREATE TABLE definition for any table
-- SHOW CREATE TABLE dim_artists;
