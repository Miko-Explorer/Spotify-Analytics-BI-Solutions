"""Read-only, parameterized KPI queries aligned to the capstone manuscript.

Fact queries select a market and dates before aggregation. No migrations or writes.
GLOBAL is a source chart, not the sum of the country charts.
"""
from datetime import timedelta
from django.db import connection
import pycountry


def rows(sql, params=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        if not cursor.description:
            return []
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, record)) for record in cursor.fetchall()]


def one(sql, params=()):
    return (rows(sql, params) or [{}])[0]


def dates(alias, start, end):
    parts, args = [], []
    if start:
        parts.append(f'{alias} >= %s'); args.append(start)
    if end:
        parts.append(f'{alias} <= %s'); args.append(end)
    return ' AND '.join(parts) or '1=1', args


def metric(label, value, fmt='integer', status=None, note=None):
    return dict(label=label, value=value, format=fmt, status=status, note=note)


def kpi_thresholds():
    """Use the warehouse's configured KPI thresholds, never client-side invented cutoffs.

    A missing or unpopulated threshold table leaves other dashboard values unchanged.
    """
    try:
        return {r['kpi_name']: r for r in rows("""SELECT kpi_name, threshold_type,
            high_value, moderate_upper, moderate_lower, low_value, description
            FROM fact_kpi_thresholds""")}
    except Exception as exc:
        # Older deployed warehouses may not yet include threshold configuration.
        from django.db import DatabaseError
        if isinstance(exc, DatabaseError):
            return {}
        raise


def apply_kpi_thresholds(data):
    """Attach interpretation metadata to KPI objects; preserve values and existing status.

    The three warehouse rules have different numeric meanings. Respect the
    documented rank direction and the percentage-baseline measure's own units.
    """
    configurations = kpi_thresholds()
    for item in data.get('metrics', []):
        name = item.get('label')
        number = item.get('value')
        if number is None:
            continue
        if name not in configurations:
            continue
        try:
            number = float(number)
        except (TypeError, ValueError, OverflowError):
            continue
        conf = configurations[name]
        hi = conf.get('high_value')
        lo = conf.get('low_value')
        if hi is None or lo is None:
            continue
        hi, lo = float(hi), float(lo)
        if name == 'Top 10 Chart Strength':
            # A smaller chart rank is stronger. moderate_upper is the middle-to-weak boundary.
            upper = float(conf['moderate_upper']) if conf.get('moderate_upper') is not None else lo
            if number <= hi:
                classification, tone = 'Strong', 'positive'
            elif number <= upper:
                classification, tone = 'Moderate', 'neutral'
            else:
                classification, tone = 'Weak', 'negative'
        elif name == 'Stream Momentum':
            if number > hi:
                classification, tone = 'Rising', 'positive'
            elif number < lo:
                classification, tone = 'Falling', 'negative'
            else:
                classification, tone = 'Stable', 'neutral'
        elif name == 'New Entries vs Historical Baseline':
            if number > hi:
                classification, tone = 'High', 'positive'
            elif number < lo:
                classification, tone = 'Low', 'negative'
            else:
                classification, tone = 'Normal', 'neutral'
        else:
            continue
        item['status'] = classification
        item['tone'] = tone
        item['threshold_description'] = conf.get('description') or ''
        item['threshold_source'] = 'MySQL fact_kpi_thresholds'
    return data


def movement(value):
    if value is None: return None
    return 'Rising' if value > 5 else 'Falling' if value < -5 else 'Stable'


def percent(current, previous):
    if previous in (None, 0) or current is None: return None
    return round((float(current) - float(previous)) * 100 / float(previous), 3)


def map_countries(items, field='code'):
    """Add ISO-3 country codes for Plotly, retaining original warehouse identifiers."""
    for item in items:
        code = (item.get(field) or '').upper()
        match = pycountry.countries.get(alpha_2=code)
        item['iso3'] = match.alpha_3 if match else None
    return items


def album_bridge_present():
    return bool(one("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='bridge_album_artist'").get('n'))


