-- Optional warehouse extension required for the manuscript's artist-album chart.
-- Does not drop or truncate any existing DW table.
-- Run ONCE after confirming the cleaned staging album artist_uris use | delimiters.
USE spotify_analytics_dw;

CREATE TABLE IF NOT EXISTS bridge_album_artist (
  album_id INT NOT NULL,
  artist_id INT NOT NULL,
  PRIMARY KEY (album_id, artist_id),
  CONSTRAINT fk_album_artist_album FOREIGN KEY(album_id) REFERENCES dim_album(album_id),
  CONSTRAINT fk_album_artist_artist FOREIGN KEY(artist_id) REFERENCES dim_artists(artist_id)
) ENGINE=InnoDB;

-- JSON_QUOTE handles escaping in supplied raw URI strings safely.
-- Matched identifiers only; unrecognized artist URI is NOT assigned a guessed artist.
INSERT IGNORE INTO bridge_album_artist (album_id, artist_id)
SELECT DISTINCT da.album_id, a.artist_id
FROM (
   SELECT DISTINCT album_uri, artist_uris
   FROM spotify_analytics_stg.clean_albums_weekly_52W
   WHERE artist_uris IS NOT NULL AND TRIM(artist_uris) <> ''
) s
JOIN dim_album da ON da.album_uri=s.album_uri
JOIN JSON_TABLE(
   CONCAT('[', REPLACE(JSON_QUOTE(s.artist_uris), '|', '\",\"'), ']'),
   '$[*]' COLUMNS(artist_uri VARCHAR(100) PATH '$')
) split_uris ON TRUE
JOIN dim_artists a ON a.artist_uri=TRIM(split_uris.artist_uri);

SELECT COUNT(*) AS album_artist_links FROM bridge_album_artist;
