-- SPOTIFY ANALYTICS | SIMPLE DATA WAREHOUSE LOAD | MySQL 8+
-- Matches spotify_analytics_stg_ddl_revised.sql and spotify_analytics_dw_ddl_revised.sql.
-- NO stored procedures, batch loops, or whole-history window ranking for facts.
-- Run marked sections independently in MySQL Workbench. Fact inserts use full history.
-- PREREQUISITES: staging loaded and cleaning notebooks have removed duplicate chart keys.
-- SECTION 1 automatically fills any missing calendar dates (1900-2100).
-- This script does NOT create/drop any database or table.
-- Optional measures remain NULL. Descriptive labels may use Unknown.
USE spotify_analytics_dw;
SET @original_safe_updates = @@SESSION.SQL_SAFE_UPDATES;
SET SESSION SQL_SAFE_UPDATES = 0;

-- ================================================================
-- SECTION 1: DIMENSIONS (run once after each staging refresh)
-- ================================================================
-- 1. DATE DIMENSION: every calendar date from 1900-01-01 to 2100-12-31.
-- Uses set-based number generation, not a stored procedure or day-by-day loop.
-- The UNIQUE key on full_date prevents repeat inserts on later runs.
-- Existing calendar rows are preserved, including their is_holiday values.
SET @calendar_start = DATE('1900-01-01');
SET @calendar_end   = DATE('2100-12-31');

INSERT INTO dim_date
    (full_date, `year`, `month`, day_of_week, is_weekend, `quarter`, is_holiday)
SELECT
    calendar.full_date,
    YEAR(calendar.full_date),
    MONTH(calendar.full_date),
    WEEKDAY(calendar.full_date) + 1,   -- Monday=1, Sunday=7
    WEEKDAY(calendar.full_date) >= 5,
    QUARTER(calendar.full_date),
    NULL                             -- no unverified holiday assignments
FROM (
    SELECT DATE_ADD(@calendar_start, INTERVAL offsets.day_number DAY) AS full_date
    FROM (
        SELECT ones.n + tens.n * 10 + hundreds.n * 100
             + thousands.n * 1000 + ten_thousands.n * 10000 AS day_number
        FROM (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) ones
        CROSS JOIN (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) tens
        CROSS JOIN (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) hundreds
        CROSS JOIN (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) thousands
        CROSS JOIN (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) ten_thousands
    ) offsets
    WHERE offsets.day_number <= DATEDIFF(@calendar_end, @calendar_start)
) calendar
LEFT JOIN dim_date existing ON existing.full_date = calendar.full_date
WHERE existing.date_id IS NULL;

-- Confirm calendar completeness before fact loading (expected: 73,414).
SELECT COUNT(*) AS calendar_dates,
       MIN(full_date) AS earliest_date,
       MAX(full_date) AS latest_date,
       DATEDIFF(@calendar_end, @calendar_start) + 1 AS expected_dates
FROM dim_date
WHERE full_date BETWEEN @calendar_start AND @calendar_end;

-- 2. CHART TYPES, STATUS CATEGORIES
INSERT INTO dim_chart_type(type_name)
VALUES ('Daily Song'), ('Weekly Album'), ('Artist Rank')
ON DUPLICATE KEY UPDATE chart_type_id = chart_type_id;
INSERT INTO dim_entry_status(status_name)
VALUES ('NEW'), ('RE-ENTRY'), ('CONTINUING')
ON DUPLICATE KEY UPDATE status_id = status_id;

-- 3. LABELS (original name/casing preserved)
INSERT INTO dim_label(label_name)
SELECT DISTINCT TRIM(label) FROM (
    SELECT label FROM spotify_analytics_stg.clean_songs_daily_365D
    UNION ALL
    SELECT label FROM spotify_analytics_stg.clean_albums_weekly_52W
) x
WHERE label IS NOT NULL AND TRIM(label) <> ''
ON DUPLICATE KEY UPDATE label_id = label_id;