def weekly_albums(country, start, end, artist_id=None, kind='global'):
    where, dp = dates('d.full_date', start, end)
    if artist_id and not album_bridge_present():
        return {'metrics': [metric('Album attribution', None, 'text', note='Run optional album bridge SQL')],
                'history': [], 'top': [], 'status': [], 'tracks': [], 'scatter': [], 'rank': [],
                'histogram': [], 'box': [], 'caveats': ['Album-to-artist bridge is not loaded.']}
    credit = ' AND EXISTS (SELECT 1 FROM bridge_album_artist ba WHERE ba.album_id=f.album_id AND ba.artist_id=%s)' if artist_id else ''
    args = [country, *dp, *([artist_id] if artist_id else [])]
    base = f"""FROM fact_album_performance f JOIN dim_date d ON d.date_id=f.date_id
        JOIN dim_geography g ON g.geo_id=f.geo_id JOIN dim_album al ON al.album_id=f.album_id
        WHERE g.country_code=%s AND {where}{credit}"""
    history = rows(f"""SELECT d.full_date day, COUNT(*) albums,
        AVG(CASE WHEN f.`rank`<=10 THEN f.peak_rank END) peak_strength
        {base} GROUP BY d.full_date ORDER BY d.full_date""", args)
    top = rows(f"""SELECT al.album_name name,MIN(f.`rank`) best_rank,MAX(f.weeks_on_chart) weeks,
        MIN(f.peak_rank) peak_rank,MAX(f.entry_rank) entry_rank
        {base} GROUP BY f.album_id,al.album_name ORDER BY best_rank LIMIT 10""", args)
    status = []
    if history:
        status = rows(f"""SELECT CASE WHEN es.status_name='NEW' THEN 'NEW' ELSE 'RETURNING' END name,
            COUNT(*) value FROM fact_album_performance f JOIN dim_date d ON d.date_id=f.date_id
            JOIN dim_geography g ON g.geo_id=f.geo_id
            LEFT JOIN dim_entry_status es ON es.status_id=f.entry_status_id
            WHERE g.country_code=%s AND d.full_date=%s AND f.`rank`<=10{credit} GROUP BY name""",
            [country, history[-1]['day'], *([artist_id] if artist_id else [])])
    caveat = 'Weekly album charts contain rank and weeks-on-chart, but no stream counts.'
    if kind == 'global':
        return dict(country=country, scope='weekly', history=history, top=top, status=status,
            period={'from': history[0]['day'] if history else None, 'to': history[-1]['day'] if history else None},
            metrics=[metric('Total Streams vs. Previous Period',None,'compact',note=caveat),
                metric('Top 10 Chart Strength', history[-1].get('peak_strength') if history else None,'decimal',note='Weekly album Top 10'),
                metric('New Entries vs. Historical Baseline',None,'percent',note='No album historical baseline'),
                metric('Stream Momentum',None,'percent',note=caveat)],caveats=[caveat])
    points = rows(f"""SELECT f.album_id, COALESCE(al.album_name,'Unknown album') name,
        MIN(f.peak_rank) peak_rank,MAX(f.entry_rank) entry_rank,
        MAX(f.weeks_on_chart) days,MAX(f.consecutive_weeks) streak,
        MAX(f.entry_rank)-MIN(f.peak_rank) improvement
        {base} GROUP BY f.album_id,al.album_name ORDER BY improvement DESC LIMIT 100""",args)
    improvements = [x['improvement'] for x in points if x['improvement'] is not None]
    average_album_streak=one(f'''SELECT AVG(streak) average_streak FROM (
        SELECT MAX(f.consecutive_weeks) streak {base} GROUP BY f.album_id
    ) x''',args).get('average_streak')
    return dict(country=country,scope='weekly',tracks=points,scatter=points,rank=[],box=[],histogram=[],
        metrics=[metric('Avg. Chart Position Improvement',sum(improvements)/len(improvements) if improvements else None,'decimal',note='Top 100 albums shown'),
            metric('Max Track Longevity (Days)',None,'integer',note='Album longevity is measured in weeks'),
            metric('Daily Rank Change',None,'integer',note='Weekly chart updates'),
            metric('Average Consecutive Chart Streak',
                   average_album_streak,
                   'decimal',note='Average of each eligible album’s maximum consecutive weeks')],caveats=[caveat])




def weekly_album_insights(country='GLOBAL', start=None, end=None, artist_id=None):
    # Independent album-only analytics; rank and weeks are never treated as streams or days.
    where, params = dates('d.full_date', start, end)
    if artist_id is not None and not album_bridge_present():
        return {'metrics': [], 'history': [], 'top': [], 'leaders': [], 'caveats':
                ['Album artist attribution requires the optional album-to-artist bridge.']}
    credit = (' AND EXISTS (SELECT 1 FROM bridge_album_artist b WHERE b.album_id=f.album_id '
              'AND b.artist_id=%s)') if artist_id is not None else ''
    args = [country, *params, *([artist_id] if artist_id is not None else [])]
    base = f'''FROM fact_album_performance f
        JOIN dim_date d ON d.date_id=f.date_id
        JOIN dim_geography g ON g.geo_id=f.geo_id
        JOIN dim_album al ON al.album_id=f.album_id
        LEFT JOIN dim_entry_status es ON es.status_id=f.entry_status_id
        WHERE g.country_code=%s AND {where}{credit}'''
    history = rows(f'''SELECT d.full_date day, COUNT(*) albums,
        COUNT(DISTINCT f.album_id) unique_albums,
        SUM(CASE WHEN es.status_name='NEW' THEN 1 ELSE 0 END) new_entries,
        ROUND(AVG(CASE WHEN f.`rank` BETWEEN 1 AND 10 THEN f.weeks_on_chart END), 2) avg_top10_weeks
        {base} GROUP BY d.full_date ORDER BY d.full_date''', args)
    top = rows(f'''SELECT f.album_id, al.album_uri, COALESCE(al.album_name,'Unknown album') name,
        MIN(f.`rank`) best_rank, MAX(f.weeks_on_chart) weeks,
        MAX(f.consecutive_weeks) streak, COUNT(DISTINCT d.full_date) observed_weeks
        {base} GROUP BY f.album_id,al.album_name ORDER BY best_rank, weeks DESC LIMIT 10''',args)
    leaders = rows(f'''SELECT f.album_id,al.album_uri,COALESCE(al.album_name,'Unknown album') name,
        MAX(f.weeks_on_chart) weeks,MIN(f.`rank`) best_rank
        {base} GROUP BY f.album_id,al.album_name ORDER BY weeks DESC, best_rank LIMIT 10''',args)
    totals = one(f'''SELECT COUNT(DISTINCT f.album_id) distinct_albums,
        COUNT(DISTINCT CASE WHEN f.`rank`=1 THEN f.album_id END) number_one_albums, MAX(f.weeks_on_chart) longest_weeks {base}''',args)
    # Count actual weekly album appearances by chart-position band. This stays
    # useful even if a selected artist has one album or constant rank/longevity.
    # Apply exactly the same date, country, and artist filters as the other charts.
    rank_counts = rows(f'''SELECT
        CASE WHEN f.`rank` = 1 THEN 'Number 1'
             WHEN f.`rank` BETWEEN 2 AND 10 THEN 'Top 2-10'
             WHEN f.`rank` BETWEEN 11 AND 50 THEN 'Rank 11-50'
             WHEN f.`rank` BETWEEN 51 AND 100 THEN 'Rank 51-100'
             ELSE 'Rank 101+' END rank_band,
        COUNT(*) observations
        {base} AND f.`rank` IS NOT NULL
        GROUP BY rank_band''', args)
    rank_map = {item['rank_band']: item['observations'] for item in rank_counts}
    rank_distribution = [dict(band=band, observations=rank_map.get(band, 0)) for band in
                         ('Number 1', 'Top 2-10', 'Rank 11-50', 'Rank 51-100', 'Rank 101+')]
    if not rank_counts:
        rank_distribution = []
    date_count=len(history)
    return dict(country=country, scope='weekly', history=history, top=top, leaders=leaders,
        rank_distribution=rank_distribution,
        period={'from':history[0]['day'] if history else None,
                'to':history[-1]['day'] if history else None},
        metrics=[metric('Unique Charting Albums',totals.get('distinct_albums'),'integer',
                        note='Distinct albums appearing in selected weekly charts'),
                 metric('Observed Chart Weeks',date_count,'integer',
                        note='Number of weekly chart dates present in selected period'),
                 metric('Best Longevity (Weeks)',totals.get('longest_weeks'),'integer',
                        note='Longest reported weeks-on-chart among matching albums'),
                 metric('Albums Reaching #1',totals.get('number_one_albums'),'integer',
                        note='Distinct albums ranked first at least once during the selection')],
        caveats=[])


