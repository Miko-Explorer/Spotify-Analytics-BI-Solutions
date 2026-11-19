-- One-time EMPTY schema baseline. Execute only through bootstrap_warehouse.py.
-- No schema selection, data import, database creation, or destructive SQL.
-- DIMENSION TABLES
CREATE TABLE dim_chart_type (
    chart_type_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    type_name ENUM('Daily Song', 'Weekly Album', 'Artist Rank') NOT NULL UNIQUE
) ENGINE=InnoDB;

-- Map raw statuses in ETL: NEW ENTRY -> NEW, RE ENTRY -> RE-ENTRY,
-- MOVED UP / MOVED DOWN / NO CHANGE -> CONTINUING.
CREATE TABLE dim_entry_status (
    status_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    status_name ENUM('NEW', 'RE-ENTRY', 'CONTINUING') NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE dim_label (
    label_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    label_name VARCHAR(255) NOT NULL UNIQUE,
    parent_company VARCHAR(255) NULL
) ENGINE=InnoDB;

CREATE TABLE dim_album (
    album_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    album_uri VARCHAR(100) NOT NULL UNIQUE,
    album_name VARCHAR(255) NULL,
    release_year SMALLINT NULL,
    label_id INT NULL,
    CONSTRAINT fk_album_label FOREIGN KEY (label_id) REFERENCES dim_label(label_id)
) ENGINE=InnoDB;

CREATE TABLE dim_track (
    track_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    track_uri VARCHAR(100) NOT NULL UNIQUE,
    track_name VARCHAR(255) NULL,
    release_date DATE NULL,
    label_id INT NULL,
    CONSTRAINT fk_track_label FOREIGN KEY (label_id) REFERENCES dim_label(label_id)
) ENGINE=InnoDB;

-- Keep dim_artists as in your original DDL; includes current artist-master measures.
CREATE TABLE dim_artists (
    artist_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    artist_uri VARCHAR(100) NOT NULL UNIQUE,
    artist_name VARCHAR(255) NULL,
    monthly_listeners BIGINT NULL,
    monthly_listeners_rank INT NULL,
    monthly_listeners_peak BIGINT NULL,
    peak_listener_rank INT NULL
) ENGINE=InnoDB;

CREATE TABLE bridge_track_artist (
    track_id INT NOT NULL,
    artist_id INT NOT NULL,
    `role` ENUM('Primary', 'Featured') NULL,
    PRIMARY KEY (track_id, artist_id),
    CONSTRAINT fk_bridge_track FOREIGN KEY (track_id) REFERENCES dim_track(track_id),
    CONSTRAINT fk_bridge_artist FOREIGN KEY (artist_id) REFERENCES dim_artists(artist_id)
) ENGINE=InnoDB;

-- Country must also support the special GLOBAL chart market.
-- Region and tier are reference-data enrichments, not supplied in the Kaggle CSVs.
CREATE TABLE dim_geography (
    geo_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    country_code VARCHAR(6) NOT NULL UNIQUE,
    country_name VARCHAR(100) NOT NULL,
    region VARCHAR(50) NULL,
    market_tier ENUM(
        'Tier 1 - Mega', 'Tier 2 - Major',
        'Tier 3 - Emerging', 'Tier 4 - Developing'
    ) NULL
) ENGINE=InnoDB;

-- Derived holiday flags need an external holiday calendar; default false = not assigned.
CREATE TABLE dim_date (
    date_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    `year` SMALLINT NOT NULL,
    `month` TINYINT NOT NULL,
    day_of_week TINYINT NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    `quarter` TINYINT NOT NULL,
    is_holiday BOOLEAN NULL DEFAULT NULL,
    CONSTRAINT chk_date_month CHECK (`month` BETWEEN 1 AND 12),
    CONSTRAINT chk_date_weekday CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT chk_date_quarter CHECK (`quarter` BETWEEN 1 AND 4)
) ENGINE=InnoDB;

-- FACT TABLES
CREATE TABLE fact_album_performance (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    date_id INT NOT NULL,
    geo_id INT NOT NULL,
    album_id INT NOT NULL,
    `rank` INT NOT NULL,
    peak_rank INT NULL,
    previous_rank INT NULL,
    weeks_on_chart INT NULL,
    consecutive_weeks INT NULL,
    entry_rank INT NULL,
    entry_status_id INT NULL,
    CONSTRAINT fk_fact_album_date FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    CONSTRAINT fk_fact_album_geo FOREIGN KEY (geo_id) REFERENCES dim_geography(geo_id),
    CONSTRAINT fk_fact_album_album FOREIGN KEY (album_id) REFERENCES dim_album(album_id),
    CONSTRAINT fk_fact_album_status FOREIGN KEY (entry_status_id) REFERENCES dim_entry_status(status_id),
    INDEX idx_fact_album_date_geo (date_id, geo_id),
    INDEX idx_fact_album_entity (album_id, date_id),
    CONSTRAINT chk_fact_album_rank CHECK (`rank` BETWEEN 1 AND 200)
) ENGINE=InnoDB;

CREATE TABLE fact_artists_performance (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    date_id INT NOT NULL,
    geo_id INT NOT NULL,
    artist_id INT NOT NULL,
    `rank` INT NOT NULL,
    peak_rank INT NULL,
    previous_rank INT NULL,
    days_on_chart INT NULL,
    consecutive_days INT NULL,
    entry_rank INT NULL,
    entry_status_id INT NULL,
    CONSTRAINT fk_fact_artist_date FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    CONSTRAINT fk_fact_artist_geo FOREIGN KEY (geo_id) REFERENCES dim_geography(geo_id),
    CONSTRAINT fk_fact_artist_artist FOREIGN KEY (artist_id) REFERENCES dim_artists(artist_id),
    CONSTRAINT fk_fact_artist_status FOREIGN KEY (entry_status_id) REFERENCES dim_entry_status(status_id),
    INDEX idx_fact_artist_date_geo (date_id, geo_id),
    INDEX idx_fact_artist_entity (artist_id, date_id),
    CONSTRAINT chk_fact_artist_rank CHECK (`rank` BETWEEN 1 AND 200)
) ENGINE=InnoDB;

-- KPI thresholds are reference/configuration data, despite the original table name.
CREATE TABLE fact_kpi_thresholds (
    kpi_name VARCHAR(100) NOT NULL PRIMARY KEY,
    threshold_type ENUM('Percentile', 'Fixed PCT', 'Absolute') NULL,
    high_value DECIMAL(18,4) NULL,
    moderate_upper DECIMAL(18,4) NULL,
    moderate_lower DECIMAL(18,4) NULL,
    low_value DECIMAL(18,4) NULL,
    description VARCHAR(500) NULL,
    last_calculated DATE NULL
) ENGINE=InnoDB;

CREATE TABLE fact_song_performance (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    date_id INT NOT NULL,
    geo_id INT NOT NULL,
    track_id INT NOT NULL,
    `rank` INT NOT NULL,
    streams BIGINT NULL,
    peak_rank INT NULL,
    previous_rank INT NULL,
    days_on_chart INT NULL,
    consecutive_days INT NULL,
    entry_rank INT NULL,
    entry_status_id INT NULL,
    CONSTRAINT fk_fact_song_date FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    CONSTRAINT fk_fact_song_geo FOREIGN KEY (geo_id) REFERENCES dim_geography(geo_id),
    CONSTRAINT fk_fact_song_track FOREIGN KEY (track_id) REFERENCES dim_track(track_id),
    CONSTRAINT fk_fact_song_status FOREIGN KEY (entry_status_id) REFERENCES dim_entry_status(status_id),
    INDEX idx_fact_song_date_geo (date_id, geo_id),
    INDEX idx_fact_song_entity (track_id, date_id),
    CONSTRAINT chk_fact_song_rank CHECK (`rank` BETWEEN 1 AND 200),
    CONSTRAINT chk_fact_song_streams CHECK (streams IS NULL OR streams >= 0)
) ENGINE=InnoDB;

-- AGGREGATE TABLES: these are refreshed by ETL, never inserted directly from raw CSVs.
CREATE TABLE agg_daily_global_summary (
    summary_date DATE NOT NULL PRIMARY KEY,
    total_streams BIGINT NOT NULL,
    avg_peak_rank_top10 DECIMAL(8,3) NULL,
    new_entry_count INT NOT NULL,
    stream_growth_rate_pct DECIMAL(12,4) NULL
) ENGINE=InnoDB;

CREATE TABLE agg_country_share (
    summary_date DATE NOT NULL,
    country_code VARCHAR(6) NOT NULL,
    country_total_streams BIGINT NOT NULL,
    global_total_streams BIGINT NULL,
    share_pct DECIMAL(12,4) NULL,
    share_change_pct DECIMAL(12,4) NULL,
    PRIMARY KEY (summary_date, country_code)
) ENGINE=InnoDB;

CREATE TABLE agg_artist_momentum (
    artist_id INT NOT NULL,
    period_start DATE NOT NULL,
    current_period_streams BIGINT NULL,
    prev_period_streams BIGINT NULL,
    growth_rate_pct DECIMAL(12,4) NULL,
    momentum_class ENUM('Rising', 'Stable', 'Falling') NULL,
    PRIMARY KEY (artist_id, period_start),
    CONSTRAINT fk_momentum_artist FOREIGN KEY (artist_id) REFERENCES dim_artists(artist_id)
) ENGINE=InnoDB;

CREATE TABLE agg_label_market_share (
    summary_date DATE NOT NULL,
    country_code VARCHAR(6) NOT NULL,
    label_name VARCHAR(255) NOT NULL,
    label_streams BIGINT NOT NULL,
    country_total_streams BIGINT NOT NULL,
    market_share_pct DECIMAL(12,4) NULL,
    PRIMARY KEY (summary_date, country_code, label_name)
) ENGINE=InnoDB;

-- Recompute at the full historical observation window; one record per track.
CREATE TABLE agg_track_velocity (
    track_id INT NOT NULL PRIMARY KEY,
    entry_rank INT NULL,
    peak_rank INT NULL,
    climbing_speed_delta INT NULL,
    velocity_class ENUM('Fast', 'Moderate', 'Slow') NULL,
    CONSTRAINT fk_velocity_track FOREIGN KEY (track_id) REFERENCES dim_track(track_id)
) ENGINE=InnoDB;

CREATE TABLE agg_longevity_benchmarks (
    track_id INT NOT NULL PRIMARY KEY,
    days_on_chart INT NULL,
    max_consecutive_streak INT NULL,
    longevity_percentile DECIMAL(7,4) NULL,
    longevity_class ENUM('High', 'Moderate', 'Low') NULL,
    CONSTRAINT fk_longevity_track FOREIGN KEY (track_id) REFERENCES dim_track(track_id)
) ENGINE=InnoDB;

CREATE TABLE agg_new_entry_baseline (
    baseline_date DATE NOT NULL PRIMARY KEY,
    period_avg_new_entries DECIMAL(12,4) NULL,
    historical_baseline DECIMAL(12,4) NULL,
    baseline_ratio_pct DECIMAL(12,4) NULL,
    entry_class ENUM('High', 'Normal', 'Low') NULL
) ENGINE=InnoDB;

CREATE TABLE agg_regional_diversity (
    summary_date DATE NOT NULL,
    country_code VARCHAR(6) NOT NULL,
    unique_artist_count_top50 INT NOT NULL,
    diversity_percentile DECIMAL(7,4) NULL,
    diversity_class ENUM('High', 'Moderate', 'Low') NULL,
    PRIMARY KEY (summary_date, country_code)
) ENGINE=InnoDB;

CREATE TABLE agg_artist_reach (
    artist_id INT NOT NULL,
    period_start DATE NOT NULL,
    distinct_country_count INT NOT NULL,
    reach_percentile DECIMAL(7,4) NULL,
    reach_class ENUM('High', 'Moderate', 'Low') NULL,
    high_reach_low_stream_flag BOOLEAN NULL DEFAULT NULL,
    PRIMARY KEY (artist_id, period_start),
    CONSTRAINT fk_reach_artist FOREIGN KEY (artist_id) REFERENCES dim_artists(artist_id)
) ENGINE=InnoDB;

CREATE TABLE bridge_album_artist (
  album_id INT NOT NULL,
  artist_id INT NOT NULL,
  PRIMARY KEY (album_id, artist_id),
  CONSTRAINT fk_album_artist_album FOREIGN KEY(album_id) REFERENCES dim_album(album_id),
  CONSTRAINT fk_album_artist_artist FOREIGN KEY(artist_id) REFERENCES dim_artists(artist_id)
) ENGINE=InnoDB;