-- 4. GEOGRAPHY: only source country codes are available.
-- country_name temporarily equals the code; region/tier remain unknown (NULL).
INSERT INTO dim_geography(country_code, country_name, region, market_tier)
SELECT DISTINCT UPPER(TRIM(country)), UPPER(TRIM(country)), NULL, NULL
FROM (
    SELECT country FROM spotify_analytics_stg.clean_songs_daily_365D
    UNION ALL SELECT country FROM spotify_analytics_stg.clean_artists_daily_365D
    UNION ALL SELECT country FROM spotify_analytics_stg.clean_albums_weekly_52W
) x
WHERE country IS NOT NULL AND TRIM(country) <> ''
ON DUPLICATE KEY UPDATE geo_id = geo_id; -- retain later geography enrichment

-- 5. ARTISTS: keep every unique URI, preferring master-record names and measures.
-- The source master table is keyed on artist_uri, so GROUP BY is unnecessary.
INSERT INTO dim_artists
 (artist_uri, artist_name, monthly_listeners, monthly_listeners_rank,
  monthly_listeners_peak, peak_listener_rank)
SELECT artist_uri, NULLIF(artist_name,''), monthly_listeners, monthly_listeners_rank,
       monthly_listeners_peak_listeners, monthly_listeners_peak_rank
FROM spotify_analytics_stg.clean_artists
WHERE artist_uri IS NOT NULL AND artist_uri <> ''
ON DUPLICATE KEY UPDATE
 artist_name = COALESCE(VALUES(artist_name), dim_artists.artist_name),
 monthly_listeners = VALUES(monthly_listeners),
 monthly_listeners_rank = VALUES(monthly_listeners_rank),
 monthly_listeners_peak = VALUES(monthly_listeners_peak),
 peak_listener_rank = VALUES(peak_listener_rank);

-- Add missing URIs from daily artist charts WITHOUT expensive name lookups.
-- Master source supplies names/metrics; chart-only artists remain with unknown name.
INSERT INTO dim_artists(artist_uri,artist_name)
SELECT DISTINCT s.artist_uri, 'Unknown Artist'
FROM spotify_analytics_stg.clean_artists_daily_365D s
WHERE s.artist_uri IS NOT NULL AND s.artist_uri <> ''
ON DUPLICATE KEY UPDATE artist_id=artist_id;

-- 6. TRACK AND ALBUM DIMENSIONS
-- Lightweight deterministic metadata per URI. The chosen metadata is the
-- lexicographically smallest non-null source value, NOT necessarily newest.
-- For changing metadata, curate dimensions separately after the initial load.
INSERT INTO dim_track(track_uri,track_name,release_date,label_id)
SELECT x.track_uri, COALESCE(x.track_name, 'Unknown Track'), x.release_date, l.label_id
FROM (
 SELECT track_uri, MIN(NULLIF(track_name,'')) track_name, MIN(release_date) release_date,
        MIN(NULLIF(label,'')) label_name
 FROM spotify_analytics_stg.clean_songs_daily_365D
 WHERE track_uri IS NOT NULL AND track_uri <> ''
 GROUP BY track_uri
) x LEFT JOIN dim_label l ON l.label_name=x.label_name
ON DUPLICATE KEY UPDATE
 track_name=COALESCE(dim_track.track_name,VALUES(track_name)),
 release_date=COALESCE(dim_track.release_date,VALUES(release_date)),
 label_id=COALESCE(dim_track.label_id,VALUES(label_id));

INSERT INTO dim_album(album_uri,album_name,release_year,label_id)
SELECT x.album_uri, COALESCE(x.album_name, 'Unknown Album'), x.release_year, l.label_id
FROM (
 SELECT album_uri, MIN(NULLIF(album_name,'')) album_name,
        MIN(YEAR(release_date)) release_year, MIN(NULLIF(label,'')) label_name
 FROM spotify_analytics_stg.clean_albums_weekly_52W
 WHERE album_uri IS NOT NULL AND album_uri <> ''
 GROUP BY album_uri
) x LEFT JOIN dim_label l ON l.label_name=x.label_name
ON DUPLICATE KEY UPDATE
 album_name=COALESCE(dim_album.album_name,VALUES(album_name)),
 release_year=COALESCE(dim_album.release_year,VALUES(release_year)),
 label_id=COALESCE(dim_album.label_id,VALUES(label_id));

