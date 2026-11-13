-- Spotify Analytics | Staging DDL | MySQL 8.0.16+
-- WARNING: Running this script DELETES the existing staging database and its data.
-- Staging follows the four cleaned DataFrame column names and preserves source detail.
DROP DATABASE IF EXISTS spotify_analytics_stg;
CREATE DATABASE spotify_analytics_stg CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE spotify_analytics_stg;

-- ARTIST MASTER: many artists have no published listener/rank metrics.
CREATE TABLE clean_artists (
    artist_uri VARCHAR(100) NOT NULL,
    artist_name VARCHAR(255) NULL,
    monthly_listeners BIGINT NULL,
    monthly_listeners_rank INT NULL,
    monthly_listeners_peak_rank INT NULL,
    monthly_listeners_peak_listeners BIGINT NULL,
    PRIMARY KEY (artist_uri),
    CONSTRAINT chk_artist_monthly_listeners CHECK (monthly_listeners IS NULL OR monthly_listeners >= 0),
    CONSTRAINT chk_artist_monthly_rank CHECK (monthly_listeners_rank IS NULL OR monthly_listeners_rank > 0),
    CONSTRAINT chk_artist_peak_rank CHECK (monthly_listeners_peak_rank IS NULL OR monthly_listeners_peak_rank > 0),
    CONSTRAINT chk_artist_peak_listeners CHECK (monthly_listeners_peak_listeners IS NULL OR monthly_listeners_peak_listeners >= 0)
) ENGINE=InnoDB;

-- WEEKLY ALBUM CHART: a single album URI appears in many weeks and countries.
-- Keep unparsed multi-artist identifiers; later DW loading resolves relationships.
CREATE TABLE clean_albums_weekly_52W (
    week_start_date DATE NOT NULL,
    country VARCHAR(6) NOT NULL,
    `rank` INT NOT NULL,
    album_uri VARCHAR(100) NOT NULL,
    album_name VARCHAR(255) NULL,
    artist_names TEXT NULL,
    label VARCHAR(255) NULL,
    peak_rank INT NULL,
    previous_rank INT NULL,
    weeks_on_chart INT NULL,
    consecutive_weeks INT NULL,
    entry_status VARCHAR(30) NULL,
    peak_date DATE NULL,
    entry_rank INT NULL,
    entry_date DATE NULL,
    release_date DATE NULL,
    artist_uris TEXT NULL,
    INDEX idx_album_chart_date_country (week_start_date, country),
    INDEX idx_album_chart_uri (album_uri),
    CONSTRAINT chk_album_rank CHECK (`rank` BETWEEN 1 AND 200),
    CONSTRAINT chk_album_peak_rank CHECK (peak_rank IS NULL OR peak_rank BETWEEN 1 AND 200),
    CONSTRAINT chk_album_previous_rank CHECK (previous_rank IS NULL OR previous_rank >= 0),
    CONSTRAINT chk_album_entry_rank CHECK (entry_rank IS NULL OR entry_rank BETWEEN 1 AND 200),
    CONSTRAINT chk_album_weeks CHECK (weeks_on_chart IS NULL OR weeks_on_chart >= 0),
    CONSTRAINT chk_album_streak CHECK (
        consecutive_weeks IS NULL OR
        (consecutive_weeks >= 0 AND (weeks_on_chart IS NULL OR consecutive_weeks <= weeks_on_chart))
    )
) ENGINE=InnoDB;

-- DAILY ARTIST CHART: daily streaks and historical rank/date fields retained.
CREATE TABLE clean_artists_daily_365D (
    `date` DATE NOT NULL,
    country VARCHAR(6) NOT NULL,
    `rank` INT NOT NULL,
    artist_uri VARCHAR(100) NOT NULL,
    artist_name VARCHAR(255) NULL,
    peak_rank INT NULL,
    previous_rank INT NULL,
    days_on_chart INT NULL,
    consecutive_days INT NULL,
    entry_status VARCHAR(30) NULL,
    peak_date DATE NULL,
    entry_rank INT NULL,
    entry_date DATE NULL,
    INDEX idx_artist_chart_date_country (`date`, country),
    INDEX idx_artist_chart_uri (artist_uri),
    CONSTRAINT chk_daily_artist_rank CHECK (`rank` BETWEEN 1 AND 200),
    CONSTRAINT chk_daily_artist_peak CHECK (peak_rank IS NULL OR peak_rank BETWEEN 1 AND 200),
    CONSTRAINT chk_daily_artist_previous CHECK (previous_rank IS NULL OR previous_rank >= 0),
    CONSTRAINT chk_daily_artist_entry CHECK (entry_rank IS NULL OR entry_rank BETWEEN 1 AND 200),
    CONSTRAINT chk_daily_artist_days CHECK (days_on_chart IS NULL OR days_on_chart >= 0),
    CONSTRAINT chk_daily_artist_streak CHECK (
        consecutive_days IS NULL OR
        (consecutive_days >= 0 AND (days_on_chart IS NULL OR consecutive_days <= days_on_chart))
    )
) ENGINE=InnoDB;

-- DAILY SONG CHART: retain the event grain (date/country/track), not a UNIQUE track URI.
CREATE TABLE clean_songs_daily_365D (
    `date` DATE NOT NULL,
    country VARCHAR(6) NOT NULL,
    `rank` INT NOT NULL,
    track_uri VARCHAR(100) NOT NULL,
    artist_names TEXT NULL,
    track_name VARCHAR(255) NULL,
    label VARCHAR(255) NULL,
    peak_rank INT NULL,
    previous_rank INT NULL,
    days_on_chart INT NULL,
    streams BIGINT NULL,
    consecutive_days INT NULL,
    entry_status VARCHAR(30) NULL,
    peak_date DATE NULL,
    entry_rank INT NULL,
    entry_date DATE NULL,
    release_date DATE NULL,
    artist_uris TEXT NULL,
    INDEX idx_song_chart_date_country (`date`, country),
    INDEX idx_song_chart_uri (track_uri),
    CONSTRAINT chk_song_rank CHECK (`rank` BETWEEN 1 AND 200),
    CONSTRAINT chk_song_peak CHECK (peak_rank IS NULL OR peak_rank BETWEEN 1 AND 200),
    CONSTRAINT chk_song_previous CHECK (previous_rank IS NULL OR previous_rank >= 0),
    CONSTRAINT chk_song_entry CHECK (entry_rank IS NULL OR entry_rank BETWEEN 1 AND 200),
    CONSTRAINT chk_song_days CHECK (days_on_chart IS NULL OR days_on_chart >= 0),
    CONSTRAINT chk_song_streams CHECK (streams IS NULL OR streams >= 0),
    CONSTRAINT chk_song_streak CHECK (
        consecutive_days IS NULL OR
        (consecutive_days >= 0 AND (days_on_chart IS NULL OR consecutive_days <= days_on_chart))
    )
) ENGINE=InnoDB;
