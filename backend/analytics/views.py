"""Read-only dashboard pages and JSON API routes."""
from datetime import date
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, DatabaseError
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.conf import settings
from . import queries, detail_tables
from .warehouse_contract import REQUIRED_COLUMNS

PAGES = {
    'global': ('Global Pulse', 'analytics/global_pulse.html'),
    'regional': ('Regional Rhythms', 'analytics/regional_rhythms.html'),
    'velocity': ('Hit Velocity & Longevity', 'analytics/hit_velocity.html'),
    'artist': ('Artist Deep-Dive', 'analytics/artist_deep_dive.html'),
    'weekly': ('Weekly Album Insights', 'analytics/weekly_albums.html'),
}

def _inputs(request, page=None):
    code = request.GET.get('country', 'PH' if page == 'regional' else 'GLOBAL').strip().upper()
    if not code or len(code) > 6 or not code.replace('-', '').isalnum():
        raise ValueError('Invalid country code')
    scope = request.GET.get('scope', 'daily')
    if scope not in ('daily', 'weekly', 'yearly'):
        raise ValueError('Unknown chart scope')
    def integer(name):
        raw = request.GET.get(name, '').strip()
        if not raw: return None
        if not raw.isascii() or not raw.isdecimal() or int(raw) < 1 or int(raw) > 2147483647:
            raise ValueError(f'{name} must be a positive integer')
        return int(raw)
    def parsed(name):
        raw = request.GET.get(name, '').strip()
        if not raw: return None
        try: return date.fromisoformat(raw)
        except ValueError: raise ValueError(f'{name} must be YYYY-MM-DD')
    start, end = parsed('start'), parsed('end')
    if start and end and start > end: raise ValueError('Start date must precede end date')
    return {'country': code, 'scope': scope, 'artist_id': integer('artist_id'),
            'track_id': integer('track_id'), 'start': start, 'end': end}

@require_GET
def guide(request):
    return render(request, 'analytics/guide.html', {'page':'guide','title':'Getting Started'})

@require_GET
def dashboard(request, page='global'):
    if page not in PAGES: raise Http404('Unknown page')
    title, template = PAGES[page]
    return render(request, template, {'page': page, 'title': title})

@require_GET
def dashboard_data(request, page):
    if page not in PAGES: return JsonResponse({'error': 'Unknown page'}, status=404)
    try:
        p = _inputs(request, page)
        c, a, s, e = p['country'], p['artist_id'], p['start'], p['end']
        if page not in ('global', 'weekly') and p['scope'] != 'daily':
            raise ValueError('This dashboard supports Daily Songs only')
        if page == 'artist' and a is None:
            return JsonResponse({'selection_required': True, 'artist': None, 'metrics': [],
                                 'daily': [], 'reach': [], 'albums': [], 'caveats': []})
        if page == 'global' and p['scope'] == 'weekly':
            raise ValueError('Weekly album charts have a dedicated dashboard.')
        if page == 'weekly': data = queries.weekly_album_insights(c,s,e,a)
        elif page == 'global': data = queries.global_pulse(c,s,e,a,p['scope'])
        elif page == 'regional':
            if c == 'GLOBAL': raise ValueError('Select an individual country for Regional Rhythms')
            data = queries.regional(c,s,e,a)
        elif page == 'velocity': data = queries.velocity(c,s,e,a,p['track_id'],p['scope'])
        else: data = queries.artist_detail(a,c,s,e)
        return JsonResponse(queries.apply_kpi_thresholds(data), encoder=DjangoJSONEncoder)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except DatabaseError:
        return JsonResponse({'error': 'Warehouse query failed. Check database connection and schema.'}, status=503)

@require_GET
def artist_search(request):
    term = request.GET.get('q','').strip()[:80]
    if len(term) < 2: return JsonResponse({'results': []})
    try: return JsonResponse({'results':queries.search_artists(term)},encoder=DjangoJSONEncoder)
    except DatabaseError: return JsonResponse({'error':'Artist search unavailable'},status=503)

@require_GET
def markets(request):
    try: return JsonResponse({'results':queries.markets()},encoder=DjangoJSONEncoder)
    except DatabaseError: return JsonResponse({'error':'Markets unavailable'},status=503)