-- 7. TRACK-ARTIST BRIDGE. Source artist_uris uses '|' separators.
-- JSON_QUOTE escapes source characters before JSON_TABLE splits them.
-- Normalize Spotify URI prefix; unknown contributing artists are inserted
-- as dimension placeholders, without fabricating names or listener metrics.
DROP TEMPORARY TABLE IF EXISTS tmp_spotify_track_artists;
CREATE TEMPORARY TABLE tmp_spotify_track_artists (
 track_uri VARCHAR(100) NOT NULL,
 artist_uri VARCHAR(100) NOT NULL,
 PRIMARY KEY(track_uri, artist_uri)
) ENGINE=InnoDB;
INSERT IGNORE INTO tmp_spotify_track_artists(track_uri, artist_uri)
SELECT s.track_uri,
       TRIM(REPLACE(j.artist_value, 'spotify:artist:', '')) AS artist_uri
FROM (
  SELECT DISTINCT track_uri, artist_uris
  FROM spotify_analytics_stg.clean_songs_daily_365D
  WHERE artist_uris IS NOT NULL AND TRIM(artist_uris) <> ''
) s
CROSS JOIN JSON_TABLE(
  CONCAT('[', REPLACE(JSON_QUOTE(s.artist_uris), '|', '","'), ']'),
  '$[*]' COLUMNS(artist_value VARCHAR(200) PATH '$')
) j
WHERE NULLIF(TRIM(REPLACE(j.artist_value, 'spotify:artist:', '')), '') IS NOT NULL;
INSERT INTO dim_artists(artist_uri,artist_name)
SELECT DISTINCT artist_uri, 'Unknown Artist' FROM tmp_spotify_track_artists
WHERE artist_uri <> ''
ON DUPLICATE KEY UPDATE artist_id=artist_id;

-- Insert missing collaboration pairs. Existing pairs remain unchanged.
INSERT IGNORE INTO bridge_track_artist(track_id, artist_id, `role`)
SELECT t.track_id, a.artist_id, NULL
FROM tmp_spotify_track_artists p
JOIN dim_track t ON t.track_uri = p.track_uri
JOIN dim_artists a ON a.artist_uri = p.artist_uri;
DROP TEMPORARY TABLE IF EXISTS tmp_spotify_track_artists;

-- ================================================================
-- SECTION 2: FACTS (ONE DIRECT FULL-HISTORY INSERT PER FACT TABLE)
-- ================================================================
-- Execute each table's TRUNCATE + INSERT separately in MySQL Workbench.
-- Load in this order: Songs, Artists, Albums, then KPI thresholds below.
-- The tables already contain one-day diagnostic records from previous tests.
-- TRUNCATE removes those previous facts, avoiding duplicate observations.
-- IMPORTANT: TRUNCATE permanently clears each fact table and commits immediately.
-- Back up your facts before executing if existing records must be retained.
-- Do NOT rerun a completed table's INSERT unless first refreshing that table.
-- These full-history queries may still exceed Workbench's 600-second timeout.
-- If an INSERT times out, confirm the server query is no longer running,
-- then use the monthly fallback described in the companion README.
-- The source cleaning notebooks must already have resolved duplicate chart keys.
-- All SQL below preserves the previous status mapping and optional NULL values.

-- 2A. DAILY SONGS: entire cleaned history.
TRUNCATE TABLE fact_song_performance;
INSERT INTO fact_song_performance (date_id, geo_id, track_id, `rank`, streams, peak_rank, previous_rank, days_on_chart, consecutive_days, entry_rank, entry_status_id)
SELECT d.date_id, g.geo_id, e.track_id, s.`rank`, s.streams, s.peak_rank, NULLIF(s.previous_rank, 0), s.days_on_chart, s.consecutive_days, s.entry_rank, es.status_id
FROM spotify_analytics_stg.clean_songs_daily_365D s
JOIN dim_date d ON d.full_date = s.`date`
JOIN dim_geography g ON g.country_code = s.country
JOIN dim_track e ON e.track_uri = s.track_uri
LEFT JOIN dim_entry_status es ON es.status_name = CASE
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('NEW', 'NEW ENTRY') THEN 'NEW'
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('RE ENTRY', 'REENTRY') THEN 'RE-ENTRY'
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('CONTINUING', 'MOVED UP', 'MOVED DOWN', 'NO CHANGE') THEN 'CONTINUING'
  ELSE NULL END;