def weekly_album_bounds():
    return one('''SELECT MIN(d.full_date) earliest, MAX(d.full_date) latest
        FROM fact_album_performance f JOIN dim_date d ON d.date_id=f.date_id''')

def weekly_album_markets(artist_id=None, start=None, end=None):
    where, params=dates('d.full_date',start,end)
    credit=(' AND EXISTS (SELECT 1 FROM bridge_album_artist b WHERE b.album_id=f.album_id '
            'AND b.artist_id=%s)') if artist_id is not None else ''
    if artist_id is not None and not album_bridge_present():
        return []
    return rows(f'''SELECT g.country_code code,g.country_name name
       FROM fact_album_performance f
       JOIN dim_date d ON d.date_id=f.date_id
       JOIN dim_geography g ON g.geo_id=f.geo_id
       WHERE {where}{credit}
       GROUP BY g.country_code,g.country_name ORDER BY g.country_code''',
       [*params,*([artist_id] if artist_id is not None else [])])

def history_bounds():
    return one('SELECT MIN(summary_date) earliest, MAX(summary_date) latest FROM agg_daily_global_summary')


def markets():
    return rows('SELECT country_code AS code,country_name AS name FROM dim_geography ORDER BY (country_code<>\'GLOBAL\'),country_code')


def search_artists(q):
    return rows('''SELECT artist_id id,COALESCE(NULLIF(artist_name,''),'Unknown artist') name
        FROM dim_artists WHERE artist_name LIKE %s ORDER BY COALESCE(monthly_listeners,0) DESC LIMIT 15''', [q+'%'])


def top_credited_filter(artist_id, alias='f'):
    if artist_id is None: return '', []
    return f' AND EXISTS (SELECT 1 FROM bridge_track_artist ba WHERE ba.track_id={alias}.track_id AND ba.artist_id=%s)', [artist_id]


def global_pulse(country='GLOBAL', start=None, end=None, artist_id=None, scope='daily'):
    if scope == 'weekly': return weekly_albums(country,start,end,artist_id,'global')
    if scope=='yearly': country='GLOBAL'
    dw, dp = dates('d.full_date', start, end)
    credit, cp = top_credited_filter(artist_id)
    base = ''' FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
        JOIN dim_geography g ON g.geo_id=f.geo_id'''
    base_where = f' WHERE g.country_code=%s AND {dw}{credit}'
    params = [country, *dp, *cp]
    # Days per market: indexed date+geo facts; precomputed aggregate for non-artist GLOBAL.
    if artist_id is None and country == 'GLOBAL':
        aw, ap = dates('summary_date',start,end)
        history = rows(f'''SELECT summary_date day,total_streams streams,new_entry_count new_entries,
             avg_peak_rank_top10 peak_strength FROM agg_daily_global_summary
             WHERE {aw} ORDER BY summary_date''',ap)
    else:
        history = rows(f'''SELECT d.full_date day,SUM(COALESCE(f.streams,0)) streams,
              COUNT(DISTINCT CASE WHEN es.status_name='NEW' THEN f.track_id END) new_entries,
              AVG(CASE WHEN f.`rank`<=10 THEN f.peak_rank END) peak_strength
              {base} LEFT JOIN dim_entry_status es ON es.status_id=f.entry_status_id
              {base_where} GROUP BY d.full_date ORDER BY d.full_date''',params)
    top = rows(f'''SELECT f.track_id,COALESCE(t.track_name,'Unknown track') name,
            SUM(COALESCE(f.streams,0)) streams,MIN(f.`rank`) best_rank
            {base} JOIN dim_track t ON t.track_id=f.track_id {base_where}
            GROUP BY f.track_id,t.track_name ORDER BY streams DESC LIMIT 10''',params)
    # Sum of NEW observations per day, with distinct tracks per day. Baseline = daily 30-prior-day average.
    total = sum(int(r['streams'] or 0) for r in history)
    new = sum(int(r['new_entries'] or 0) for r in history)
    latest = history[-1] if history else {}
    prior = None
    if history:
        first_date = history[0]['day']; last_date=history[-1]['day']
        span = (last_date-first_date).days+1
        # Exact preceding equivalent calendar period, NOT first vs last day.
        prev_start=first_date-timedelta(days=span);prev_end=first_date-timedelta(days=1)
        w, a = dates('d.full_date',prev_start,prev_end)
        if artist_id is None and country == 'GLOBAL':
            prior=one('SELECT SUM(total_streams) s FROM agg_daily_global_summary WHERE summary_date BETWEEN %s AND %s',[prev_start,prev_end]).get('s')
        elif artist_id is None and country!='GLOBAL':
            prior=one('SELECT SUM(country_total_streams) s FROM agg_country_share WHERE country_code=%s AND summary_date BETWEEN %s AND %s',[country,prev_start,prev_end]).get('s')
        else:
            prior=one(f'''SELECT SUM(COALESCE(f.streams,0)) s {base} WHERE g.country_code=%s AND {w}{credit}''',[country,*a,*cp]).get('s')
    growth=percent(total,prior)
    peak=latest.get('peak_strength')
    peak_class=None if peak is None else ('Strong' if float(peak)<=3 else 'Moderate' if float(peak)<=6 else 'Weak')
    # Historical baseline is source GLOBAL only. Show N/A for country or artist subset.
    baseline = None
    if country=='GLOBAL' and artist_id is None and history:
        baseline=one('''SELECT SUM(historical_baseline) baseline,COUNT(historical_baseline) n
          FROM agg_new_entry_baseline WHERE baseline_date BETWEEN %s AND %s''',[history[0]['day'],latest['day']])
        if baseline.get('n') != len(history): baseline=None
    baseline_sum=baseline.get('baseline') if baseline else None
    entry_ratio = round(100*new/float(baseline_sum),2) if baseline_sum else None
    entry_class=None if entry_ratio is None else ('High' if entry_ratio>120 else 'Low' if entry_ratio<80 else 'Normal')
    # Top-10 at latest chart date, not across period, for NEW/RETURNING donut.
    status=[]
    if history:
        status=rows(f'''SELECT CASE WHEN es.status_name='NEW' THEN 'NEW' ELSE 'RETURNING' END name,
              COUNT(*) value {base} LEFT JOIN dim_entry_status es ON es.status_id=f.entry_status_id
              WHERE g.country_code=%s AND d.full_date=%s AND f.`rank`<=10{credit}
              GROUP BY name''',[country,latest['day'],*cp])
    return dict(country=country,history=history,top=top,status=status,
        scope=scope,period={'from':history[0]['day'] if history else None,'to':latest.get('day')},
        metrics=[metric('Total Streams vs. Previous Period',total,'compact',movement(growth),f'Previous period: {prior:,}' if prior is not None else 'Previous equivalent period unavailable'),
            metric('Top 10 Chart Strength',peak,'decimal',peak_class,'Latest date: average peak rank for chart Top 10'),
            metric('New Entries vs. Historical Baseline' if entry_ratio is not None else 'New Entry Observations',
                   entry_ratio if entry_ratio is not None else (new if history else None),
                   'percent' if entry_ratio is not None else 'integer',entry_class,
                   'Historical baseline ratio' if entry_ratio is not None else 'Sum of daily NEW chart entries in selected market and dates'),
            metric('Stream Momentum' if growth is not None else 'Observed Chart Days',
                   growth if growth is not None else (len(history) if history else None),
                   'percent' if growth is not None else 'integer',movement(growth) if growth is not None else None,
                   'Change versus preceding equivalent period' if growth is not None else 'Days with chart-stream observations; no comparable preceding period')],
        new_entry_count=new)