@require_GET
def metadata(request):
    try:return JsonResponse({'bounds':queries.history_bounds()},encoder=DjangoJSONEncoder)
    except DatabaseError:return JsonResponse({'error':'Warehouse metadata unavailable'},status=503)

@require_GET
def weekly_metadata(request):
    try: return JsonResponse({'bounds':queries.weekly_album_bounds()},encoder=DjangoJSONEncoder)
    except DatabaseError: return JsonResponse({'error':'Weekly album metadata unavailable'},status=503)

@require_GET
def health(request):
    """Verify selected schema and SELECT access without reading warehouse records."""
    try:
        with connection.cursor() as c:
            c.execute('SELECT DATABASE()')
            if c.fetchone()[0] != settings.DW_EXPECTED_SCHEMA:
                return JsonResponse({'status':'schema_mismatch'}, status=503)
            for table, columns in REQUIRED_COLUMNS.items():
                # Identifiers are a committed constant, never request parameters.
                projection = ', '.join(f'`{column}`' for column in columns)
                c.execute(f'SELECT {projection} FROM `{table}` WHERE 1=0')
        return JsonResponse({'status':'ok','schema':settings.DW_EXPECTED_SCHEMA,
                             'tables_verified':len(REQUIRED_COLUMNS)})
    except DatabaseError:return JsonResponse({'status':'database_unavailable'},status=503)


@require_GET
def table_data(request, page):
    """Searchable, sortable, paginated warehouse detail for each dashboard."""
    if page not in PAGES:
        return JsonResponse({'error': 'Unknown dashboard'}, status=404)
    try:
        p = _inputs(request, page)
        def bounded_positive(key, default, maximum):
            raw = request.GET.get(key, str(default))
            if not raw.isascii() or not raw.isdecimal() or not 1 <= int(raw) <= maximum:
                raise ValueError(f'{key} must be between 1 and {maximum}')
            return int(raw)
        if page == 'artist' and p['artist_id'] is None:
            return JsonResponse({'columns': detail_tables.SCHEMAS['artist'], 'rows': [],
                                 'page': 1, 'has_next': False,
                                 'note': 'Select an artist to view credited records.'})
        result = detail_tables.detail_table(
            page, country=p['country'], start=p['start'], end=p['end'],
            artist_id=p['artist_id'], scope=p['scope'],
            search=request.GET.get('search', ''),
            sort=request.GET.get('sort', ''),
            direction=request.GET.get('direction', 'desc'),
            page_number=bounded_positive('page', 1, 200),
            page_size=bounded_positive('size', 20, 50))
        return JsonResponse(result, encoder=DjangoJSONEncoder)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except DatabaseError:
        return JsonResponse({'error': 'Detail table query unavailable'}, status=503)


@require_GET
def filter_options(request, page):
    """Read-only options for capability-aware dashboard filters."""
    if page not in PAGES:
        return JsonResponse({'error':'Unknown dashboard'}, status=404)
    try:
        p = _inputs(request, page)
        if page == 'artist' and p['artist_id'] is None:
            return JsonResponse({'selection_required': True, 'countries': [],
                                 'scopes': [{'value': 'daily', 'label': 'Daily Songs'}],
                                 'notes': ['Select an artist to enable market filters.']})
        if page == 'weekly':
            available = queries.weekly_album_markets(p['artist_id'],p['start'],p['end'])
            results = {'countries': available,
                       'scopes': [{'value': 'weekly', 'label': 'Weekly Albums'}],
                       'notes': []}
        else:
            results = queries.filter_availability(page, p['artist_id'], p['start'], p['end'], p['scope'])
            if page in ('global','velocity'):
                results['notes'] = [n for n in results.get('notes',[]) if 'Weekly Album' not in n and 'weekly album' not in n]
            if page == 'global':
                results['scopes'] = [x for x in results.get('scopes',[]) if x.get('value') != 'weekly']
                results['notes'] = [n for n in results.get('notes',[]) if 'Weekly Album' not in n and 'weekly album' not in n]
        return JsonResponse(results, encoder=DjangoJSONEncoder)
    except ValueError as exc:
        return JsonResponse({'error':str(exc)}, status=400)
    except DatabaseError:
        return JsonResponse({'error':'Available filters unavailable'}, status=503)