SELECT 'SONGS' AS dataset, COUNT(*) AS loaded_rows FROM fact_song_performance;

-- 2B. DAILY ARTISTS: entire cleaned history.
TRUNCATE TABLE fact_artists_performance;
INSERT INTO fact_artists_performance (date_id, geo_id, artist_id, `rank`, peak_rank, previous_rank, days_on_chart, consecutive_days, entry_rank, entry_status_id)
SELECT d.date_id, g.geo_id, e.artist_id, s.`rank`, s.peak_rank, NULLIF(s.previous_rank, 0), s.days_on_chart, s.consecutive_days, s.entry_rank, es.status_id
FROM spotify_analytics_stg.clean_artists_daily_365D s
JOIN dim_date d ON d.full_date = s.`date`
JOIN dim_geography g ON g.country_code = s.country
JOIN dim_artists e ON e.artist_uri = s.artist_uri
LEFT JOIN dim_entry_status es ON es.status_name = CASE
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('NEW', 'NEW ENTRY') THEN 'NEW'
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('RE ENTRY', 'REENTRY') THEN 'RE-ENTRY'
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('CONTINUING', 'MOVED UP', 'MOVED DOWN', 'NO CHANGE') THEN 'CONTINUING'
  ELSE NULL END;
SELECT 'ARTISTS' AS dataset, COUNT(*) AS loaded_rows FROM fact_artists_performance;

-- 2C. WEEKLY ALBUMS: entire cleaned history; date key is week_start_date.
TRUNCATE TABLE fact_album_performance;
INSERT INTO fact_album_performance (date_id, geo_id, album_id, `rank`, peak_rank, previous_rank, weeks_on_chart, consecutive_weeks, entry_rank, entry_status_id)
SELECT d.date_id, g.geo_id, e.album_id, s.`rank`, s.peak_rank, NULLIF(s.previous_rank, 0), s.weeks_on_chart, s.consecutive_weeks, s.entry_rank, es.status_id
FROM spotify_analytics_stg.clean_albums_weekly_52W s
JOIN dim_date d ON d.full_date = s.`week_start_date`
JOIN dim_geography g ON g.country_code = s.country
JOIN dim_album e ON e.album_uri = s.album_uri
LEFT JOIN dim_entry_status es ON es.status_name = CASE
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('NEW', 'NEW ENTRY') THEN 'NEW'
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('RE ENTRY', 'REENTRY') THEN 'RE-ENTRY'
  WHEN UPPER(REPLACE(REPLACE(TRIM(s.entry_status), '_', ' '), '-', ' ')) IN ('CONTINUING', 'MOVED UP', 'MOVED DOWN', 'NO CHANGE') THEN 'CONTINUING'
  ELSE NULL END;
SELECT 'ALBUMS' AS dataset, COUNT(*) AS loaded_rows FROM fact_album_performance;

-- KPI configuration preserved from original warehouse loader.
INSERT INTO fact_kpi_thresholds
 (kpi_name, threshold_type, high_value, moderate_upper, moderate_lower,
  low_value, description, last_calculated)
VALUES
 ('Stream Momentum', 'Fixed PCT', 5.0000, 5.0000, -5.0000, -5.0000,
  'Rising >5%; Stable -5% to +5%; Falling <-5%', CURRENT_DATE()),
 ('Top 10 Chart Strength', 'Absolute', 3.0000, 6.0000, 3.0000, 6.0000,
  'Strong <=3; Moderate >3 to <=6; Weak >6 (smaller rank is better)', CURRENT_DATE()),
 ('New Entries vs Historical Baseline', 'Fixed PCT', 120.0000, 120.0000, 80.0000, 80.0000,
  'High >120% baseline; Normal 80%-120%; Low <80%', CURRENT_DATE())