def top_label_share(country, start=None, end=None):
    """Leading label's streams divided by all charted country streams, including unknown labels."""
    w, args = dates('summary_date', start, end)
    data = one(f"""SELECT MAX(label_total) leader_streams FROM (
       SELECT SUM(label_streams) label_total FROM agg_label_market_share
       WHERE country_code=%s AND {w} GROUP BY label_name
       ) x""", [country, *args])
    denom = one(f"""SELECT SUM(country_total_streams) total_streams
       FROM agg_country_share WHERE country_code=%s AND {w}""", [country, *args])
    n, d = data.get('leader_streams'), denom.get('total_streams')
    return round(100*float(n)/float(d),2) if n is not None and d else None


def regional(country='PH',start=None,end=None,artist_id=None):
    aw,ap=dates('summary_date',start,end)
    history=rows(f'''SELECT summary_date day,share_pct share,share_change_pct change_pct,
        country_total_streams streams,global_total_streams global_streams
        FROM agg_country_share WHERE country_code=%s AND {aw} ORDER BY summary_date''',[country,*ap])
    latest=history[-1] if history else {}
    diversity=one(f'''SELECT unique_artist_count_top50 artists,diversity_class category
        FROM agg_regional_diversity WHERE country_code=%s AND {aw}
        ORDER BY summary_date DESC LIMIT 1''',[country,*ap])
    # Actual selected-country artist leaderboard by mean chart rank.
    w,dp=dates('d.full_date',start,end)
    artist_filter=' AND f.artist_id=%s' if artist_id else ''
    ar=[artist_id] if artist_id else []
    top_artists=rows(f'''SELECT a.artist_id,COALESCE(a.artist_name,'Unknown artist') name,
        ROUND(AVG(f.`rank`),2) avg_rank,COUNT(*) chart_days
        FROM fact_artists_performance f JOIN dim_date d ON d.date_id=f.date_id
        JOIN dim_geography g ON g.geo_id=f.geo_id
        JOIN dim_artists a ON a.artist_id=f.artist_id
        WHERE g.country_code=%s AND {w}{artist_filter}
        GROUP BY a.artist_id,a.artist_name ORDER BY avg_rank,chart_days DESC LIMIT 5''',[country,*dp,*ar])
    # Lead by allocated streams, credit split equally for multi-artist tracks.
    credit,cp=top_credited_filter(artist_id)
    local_hero=one(f"""WITH artist_totals AS (
       SELECT b.artist_id,a.artist_name name,
         ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.cnt,0)),0) streams
       FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
       JOIN dim_geography g ON g.geo_id=f.geo_id
       JOIN bridge_track_artist b ON b.track_id=f.track_id
       JOIN dim_artists a ON a.artist_id=b.artist_id
       JOIN (SELECT track_id,COUNT(*) cnt FROM bridge_track_artist GROUP BY track_id) c ON c.track_id=f.track_id
       WHERE g.country_code=%s AND {w}
       GROUP BY b.artist_id,a.artist_name
    ), ranked AS (
       SELECT *,PERCENT_RANK() OVER (ORDER BY streams) percentile FROM artist_totals
    )
    SELECT artist_id,name,streams,percentile FROM ranked
    {'WHERE artist_id=%s' if artist_id else ''}
    ORDER BY streams DESC LIMIT 1""",[country,*dp,*ar])
    hero_pct=local_hero.get('percentile')
    hero_class=None if hero_pct is None else ('High' if float(hero_pct)>.75 else 'Low' if float(hero_pct)<.25 else 'Moderate')
    # Label breakdown aggregate is precomputed by country/day.
    labels=rows(f'''SELECT label_name,SUM(label_streams) streams FROM agg_label_market_share
         WHERE country_code=%s AND {aw} GROUP BY label_name ORDER BY streams DESC LIMIT 8''',[country,*ap])
    # Overlay the selected country's daily #1 track streams vs that SAME track's GLOBAL streams.
    compare=rows(f'''SELECT d.full_date day,COALESCE(local.streams,0) local_streams,
        global_f.streams global_streams,t.track_name track
        FROM fact_song_performance local
        JOIN dim_date d ON d.date_id=local.date_id
        JOIN dim_geography g ON g.geo_id=local.geo_id AND g.country_code=%s
        JOIN dim_track t ON t.track_id=local.track_id
        LEFT JOIN dim_geography gg ON gg.country_code='GLOBAL'
        LEFT JOIN fact_song_performance global_f ON global_f.date_id=local.date_id
            AND global_f.geo_id=gg.geo_id AND global_f.track_id=local.track_id
        WHERE local.`rank`=1 AND {w}{credit.replace('f.track_id','local.track_id')}
        ORDER BY d.full_date''',[country,*dp,*cp])
    shares=rows(f'''SELECT country_code,ROUND(100*SUM(country_total_streams)/NULLIF(SUM(global_total_streams),0),4) share_pct
        FROM agg_country_share WHERE {aw} GROUP BY country_code ORDER BY share_pct DESC''',ap)
    if artist_id is not None:
        # Dedication Mode: artist share of chart streams in each country, never market-wide share.
        history=rows(f"""WITH per_day AS (
           SELECT d.full_date day,
             ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.cnt,0)),0) streams
           FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
           JOIN dim_geography g ON g.geo_id=f.geo_id
           JOIN bridge_track_artist b ON b.track_id=f.track_id
           JOIN (SELECT track_id,COUNT(*) cnt FROM bridge_track_artist GROUP BY track_id) c ON c.track_id=f.track_id
           WHERE b.artist_id=%s AND g.country_code=%s AND {w}
           GROUP BY d.full_date
         ), share AS (
           SELECT per_day.day,per_day.streams,ROUND(100*per_day.streams/NULLIF(a.country_total_streams,0),4) share
           FROM per_day JOIN agg_country_share a ON a.summary_date=per_day.day AND a.country_code=%s
         )
         SELECT day,streams,share,ROUND(100*(share-LAG(share) OVER (ORDER BY day)) /
                    NULLIF(LAG(share) OVER (ORDER BY day),0),4) change_pct
         FROM share ORDER BY day""",[artist_id,country,*dp,country])
        latest=history[-1] if history else {}
        diversity={}
        labels=rows(f"""SELECT COALESCE(l.label_name,'Unknown label') label_name,
             ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.cnt,0)),0) streams
             FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
             JOIN dim_geography g ON g.geo_id=f.geo_id
             JOIN bridge_track_artist b ON b.track_id=f.track_id
             JOIN (SELECT track_id,COUNT(*) cnt FROM bridge_track_artist GROUP BY track_id) c ON c.track_id=f.track_id
             JOIN dim_track t ON t.track_id=f.track_id LEFT JOIN dim_label l ON l.label_id=t.label_id
             WHERE b.artist_id=%s AND g.country_code=%s AND {w}
             GROUP BY label_name ORDER BY streams DESC LIMIT 8""",[artist_id,country,*dp])
        shares=rows(f"""SELECT g.country_code,ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.cnt,0)),0) artist_streams
             FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
             JOIN dim_geography g ON g.geo_id=f.geo_id
             JOIN bridge_track_artist b ON b.track_id=f.track_id
             JOIN (SELECT track_id,COUNT(*) cnt FROM bridge_track_artist GROUP BY track_id) c ON c.track_id=f.track_id
             WHERE b.artist_id=%s AND g.country_code<>'GLOBAL' AND {w}
             GROUP BY g.country_code""",[artist_id,*dp])
    change=latest.get('change_pct');reach=latest.get('share')
    return dict(country=country,artist_mode=bool(artist_id),history=history,top_artists=top_artists,labels=labels,compare=compare,shares=map_countries(shares, 'country_code'),
        local_hero=local_hero,period={'from':history[0]['day'] if history else None,'to':latest.get('day')},
        metrics=[metric('Leading Artist Volume',local_hero.get('streams'),'compact',hero_class,local_hero.get('name','No chart artist')),
            metric('Observed Artist Chart Days' if artist_id else 'Unique Artist Count (Top 50)',
                   len(history) if artist_id and history else diversity.get('artists'),
                   'integer',None if artist_id else diversity.get('category'),
                   'Days with credited streams in the selected market' if artist_id else 'Latest available Top 50 artist diversity'),
            metric('Change in Country Share (%)',change,'percent',movement(change),f'Latest artist share: {reach}%' if artist_id else f'Latest market share: {reach}%'),
            metric('Top Record Label Market Share',
                (100 * float(labels[0]['streams']) / sum(float(x.get('streams') or 0) for x in history) if labels and sum(float(x.get('streams') or 0) for x in history)>0 else None) if artist_id else
                top_label_share(country,start,end), 'percent',
                note='Leading credited label streams as a share of the artist’s allocated streams in this country' if artist_id else 'Leading label streams divided by all country chart streams')])


