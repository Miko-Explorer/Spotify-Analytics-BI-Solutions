-- Optional performance indexes. Review table indexes before applying.
-- They can take time to create on multi-million-row fact tables.
USE spotify_analytics_dw;
CREATE INDEX idx_song_geo_date_track ON fact_song_performance (geo_id, date_id, track_id);
CREATE INDEX idx_artist_geo_date_id ON fact_artists_performance (geo_id, date_id, artist_id);
CREATE INDEX idx_album_geo_date_id ON fact_album_performance (geo_id, date_id, album_id);