ON DUPLICATE KEY UPDATE
 threshold_type=VALUES(threshold_type), high_value=VALUES(high_value),
 moderate_upper=VALUES(moderate_upper), moderate_lower=VALUES(moderate_lower),
 low_value=VALUES(low_value), description=VALUES(description),
 last_calculated=VALUES(last_calculated);

-- ================================================================
-- SECTION 3: AGGREGATIONS (run ONLY AFTER every fact week is loaded)
-- ================================================================
-- The nine original KPI definitions are preserved to support dashboard pages.
-- Run each START TRANSACTION through COMMIT independently if necessary.
-- These aggregation queries may still take time on large fact tables.
START TRANSACTION;
-- 1. GLOBAL DAILY: only source GLOBAL chart data, avoiding double counting.
 DELETE FROM agg_daily_global_summary;
 INSERT INTO agg_daily_global_summary
   (summary_date, total_streams, avg_peak_rank_top10, new_entry_count, stream_growth_rate_pct)
 WITH daily AS (
   SELECT d.full_date AS summary_date,
          SUM(COALESCE(f.streams,0)) AS total_streams,
          AVG(CASE WHEN f.`rank`<=10 THEN f.peak_rank END) AS avg_peak_rank_top10,
          COUNT(DISTINCT CASE WHEN s.status_name='NEW' THEN f.track_id END) AS new_entry_count
   FROM fact_song_performance f
   JOIN dim_date d ON d.date_id=f.date_id
   JOIN dim_geography g ON g.geo_id=f.geo_id AND g.country_code='GLOBAL'
   LEFT JOIN dim_entry_status s ON s.status_id=f.entry_status_id
   GROUP BY d.full_date
 ), with_prev AS (
   SELECT daily.*,
          LAG(total_streams) OVER(ORDER BY summary_date) AS previous_streams,
          LAG(summary_date) OVER(ORDER BY summary_date) AS previous_date
   FROM daily
 )
 SELECT summary_date,total_streams,ROUND(avg_peak_rank_top10,3),new_entry_count,
        CASE WHEN DATEDIFF(summary_date,previous_date)=1 AND previous_streams>0
          THEN ROUND(100.0*(total_streams-previous_streams)/previous_streams,4)
          ELSE NULL END
 FROM with_prev;
COMMIT;

START TRANSACTION;
-- 2. COUNTRY SHARE: countries compared against source GLOBAL for same date.
 -- NULL share when global source is missing or zero.
 DELETE FROM agg_country_share;
 INSERT INTO agg_country_share
   (summary_date,country_code,country_total_streams,global_total_streams,share_pct,share_change_pct)
 WITH country_daily AS (
   SELECT d.full_date summary_date,g.country_code,
          SUM(COALESCE(f.streams,0)) country_total_streams
   FROM fact_song_performance f
   JOIN dim_date d ON d.date_id=f.date_id
   JOIN dim_geography g ON g.geo_id=f.geo_id
   WHERE g.country_code<>'GLOBAL'
   GROUP BY d.full_date,g.country_code
 ), shares AS (
   SELECT c.*,
          gl.total_streams global_total_streams,
          CASE WHEN gl.total_streams>0
            THEN 100.0*c.country_total_streams/gl.total_streams
            ELSE NULL END share_pct
   FROM country_daily c
   LEFT JOIN agg_daily_global_summary gl ON gl.summary_date=c.summary_date
 ), previous_share AS (
   SELECT shares.*,
          LAG(share_pct) OVER (PARTITION BY country_code ORDER BY summary_date) prev_share,
          LAG(summary_date) OVER (PARTITION BY country_code ORDER BY summary_date) prev_date
   FROM shares
 )
 SELECT summary_date,country_code,country_total_streams,global_total_streams,
        ROUND(share_pct,4),
        CASE WHEN DATEDIFF(summary_date,prev_date)=1 AND prev_share>0
          THEN ROUND(100.0*(share_pct-prev_share)/prev_share,4)
          ELSE NULL END
 FROM previous_share;
COMMIT;