def velocity(country='GLOBAL',start=None,end=None,artist_id=None,track_id=None,scope='daily'):
    if scope == 'weekly': return weekly_albums(country,start,end,artist_id,'velocity')
    w,dp=dates('d.full_date',start,end)
    credit,cp=top_credited_filter(artist_id)
    # Scope selected-country tracked songs, one per track. Window rows are limited by dates/country.
    base=f'''FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
        JOIN dim_geography g ON g.geo_id=f.geo_id
        JOIN dim_track t ON t.track_id=f.track_id
        WHERE g.country_code=%s AND {w}{credit}'''
    params=[country,*dp,*cp]
    # Do not reuse agg_track_velocity for GLOBAL: its ETL mixes all country charts.
    full_global=False
    if full_global:
        velocity_rows=rows("""SELECT v.track_id,COALESCE(t.track_name,'Unknown track') name,
          v.entry_rank,v.peak_rank,v.climbing_speed_delta improvement,
          l.days_on_chart days,l.max_consecutive_streak streak
          FROM agg_track_velocity v JOIN dim_track t ON t.track_id=v.track_id
          LEFT JOIN agg_longevity_benchmarks l ON l.track_id=v.track_id
          ORDER BY v.climbing_speed_delta DESC LIMIT 100""")
        summary=one("""SELECT AVG(climbing_speed_delta) avg_improvement FROM agg_track_velocity""")
        summary['max_days']=one('SELECT MAX(days_on_chart) m FROM agg_longevity_benchmarks').get('m')
    else:
        velocity_rows=rows(f"""SELECT f.track_id,COALESCE(t.track_name,'Unknown track') name,
            MIN(f.peak_rank) peak_rank,MAX(f.entry_rank) entry_rank,
            MAX(f.days_on_chart) days,MAX(f.consecutive_days) streak,
            MAX(f.entry_rank)-MIN(f.peak_rank) improvement
            {base} GROUP BY f.track_id,t.track_name ORDER BY improvement DESC LIMIT 100""",params)
        summary=one(f"""SELECT AVG(x.improvement) avg_improvement,MAX(x.days) max_days
            FROM (SELECT f.track_id,MAX(f.entry_rank)-MIN(f.peak_rank) improvement,
            MAX(f.days_on_chart) days {base} GROUP BY f.track_id) x""",params)
    leader=next((x for x in sorted(velocity_rows,key=lambda z:z['days'] or 0,reverse=True)),{})
    if track_id is None and velocity_rows: track_id=velocity_rows[0]['track_id']
    rank=[]
    if track_id:
        rank=rows(f"""SELECT d.full_date day,f.`rank` chart_rank,f.previous_rank,
            CASE WHEN f.previous_rank IS NULL THEN NULL ELSE f.previous_rank-f.`rank` END rank_change
            {base} AND f.track_id=%s ORDER BY d.full_date""",[*params,track_id])
    if full_global:
        histogram=rows("""SELECT FLOOR(max_consecutive_streak/10)*10 bucket,COUNT(*) count
            FROM agg_longevity_benchmarks WHERE max_consecutive_streak IS NOT NULL
            GROUP BY bucket ORDER BY bucket LIMIT 55""")
        box=rows("""SELECT l.label_name,lb.days_on_chart days FROM agg_longevity_benchmarks lb
           JOIN dim_track t ON t.track_id=lb.track_id JOIN dim_label l ON l.label_id=t.label_id
           JOIN (SELECT t.label_id FROM agg_longevity_benchmarks a
                 JOIN dim_track t ON t.track_id=a.track_id
                 WHERE t.label_id IS NOT NULL GROUP BY t.label_id ORDER BY COUNT(*) DESC LIMIT 8) leading
           ON leading.label_id=t.label_id
           WHERE lb.days_on_chart IS NOT NULL LIMIT 2400""")
    else:
        histogram=rows(f"""SELECT FLOOR(t.streak/10)*10 bucket,COUNT(*) count
             FROM (SELECT f.track_id,MAX(f.consecutive_days) streak {base} GROUP BY f.track_id) t
             WHERE t.streak IS NOT NULL GROUP BY bucket ORDER BY bucket LIMIT 55""",params)
        box=rows(f"""SELECT x.label_name,x.days FROM (
           SELECT l.label_name,MAX(f.days_on_chart) days
           FROM fact_song_performance f JOIN dim_date d ON d.date_id=f.date_id
           JOIN dim_geography g ON g.geo_id=f.geo_id
           JOIN dim_track t ON t.track_id=f.track_id
           JOIN dim_label l ON l.label_id=t.label_id
           WHERE g.country_code=%s AND {w}{credit}
           GROUP BY f.track_id,l.label_name) x LIMIT 2400""",params)
    speed_class=None
    longevity_class=None
    if full_global:
        pct_velocity=one('''WITH measured AS (
           SELECT climbing_speed_delta val,PERCENT_RANK() OVER (ORDER BY climbing_speed_delta) pct
           FROM agg_track_velocity WHERE climbing_speed_delta IS NOT NULL)
           SELECT MIN(CASE WHEN pct>=0.25 THEN val END) p25,
                  MIN(CASE WHEN pct>=0.75 THEN val END) p75 FROM measured''')
        pct_longevity=one('''WITH measured AS (
           SELECT days_on_chart val,PERCENT_RANK() OVER (ORDER BY days_on_chart) pct
           FROM agg_longevity_benchmarks WHERE days_on_chart IS NOT NULL)
           SELECT MIN(CASE WHEN pct>=0.25 THEN val END) p25,
                  MIN(CASE WHEN pct>=0.75 THEN val END) p75 FROM measured''')
        average=summary.get('avg_improvement');longest=summary.get('max_days')
        if average is not None and pct_velocity.get('p75') is not None:
            speed_class=('Fast' if average>=pct_velocity['p75'] else
                         'Moderate' if average>=pct_velocity['p25'] else 'Slow')
        if longest is not None and pct_longevity.get('p75') is not None:
            longevity_class=('High' if longest>=pct_longevity['p75'] else
                             'Moderate' if longest>=pct_longevity['p25'] else 'Low')
    if not full_global:
        quantiles=rows(f"""WITH per_track AS (
           SELECT f.track_id,MAX(f.entry_rank)-MIN(f.peak_rank) improvement,
                  MAX(f.days_on_chart) longevity {base} GROUP BY f.track_id
         ), ranked AS (
           SELECT improvement,longevity,
             PERCENT_RANK() OVER (ORDER BY improvement) speed_pct,
             PERCENT_RANK() OVER (ORDER BY longevity) longevity_pct
           FROM per_track WHERE improvement IS NOT NULL AND longevity IS NOT NULL
         )
         SELECT MIN(CASE WHEN speed_pct>=0.25 THEN improvement END) speed25,
                MIN(CASE WHEN speed_pct>=0.75 THEN improvement END) speed75,
                MIN(CASE WHEN longevity_pct>=0.25 THEN longevity END) days25,
                MIN(CASE WHEN longevity_pct>=0.75 THEN longevity END) days75
         FROM ranked""",params)
        thresholds=quantiles[0] if quantiles else {}
        mean=summary.get('avg_improvement');maximum=summary.get('max_days')
        if mean is not None and thresholds.get('speed75') is not None:
            speed_class='Fast' if mean>=thresholds['speed75'] else 'Moderate' if mean>=thresholds['speed25'] else 'Slow'
        if maximum is not None and thresholds.get('days75') is not None:
            longevity_class='High' if maximum>=thresholds['days75'] else 'Moderate' if maximum>=thresholds['days25'] else 'Low'
    avg_streak=one(f'''SELECT AVG(x.streak) average_streak FROM (
        SELECT MAX(f.consecutive_days) streak {base} GROUP BY f.track_id
    ) x''',params).get('average_streak')
    latest_rank=rank[-1] if rank else {}
    return dict(country=country,scope=scope,tracks=velocity_rows,scatter=velocity_rows,
        histogram=histogram,box=box,rank=rank,selected_track=track_id,
        metrics=[metric('Avg. Chart Position Improvement',summary.get('avg_improvement'),'decimal',speed_class,'Entry rank minus best peak rank; selected market percentile'),
            metric('Max Track Longevity (Days)',summary.get('max_days'),'integer',longevity_class,'Maximum chart days among eligible tracks'),
            metric('Daily Rank Change' if latest_rank.get('rank_change') is not None else 'Ranked Tracks in Comparison',
                  latest_rank.get('rank_change') if latest_rank.get('rank_change') is not None else (len(velocity_rows) if velocity_rows else None),
                  'integer',
                  ('Rising' if latest_rank.get('rank_change')>0 else 'Falling' if latest_rank.get('rank_change')<0 else 'Stable') if latest_rank.get('rank_change') is not None else None,
                  'Most recent rank movement of selected track' if latest_rank.get('rank_change') is not None else 'Distinct tracks in the filtered comparison, capped at 100'),
            metric('Average Consecutive Chart Streak',avg_streak,'decimal',note='Average of each track’s maximum observed consecutive days')])


