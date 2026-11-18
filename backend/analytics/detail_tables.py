"""Read-only, bounded detail tables. All user values passed as SQL parameters.

Each page returns at most 50 rows per request. CSV export uses the current
visible page, not an unbounded warehouse export.
"""
from .queries import rows, dates, one

SCHEMAS = {
    'global': [('track', 'Track'), ('artists', 'Credited artists'), ('streams', 'Streams'),
               ('best_rank', 'Best rank'), ('peak_rank', 'Peak rank'), ('days_on_chart', 'Chart days')],
    'regional': [('label', 'Record label'), ('streams', 'Country streams'),
                 ('country_streams', 'All country streams'), ('share_pct', 'Share (%)')],
    'velocity': [('track', 'Track'), ('label', 'Record label'), ('entry_rank', 'Entry rank'),
                 ('peak_rank', 'Peak rank'), ('improvement', 'Improvement'),
                 ('days_on_chart', 'Chart days'), ('streak', 'Consecutive days')],
    'weekly': [('album','Album'),('best_rank','Best rank'),('weeks','Weeks on chart'),('observed_weeks','Observed chart weeks')],
    'artist': [('track', 'Track'), ('streams', 'Credited streams'), ('best_rank', 'Best rank'),
               ('peak_rank', 'Peak rank'), ('days_on_chart', 'Chart days'), ('markets', 'Markets')],
}