START TRANSACTION;
-- 3. ARTIST MOMENTUM: weekly GLOBAL streams allocated equally across credited artists.
 -- Tracks with no bridge artists cannot contribute to this derived measure.
 DELETE FROM agg_artist_momentum;
 INSERT INTO agg_artist_momentum
   (artist_id,period_start,current_period_streams,prev_period_streams,
    growth_rate_pct,momentum_class)
 WITH credits AS (
   SELECT track_id,COUNT(*) artist_count FROM bridge_track_artist GROUP BY track_id
 ), weekly AS (
   SELECT b.artist_id,
          DATE_SUB(d.full_date,INTERVAL WEEKDAY(d.full_date) DAY) period_start,
          ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.artist_count,0)),0) current_streams
   FROM fact_song_performance f
   JOIN dim_date d ON d.date_id=f.date_id
   JOIN dim_geography g ON g.geo_id=f.geo_id AND g.country_code='GLOBAL'
   JOIN bridge_track_artist b ON b.track_id=f.track_id
   JOIN credits c ON c.track_id=f.track_id
   GROUP BY b.artist_id,DATE_SUB(d.full_date,INTERVAL WEEKDAY(d.full_date) DAY)
 ), w_prev AS (
   SELECT weekly.*,
          LAG(current_streams) OVER (PARTITION BY artist_id ORDER BY period_start) prev_streams,
          LAG(period_start) OVER (PARTITION BY artist_id ORDER BY period_start) prev_week
   FROM weekly
 ), w_calc AS (
   SELECT *,CASE WHEN DATEDIFF(period_start,prev_week)=7 AND prev_streams>0
       THEN 100.0*(current_streams-prev_streams)/prev_streams ELSE NULL END growth_pct
   FROM w_prev
 )
 SELECT artist_id,period_start,current_streams,
        CASE WHEN DATEDIFF(period_start,prev_week)=7 THEN prev_streams ELSE NULL END,
        ROUND(growth_pct,4),
        CASE WHEN growth_pct>5 THEN 'Rising'
             WHEN growth_pct< -5 THEN 'Falling'
             WHEN growth_pct IS NOT NULL THEN 'Stable' ELSE NULL END
 FROM w_calc;
COMMIT;

START TRANSACTION;
-- 4. LABEL MARKET SHARE: percent of the country's ranked-track streams.
 -- Tracks with unknown labels remain in the country denominator.
 DELETE FROM agg_label_market_share;
 INSERT INTO agg_label_market_share
   (summary_date,country_code,label_name,label_streams,country_total_streams,market_share_pct)
 WITH totals AS (
   SELECT d.full_date summary_date,g.country_code,
          SUM(COALESCE(f.streams,0)) country_total_streams
   FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
   JOIN dim_geography g ON g.geo_id=f.geo_id
   WHERE g.country_code<>'GLOBAL'
   GROUP BY d.full_date,g.country_code
 ), labels AS (
   SELECT d.full_date summary_date,g.country_code,l.label_name,
          SUM(COALESCE(f.streams,0)) label_streams
   FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
   JOIN dim_geography g ON g.geo_id=f.geo_id
   JOIN dim_track t ON t.track_id=f.track_id
   JOIN dim_label l ON l.label_id=t.label_id
   WHERE g.country_code<>'GLOBAL'
   GROUP BY d.full_date,g.country_code,l.label_name
 )
 SELECT l.summary_date,l.country_code,l.label_name,l.label_streams,t.country_total_streams,
        CASE WHEN t.country_total_streams>0
         THEN ROUND(100.0*l.label_streams/t.country_total_streams,4) ELSE NULL END
 FROM labels l JOIN totals t
 ON t.summary_date=l.summary_date AND t.country_code=l.country_code;
COMMIT;