def artist_detail(artist_id=None,country='GLOBAL',start=None,end=None):
    if artist_id is None:
        return {'selection_required': True, 'artist': None, 'metrics': [],
                'daily': [], 'reach': [], 'albums': [], 'caveats': []}
    artist=one('SELECT artist_id,artist_name,monthly_listeners,monthly_listeners_peak FROM dim_artists WHERE artist_id=%s',[artist_id])
    if not artist: return {'artist':None,'metrics':[], 'daily':[], 'reach':[], 'albums':[]}
    aid=artist['artist_id']
    w,dp=dates('d.full_date',start,end)
    geo=' AND g.country_code=%s' if country!='ALL' else " AND g.country_code<>'GLOBAL'"
    gp=[country] if country!='ALL' else []
    daily=rows(f'''SELECT d.full_date day,ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.credit_count,0)),0) streams
        FROM bridge_track_artist b JOIN fact_song_performance f ON f.track_id=b.track_id
        JOIN dim_date d ON d.date_id=f.date_id JOIN dim_geography g ON g.geo_id=f.geo_id
        JOIN (SELECT track_id,COUNT(*) credit_count FROM bridge_track_artist GROUP BY track_id) c ON c.track_id=b.track_id
        WHERE b.artist_id=%s AND {w}{geo}
        GROUP BY d.full_date ORDER BY d.full_date''',[aid,*dp,*gp])
    # Reach country code chart presence (GLOBAL excluded), for current scope.
    reach=rows(f'''SELECT g.country_code code,COUNT(DISTINCT d.full_date) chart_days,
         ROUND(SUM(COALESCE(f.streams,0)/NULLIF(c.credit_count,0)),0) streams
         FROM bridge_track_artist b JOIN fact_song_performance f ON f.track_id=b.track_id
         JOIN dim_date d ON d.date_id=f.date_id JOIN dim_geography g ON g.geo_id=f.geo_id
         JOIN (SELECT track_id,COUNT(*) credit_count FROM bridge_track_artist GROUP BY track_id) c ON c.track_id=b.track_id
         WHERE b.artist_id=%s AND g.country_code<>'GLOBAL' AND {w}
           AND (%s IN ('GLOBAL','ALL') OR g.country_code=%s)
         GROUP BY g.country_code ORDER BY streams DESC''',[aid,*dp,country,country])
    # Album credits are held only as pipe-delimited strings in STAGING, not as a warehouse bridge.
    # Avoid an unverified artist-to-album join. See README for the required album bridge.
    albums=[]
    if album_bridge_present():
        albums=rows("""SELECT COALESCE(al.album_name,'Unknown album') name,
          MAX(f.weeks_on_chart) weeks,ROUND(AVG(f.`rank`),2) avg_rank
          FROM bridge_album_artist ba JOIN fact_album_performance f ON f.album_id=ba.album_id
          JOIN dim_album al ON al.album_id=ba.album_id JOIN dim_geography g ON g.geo_id=f.geo_id
          WHERE ba.artist_id=%s AND (%s='ALL' OR g.country_code=%s)
          GROUP BY f.album_id,al.album_name ORDER BY weeks DESC LIMIT 12""",[aid,country,country])
    momentum=rows('''SELECT period_start day,current_period_streams streams,growth_rate_pct growth
         FROM agg_artist_momentum WHERE artist_id=%s ORDER BY period_start DESC LIMIT 52''',[aid])
    # The stream-growth KPI must follow the chosen country/date filters.
    # Compare the last two complete, contiguous 7-day periods within the
    # selected daily series, avoiding unrelated GLOBAL artist momentum.
    from datetime import timedelta
    daily_values={r['day']:float(r.get('streams') or 0) for r in daily}
    last_day=max(daily_values) if daily_values else None
    growth=None
    if last_day:
        current_days=[last_day-timedelta(days=i) for i in range(7)]
        previous_days=[last_day-timedelta(days=i) for i in range(7,14)]
        if all(day in daily_values for day in current_days + previous_days):
            current_streams=sum(daily_values[day] for day in current_days)
            previous_streams=sum(daily_values[day] for day in previous_days)
            growth=percent(current_streams,previous_streams)
    # Preserve four relevant KPI positions if a valid comparison is absent.
    # A daily mean has a truthful denominator whenever stream observations exist.
    growth_metric=(metric('Artist Stream Growth Rate',growth,'percent',movement(growth),
                         'Latest two complete 7-day periods in selected market and dates')
                   if growth is not None else
                   metric('Average Chart-Day Streams',
                          sum(daily_values.values())/len(daily_values) if daily_values else None,
                          'compact',note='Available chart-day mean; insufficient comparable days for growth'))
    return dict(artist=artist,country=country,daily=daily,reach=map_countries(reach),albums=albums,
        momentum=list(reversed(momentum)),
        metrics=[metric('Max Monthly Listeners' if artist.get('monthly_listeners_peak') is not None else 'Observed Artist Chart Days',
                   artist.get('monthly_listeners_peak') if artist.get('monthly_listeners_peak') is not None else (len(daily) if daily else None),
                   'compact' if artist.get('monthly_listeners_peak') is not None else 'integer',
                   note='Artist-master historical peak, independent of country/date filters' if artist.get('monthly_listeners_peak') is not None else 'Days containing credited artist streams in selected market'),
            metric('Distinct Country Count',len(reach),'integer',note='Country charts containing credited tracks'),
            growth_metric,
            metric('Total Artist Streams',sum(float(r.get('streams') or 0) for r in daily),'compact',note='Equal credited share of track streams in selected chart market and dates')],
        caveats=([ 'Album comparison requires the optional album-to-artist bridge.' ] if not album_bridge_present() else []))