def detail_table(page, country='GLOBAL', start=None, end=None, artist_id=None,
                 scope='daily', search='', sort='', direction='desc', page_number=1, page_size=20):
    if page not in SCHEMAS:
        raise ValueError('Invalid dashboard')
    if not isinstance(page_number, int) or not 1 <= page_number <= 200:
        raise ValueError('Page must be between 1 and 200')
    if not isinstance(page_size, int) or not 1 <= page_size <= 50:
        raise ValueError('Page size must be between 1 and 50')
    search = (search or '').strip()[:100]
    direction = 'ASC' if direction == 'asc' else 'DESC'
    columns = SCHEMAS[page]
    allowed = {key for key, _ in columns}
    sort = sort if sort in allowed else {'global': 'streams','regional': 'streams',
                                        'velocity': 'improvement','artist': 'streams','weekly': 'best_rank'}[page]
    offset = (page_number-1)*page_size
    pattern = '%' + search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
    dw, date_args = dates('d.full_date',start,end)
    credit_filter = (' AND EXISTS (SELECT 1 FROM bridge_track_artist bc'
                     ' WHERE bc.track_id=f.track_id AND bc.artist_id=%s)') if artist_id else ''
    artist_args = [artist_id] if artist_id else []
    caveat = None

    if page == 'weekly':
        from .queries import album_bridge_present
        if artist_id is not None and not album_bridge_present():
            return {'columns': columns, 'rows': [], 'page': page_number, 'has_next': False,
                    'note': 'Album-to-artist bridge is required for this filter.'}
        linked=(' AND EXISTS (SELECT 1 FROM bridge_album_artist ab WHERE ab.album_id=f.album_id '
                'AND ab.artist_id=%s)') if artist_id is not None else ''
        sql=f'''SELECT COALESCE(al.album_name,'Unknown album') album,
            MIN(f.`rank`) best_rank,MAX(f.weeks_on_chart) weeks,
            COUNT(DISTINCT d.full_date) observed_weeks
            FROM fact_album_performance f
            JOIN dim_album al ON al.album_id=f.album_id
            JOIN dim_date d ON d.date_id=f.date_id
            JOIN dim_geography g ON g.geo_id=f.geo_id
            WHERE g.country_code=%s AND {dw}{linked}
              AND COALESCE(al.album_name,'') LIKE %s
            GROUP BY f.album_id,al.album_name'''
        args=[country,*date_args,*artist_args,pattern]
        caveat='Weekly chart data does not contain album stream counts.'
    elif page == 'global':

        if scope == 'weekly':
            if artist_id:
                bridge=one("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='bridge_album_artist'")
                if not bridge.get('n'):
                    return {'columns': columns, 'rows': [], 'page': page_number, 'has_next': False,
                            'note': 'Album-to-artist bridge not loaded.'}
            linked = (' AND EXISTS (SELECT 1 FROM bridge_album_artist ab'
                      ' WHERE ab.album_id=f.album_id AND ab.artist_id=%s)') if artist_id else ''
            sql = f'''SELECT COALESCE(al.album_name,'Unknown album') track,
                  'Album credits' artists, NULL streams,MIN(f.`rank`) best_rank,
                  MIN(f.peak_rank) peak_rank,MAX(f.weeks_on_chart) days_on_chart
                  FROM fact_album_performance f
                  JOIN dim_album al ON al.album_id=f.album_id
                  JOIN dim_date d ON d.date_id=f.date_id
                  JOIN dim_geography g ON g.geo_id=f.geo_id
                  WHERE g.country_code=%s AND {dw}{linked}
                  AND COALESCE(al.album_name,'') LIKE %s
                  GROUP BY f.album_id,al.album_name'''
            args=[country,*date_args,*artist_args,pattern]
            caveat='Weekly albums have no stream measurements. Chart days column contains weeks.'
            if sort == 'streams': sort='best_rank'
        else:
            selected='GLOBAL' if scope=='yearly' else country
            sql=f'''SELECT COALESCE(t.track_name,'Unknown track') track,
                COALESCE(MAX(credit.names),'Unknown artist') artists,
                SUM(COALESCE(f.streams,0)) streams, MIN(f.`rank`) best_rank,
                MIN(f.peak_rank) peak_rank, MAX(f.days_on_chart) days_on_chart
                FROM fact_song_performance f
                JOIN dim_track t ON t.track_id=f.track_id
                JOIN dim_date d ON d.date_id=f.date_id
                JOIN dim_geography g ON g.geo_id=f.geo_id
                LEFT JOIN (SELECT b.track_id, GROUP_CONCAT(DISTINCT a.artist_name
                   ORDER BY a.artist_name SEPARATOR ', ') names FROM bridge_track_artist b
                   JOIN dim_artists a ON a.artist_id=b.artist_id GROUP BY b.track_id) credit
                   ON credit.track_id=f.track_id
                WHERE g.country_code=%s AND {dw}{credit_filter}
                AND COALESCE(t.track_name,'') LIKE %s
                GROUP BY f.track_id,t.track_name'''
            args=[selected,*date_args,*artist_args,pattern]

    elif page == 'regional':
        if country == 'GLOBAL': raise ValueError('Select a country for Regional Rhythms')
        aw,ap=dates('summary_date',start,end)
        if artist_id:
            sql=f'''SELECT COALESCE(l.label_name,'Unknown label') label,
                    ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.artist_count,0)),0) streams,
                    NULL country_streams,NULL share_pct
                    FROM fact_song_performance f
                    JOIN dim_track t ON t.track_id=f.track_id
                    LEFT JOIN dim_label l ON l.label_id=t.label_id
                    JOIN dim_date d ON d.date_id=f.date_id
                    JOIN dim_geography g ON g.geo_id=f.geo_id
                    JOIN bridge_track_artist b ON b.track_id=f.track_id
                    JOIN (SELECT track_id,COUNT(*) artist_count FROM bridge_track_artist GROUP BY track_id) c
                      ON c.track_id=f.track_id
                    WHERE g.country_code=%s AND b.artist_id=%s AND {dw}
                      AND COALESCE(l.label_name,'Unknown label') LIKE %s
                    GROUP BY l.label_name'''
            args=[country,artist_id,*date_args,pattern]
            caveat='Artist Dedication: credits are split equally among credited artists; country-wide market share is not applicable.'
            if sort in ('country_streams','share_pct'): sort='streams'
        else:
            sql=f'''SELECT a.label_name label,SUM(a.label_streams) streams,
                 MAX(den.country_streams) country_streams,
                 ROUND(100*SUM(a.label_streams)/NULLIF(MAX(den.country_streams),0),2) share_pct
                 FROM agg_label_market_share a
                 CROSS JOIN (SELECT SUM(country_total_streams) country_streams
                   FROM agg_country_share WHERE country_code=%s AND {aw}) den
                 WHERE a.country_code=%s AND {aw.replace('summary_date','a.summary_date')}
                   AND a.label_name LIKE %s
                 GROUP BY a.label_name'''
            args=[country,*ap,country,*ap,pattern]

    elif page == 'velocity':
        if scope=='weekly':
            if artist_id:
                bridge=one("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='bridge_album_artist'")
                if not bridge.get('n'):
                    return {'columns': columns,'rows':[],'page':page_number,'has_next':False,
                            'note':'Album-to-artist bridge not loaded.'}
            linked=(' AND EXISTS (SELECT 1 FROM bridge_album_artist ba WHERE ba.album_id=f.album_id AND ba.artist_id=%s)') if artist_id else ''
            sql=f'''SELECT COALESCE(al.album_name,'Unknown album') track,
                COALESCE(l.label_name,'Unknown label') label,
                MAX(f.entry_rank) entry_rank, MIN(f.peak_rank) peak_rank,
                MAX(f.entry_rank)-MIN(f.peak_rank) improvement,
                MAX(f.weeks_on_chart) days_on_chart,
                MAX(f.consecutive_weeks) streak
                FROM fact_album_performance f JOIN dim_album al ON al.album_id=f.album_id
                LEFT JOIN dim_label l ON l.label_id=al.label_id
                JOIN dim_date d ON d.date_id=f.date_id
                JOIN dim_geography g ON g.geo_id=f.geo_id
                WHERE g.country_code=%s AND {dw}{linked}
                  AND COALESCE(al.album_name,'') LIKE %s
                GROUP BY f.album_id,al.album_name,l.label_name'''
            args=[country,*date_args,*artist_args,pattern]
            caveat='Weekly album chart longevity and streak are measured in weeks.'
        else:
            selected='GLOBAL' if scope=='yearly' else country
            sql=f'''SELECT COALESCE(t.track_name,'Unknown track') track,
                COALESCE(l.label_name,'Unknown label') label,
                MAX(f.entry_rank) entry_rank, MIN(f.peak_rank) peak_rank,
                MAX(f.entry_rank)-MIN(f.peak_rank) improvement,
                MAX(f.days_on_chart) days_on_chart,MAX(f.consecutive_days) streak
                FROM fact_song_performance f
                JOIN dim_track t ON t.track_id=f.track_id
                LEFT JOIN dim_label l ON l.label_id=t.label_id
                JOIN dim_date d ON d.date_id=f.date_id
                JOIN dim_geography g ON g.geo_id=f.geo_id
                WHERE g.country_code=%s AND {dw}{credit_filter}
                  AND COALESCE(t.track_name,'') LIKE %s
                GROUP BY f.track_id,t.track_name,l.label_name'''
            args=[selected,*date_args,*artist_args,pattern]

    else:  # Artist Deep-Dive: per-track detail for the selected artist.
        if not artist_id:
            artist_id=one('''SELECT artist_id FROM dim_artists WHERE artist_name IS NOT NULL
                         ORDER BY monthly_listeners DESC LIMIT 1''').get('artist_id')
        if not artist_id:
            return {'columns':columns,'rows':[],'page':page_number,'has_next':False}
        geo_clause='' if country=='ALL' else ' AND g.country_code=%s'
        gp=[] if country=='ALL' else [country]
        sql=f'''SELECT COALESCE(t.track_name,'Unknown track') track,
            ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.artist_count,0)),0) streams,
            MIN(f.`rank`) best_rank, MIN(f.peak_rank) peak_rank,
            MAX(f.days_on_chart) days_on_chart,
            COUNT(DISTINCT CASE WHEN g.country_code<>'GLOBAL' THEN g.country_code END) markets
            FROM bridge_track_artist b
            JOIN fact_song_performance f ON f.track_id=b.track_id
            JOIN dim_track t ON t.track_id=f.track_id
            JOIN dim_date d ON d.date_id=f.date_id
            JOIN dim_geography g ON g.geo_id=f.geo_id
            JOIN (SELECT track_id,COUNT(*) artist_count FROM bridge_track_artist GROUP BY track_id) c
                 ON c.track_id=f.track_id
            WHERE b.artist_id=%s AND {dw}{geo_clause}
              AND COALESCE(t.track_name,'') LIKE %s
            GROUP BY f.track_id,t.track_name'''
        args=[artist_id,*date_args,*gp,pattern]
        caveat='Allocated track streams use equal shares for every credited artist.'

    query=f'''SELECT * FROM ({sql}) detail ORDER BY {sort} {direction}, {columns[0][0]} ASC LIMIT %s OFFSET %s'''
    items=rows(query,[*args,page_size+1,offset])
    return {'columns':columns,'rows':items[:page_size], 'page':page_number,
            'page_size':page_size,'has_next':len(items)>page_size,'sort':sort,
            'direction':direction,'note':caveat}