START TRANSACTION;
-- 5. TRACK VELOCITY: aggregate across observed markets (not market-specific).
 -- MIN(peak_rank) is best historical chart position (lower = better).
 DELETE FROM agg_track_velocity;
 INSERT INTO agg_track_velocity
   (track_id,entry_rank,peak_rank,climbing_speed_delta,velocity_class)
 WITH ranked AS (
   SELECT f.track_id, f.entry_rank, f.peak_rank,
          ROW_NUMBER() OVER (
            PARTITION BY f.track_id ORDER BY d.full_date, f.`rank`, f.id
          ) AS first_observation
   FROM fact_song_performance f
   JOIN dim_date d ON d.date_id=f.date_id
 ), track_base AS (
   SELECT track_id,
          MAX(CASE WHEN first_observation=1 THEN entry_rank END) entry_rank,
          MIN(peak_rank) peak_rank
   FROM ranked GROUP BY track_id
 ), delta_calc AS (
   SELECT track_id,entry_rank,peak_rank,
          (entry_rank-peak_rank) delta FROM track_base
 ), scored AS (
   SELECT *, PERCENT_RANK() OVER (ORDER BY delta) pct
   FROM delta_calc
 )
 SELECT track_id,entry_rank,peak_rank,delta,
        CASE WHEN delta IS NULL THEN NULL
             WHEN pct>=0.75 THEN 'Fast'
             WHEN pct>=0.25 THEN 'Moderate' ELSE 'Slow' END
 FROM scored;
COMMIT;

START TRANSACTION;
-- 6. LONGEVITY: source days_on_chart is a cumulative metric.
 DELETE FROM agg_longevity_benchmarks;
 INSERT INTO agg_longevity_benchmarks
   (track_id,days_on_chart,max_consecutive_streak,longevity_percentile,longevity_class)
 WITH longevity AS (
   SELECT track_id,MAX(days_on_chart) days_on_chart,
          MAX(consecutive_days) max_streak
   FROM fact_song_performance GROUP BY track_id
 ), scored AS (
   SELECT *,PERCENT_RANK() OVER (ORDER BY days_on_chart) pct FROM longevity
 )
 SELECT track_id,days_on_chart,max_streak,
        CASE WHEN days_on_chart IS NOT NULL THEN ROUND(pct,4) ELSE NULL END,
        CASE WHEN days_on_chart IS NULL THEN NULL
             WHEN pct>=0.75 THEN 'High'
             WHEN pct>=0.25 THEN 'Moderate' ELSE 'Low' END
 FROM scored;
COMMIT;

START TRANSACTION;
-- 7. NEW-ENTRY BASELINE: average daily new entries over preceding 30 observed
 -- days; missing early comparison history produces NULL, not a false baseline.
 DELETE FROM agg_new_entry_baseline;
 INSERT INTO agg_new_entry_baseline
   (baseline_date,period_avg_new_entries,historical_baseline,baseline_ratio_pct,entry_class)
 WITH counts AS (
   SELECT summary_date,new_entry_count,
          AVG(new_entry_count) OVER
          (ORDER BY summary_date ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) baseline,
          COUNT(*) OVER
          (ORDER BY summary_date ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) baseline_days
   FROM agg_daily_global_summary
 ), calc AS (
   SELECT *,CASE WHEN baseline_days=30 AND baseline>0
     THEN 100.0*new_entry_count/baseline ELSE NULL END ratio_pct
   FROM counts
 )
 SELECT summary_date,CAST(new_entry_count AS DECIMAL(12,4)),
        CASE WHEN baseline_days=30 THEN ROUND(baseline,4) ELSE NULL END,
        ROUND(ratio_pct,4),
        CASE WHEN ratio_pct>120 THEN 'High'
             WHEN ratio_pct<80 THEN 'Low'
             WHEN ratio_pct IS NOT NULL THEN 'Normal' ELSE NULL END
 FROM calc;
COMMIT;

START TRANSACTION;
-- 8. REGIONAL DIVERSITY: distinct artists in each country's top-50 DAILY
 -- ARTIST chart. Percentile measured within each country's observations.
 DELETE FROM agg_regional_diversity;
 INSERT INTO agg_regional_diversity
   (summary_date,country_code,unique_artist_count_top50,diversity_percentile,diversity_class)
 WITH daily AS (
   SELECT d.full_date summary_date,g.country_code,
          COUNT(DISTINCT f.artist_id) artist_count
   FROM fact_artists_performance f JOIN dim_date d ON d.date_id=f.date_id
   JOIN dim_geography g ON g.geo_id=f.geo_id
   WHERE g.country_code<>'GLOBAL' AND f.`rank`<=50
   GROUP BY d.full_date,g.country_code
 ), scored AS (
   SELECT *,PERCENT_RANK() OVER (PARTITION BY country_code ORDER BY artist_count) pct
   FROM daily
 )
 SELECT summary_date,country_code,artist_count,ROUND(pct,4),
        CASE WHEN pct>=0.75 THEN 'High'
             WHEN pct>=0.25 THEN 'Moderate' ELSE 'Low' END
 FROM scored;