# Filter availability is calculated from observed chart data, not the whole geography dictionary.
def filter_availability(page, artist_id=None, start=None, end=None, scope='daily'):
    """Return only viable market/scope options for the selected page and artist.

    Weekly albums are withheld from the interactive selector because multiple
    mandatory manuscript KPIs require daily streams or daily ranks.
    The unfiltered full-history analysis is still available in the warehouse.
    """
    if page not in ('global', 'regional', 'velocity', 'artist'):
        raise ValueError('Unknown dashboard')
    if scope not in ('daily', 'yearly'):
        scope = 'daily'
    if page != 'global':
        scope = 'daily'
    if page == 'global' and scope == 'yearly':
        if artist_id is not None:
            date_where, date_args = dates('d.full_date',start,end)
            available = rows(f"""SELECT g.country_code code, g.country_name name
                FROM bridge_track_artist b
                JOIN fact_song_performance f ON f.track_id=b.track_id
                JOIN dim_date d ON d.date_id=f.date_id
                JOIN dim_geography g ON g.geo_id=f.geo_id
                WHERE b.artist_id=%s AND g.country_code='GLOBAL' AND {date_where}
                LIMIT 1""", [artist_id,*date_args])
        else:
            aw, ap = dates('summary_date',start,end)
            available = ([{'code':'GLOBAL','name':'Global'}]
                         if one(f'SELECT 1 ok FROM agg_daily_global_summary WHERE {aw} LIMIT 1',ap).get('ok')
                         else [])
    elif artist_id is not None:
        date_where, date_args = dates('d.full_date', start, end)
        available = rows(f"""SELECT g.country_code code, g.country_name name, MIN(d.full_date) earliest, MAX(d.full_date) latest
            FROM bridge_track_artist b
            JOIN fact_song_performance f ON f.track_id=b.track_id
            JOIN dim_geography g ON g.geo_id=f.geo_id
            JOIN dim_date d ON d.date_id=f.date_id
            WHERE b.artist_id=%s AND {date_where}
            GROUP BY g.country_code,g.country_name ORDER BY code""", [artist_id, *date_args])
    else:
        date_where, date_args = dates('a.summary_date', start, end)
        available = rows(f"""SELECT g.country_code code, g.country_name name, MIN(a.summary_date) earliest, MAX(a.summary_date) latest
            FROM agg_country_share a JOIN dim_geography g ON g.country_code=a.country_code
            WHERE {date_where} GROUP BY g.country_code,g.country_name ORDER BY code""", date_args)
        if page != 'regional':
            gw, gp = dates('summary_date',start,end)
            if one(f'SELECT 1 ok FROM agg_daily_global_summary WHERE {gw} LIMIT 1',gp).get('ok'):
                available.insert(0, {'code':'GLOBAL','name':'Global'})
    if page == 'regional':
        available = [x for x in available if x['code'] != 'GLOBAL']
    if page == 'artist' and available:
        available.insert(0, {'code':'ALL','name':'All chart markets'})
    # An artist without any charted track has no supported country; do not offer
    # the misleading global option in this case.
    return {
        'countries': available,
        'scopes': ([{'value':'daily','label':'Daily Songs'},
                    {'value':'yearly','label':'Global Yearly Aggregate'}]
                   if page=='global' else [{'value':'daily','label':'Daily Songs'}]),
        'periods': [{'value':'all','label':'All available history'},
                    {'value':'30','label':'Latest 30 days'},
                    {'value':'90','label':'Latest 90 days'},
                    {'value':'365','label':'Latest 365 days'},
                    {'value':'custom','label':'Custom range'}],
        'scope': scope,
        'notes': (['Weekly Albums is unavailable in these controls because its source has no streams or daily chart positions.']
                  if page in ('global','velocity') else []),
    }