COMMIT;

START TRANSACTION;
-- 9. ARTIST REACH: weekly number of DISTINCT country charts where artist's
 -- credited tracks appear. High-reach/low-stream uses weekly cohort percentiles.
 DELETE FROM agg_artist_reach;
 INSERT INTO agg_artist_reach
   (artist_id,period_start,distinct_country_count,reach_percentile,
    reach_class,high_reach_low_stream_flag)
 WITH credits AS (
   SELECT track_id,COUNT(*) artist_count FROM bridge_track_artist GROUP BY track_id
 ), weekly AS (
   SELECT b.artist_id,
          DATE_SUB(d.full_date,INTERVAL WEEKDAY(d.full_date) DAY) period_start,
          COUNT(DISTINCT g.country_code) country_count,
          SUM(COALESCE(f.streams,0)/NULLIF(c.artist_count,0)) allocated_streams
   FROM fact_song_performance f
   JOIN dim_date d ON d.date_id=f.date_id
   JOIN dim_geography g ON g.geo_id=f.geo_id AND g.country_code<>'GLOBAL'
   JOIN bridge_track_artist b ON b.track_id=f.track_id
   JOIN credits c ON c.track_id=f.track_id
   GROUP BY b.artist_id,DATE_SUB(d.full_date,INTERVAL WEEKDAY(d.full_date) DAY)
 ), scored AS (
   SELECT *,PERCENT_RANK() OVER (PARTITION BY period_start ORDER BY country_count) reach_pct,
          PERCENT_RANK() OVER (PARTITION BY period_start ORDER BY allocated_streams) streams_pct
   FROM weekly
 )
 SELECT artist_id,period_start,country_count,ROUND(reach_pct,4),
        CASE WHEN reach_pct>=0.75 THEN 'High'
             WHEN reach_pct>=0.25 THEN 'Moderate' ELSE 'Low' END,
        (reach_pct>=0.75 AND streams_pct<0.25)
 FROM scored;
COMMIT;

-- ================================================================
-- SECTION 4: QUICK ROW-COUNT VALIDATION
-- ================================================================
SELECT 'dim_artists' dataset, COUNT(*) records FROM dim_artists
UNION ALL SELECT 'dim_track', COUNT(*) FROM dim_track
UNION ALL SELECT 'dim_album', COUNT(*) FROM dim_album
UNION ALL SELECT 'bridge_track_artist', COUNT(*) FROM bridge_track_artist
UNION ALL SELECT 'fact_song_performance', COUNT(*) FROM fact_song_performance
UNION ALL SELECT 'fact_artists_performance', COUNT(*) FROM fact_artists_performance
UNION ALL SELECT 'fact_album_performance', COUNT(*) FROM fact_album_performance
UNION ALL SELECT 'agg_daily_global_summary', COUNT(*) FROM agg_daily_global_summary
UNION ALL SELECT 'agg_country_share', COUNT(*) FROM agg_country_share
UNION ALL SELECT 'agg_artist_momentum', COUNT(*) FROM agg_artist_momentum
UNION ALL SELECT 'agg_label_market_share', COUNT(*) FROM agg_label_market_share
UNION ALL SELECT 'agg_track_velocity', COUNT(*) FROM agg_track_velocity
UNION ALL SELECT 'agg_longevity_benchmarks', COUNT(*) FROM agg_longevity_benchmarks
UNION ALL SELECT 'agg_new_entry_baseline', COUNT(*) FROM agg_new_entry_baseline
UNION ALL SELECT 'agg_regional_diversity', COUNT(*) FROM agg_regional_diversity
UNION ALL SELECT 'agg_artist_reach', COUNT(*) FROM agg_artist_reach;
-- Restore Workbench safe updates before leaving the session.
SET SESSION SQL_SAFE_UPDATES = @original_safe_updates;
