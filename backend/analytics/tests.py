"""Basic route, input validation, and KPI formula tests (no MySQL required)."""
from datetime import date
from unittest.mock import patch
from django.test import SimpleTestCase
from django.urls import reverse
from .queries import percent, movement

class DashboardTests(SimpleTestCase):
    def test_pages_render(self):
        for name in ('global','regional','velocity','artist','weekly'):
            result=self.client.get(reverse(name))
            self.assertEqual(result.status_code,200)
            self.assertContains(result,'id="metrics"')

    @patch('analytics.views.queries.kpi_thresholds', return_value={})
    @patch('analytics.views.queries.global_pulse',return_value={'metrics':[],'history':[],'top':[]})
    def test_global_api_filters(self,service,thresholds):
        r=self.client.get('/api/global/?country=PH&start=2026-01-01&end=2026-02-01')
        self.assertEqual(r.status_code,200)
        service.assert_called_once_with('PH',date(2026,1,1),date(2026,2,1),None,'daily')

    def test_invalid_dates(self):
        self.assertEqual(self.client.get('/api/global/?start=bad').status_code,400)
        self.assertEqual(self.client.get('/api/global/?start=2026-02-01&end=2026-01-01').status_code,400)

    def test_invalid_identifiers(self):
        self.assertEqual(self.client.get('/api/artist/?artist_id=oops').status_code,400)
        self.assertEqual(self.client.get('/api/velocity/?track_id=-3').status_code,400)
        self.assertEqual(self.client.get('/api/global/?scope=biweekly').status_code,400)

    @patch('analytics.views.queries.history_bounds',return_value={'earliest':'2025-11-11','latest':'2026-11-10'})
    def test_metadata(self,service):
        self.assertEqual(self.client.get('/api/metadata/').status_code,200)

    def test_percent(self):
        self.assertEqual(percent(105,100),5)
        self.assertEqual(percent(94,100),-6)
        self.assertIsNone(percent(100,0))
        self.assertEqual(movement(5),'Stable')
        self.assertEqual(movement(-5.1),'Falling')


class DetailTableTests(SimpleTestCase):
    @patch('analytics.views.detail_tables.detail_table', return_value={
        'columns': [['track', 'Track']], 'rows': [], 'page': 1, 'has_next': False})
    def test_table_endpoint_filters(self, query):
        response = self.client.get('/api/table/global/?country=PH&size=10&search=pop')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(query.call_args.kwargs['country'], 'PH')
        self.assertEqual(query.call_args.kwargs['page_size'], 10)
        self.assertEqual(query.call_args.kwargs['search'], 'pop')

    def test_rejects_unbounded_pagination(self):
        self.assertEqual(self.client.get('/api/table/global/?size=99999').status_code, 400)
        self.assertEqual(self.client.get('/api/table/global/?page=-1').status_code, 400)
        self.assertEqual(self.client.get('/api/table/missing/').status_code, 404)

    def test_has_expandable_detail_section(self):
        for route in ('global', 'regional', 'velocity', 'artist', 'weekly'):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'id="detail-explorer"')
            self.assertContains(response, 'id="detail-search"')
            self.assertContains(response, 'id="detail-export"')

class CapabilityFilterTests(SimpleTestCase):
    @patch('analytics.views.queries.filter_availability', return_value={
        'countries': [{'code': 'PH', 'name': 'Philippines'}],
        'scopes': [{'value': 'daily', 'label': 'Daily Songs'}],
        'periods': [], 'notes': [], 'scope': 'daily'})
    def test_filter_options(self, mock_service):
        response = self.client.get('/api/filter-options/regional/?artist_id=42&start=2026-01-01')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['countries'][0]['code'], 'PH')
        self.assertEqual(mock_service.call_args.args[1], 42)

    def test_unknown_page_and_invalid_identifier(self):
        self.assertEqual(self.client.get('/api/filter-options/unknown/').status_code, 404)
        self.assertEqual(self.client.get('/api/filter-options/artist/?artist_id=bad').status_code, 400)

    @patch('analytics.queries.one', return_value={})
    @patch('analytics.queries.rows', return_value=[{'code':'PH','name':'Philippines'}])
    def test_yearly_scope_not_on_velocity(self, mock_rows, mock_one):
        from .queries import filter_availability
        response = filter_availability('velocity')
        self.assertEqual([s['value'] for s in response['scopes']], ['daily'])


class ExplicitArtistSelectionTests(SimpleTestCase):
    @patch('analytics.views.queries.artist_detail')
    def test_artist_api_never_defaults_to_a_named_artist(self, service):
        response = self.client.get('/api/artist/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['selection_required'])
        service.assert_not_called()

    @patch('analytics.views.detail_tables.detail_table')
    def test_unselected_artist_has_no_detail_rows(self, service):
        response = self.client.get('/api/table/artist/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rows'], [])
        service.assert_not_called()

    @patch('analytics.views.queries.filter_availability')
    def test_artist_markets_require_selection(self, service):
        response = self.client.get('/api/filter-options/artist/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['countries'], [])
        service.assert_not_called()


class V6AssetContractTests(SimpleTestCase):
    def test_zoom_script_and_icons_are_present(self):
        from pathlib import Path
        base = Path(__file__).resolve().parent.parent
        self.assertIn('visual-zoom.js', (base / 'templates' / 'base.html').read_text(encoding='utf-8'))
        self.assertIn('metricIcon', (base / 'static' / 'js' / 'main.js').read_text(encoding='utf-8'))
        self.assertIn('Zoom', (base / 'static' / 'js' / 'visual-zoom.js').read_text(encoding='utf-8'))


class V7RegionalContractTests(SimpleTestCase):
    def test_regional_market_share_is_a_time_series(self):
        from pathlib import Path
        base=Path(__file__).resolve().parent.parent
        template=(base/'templates/analytics/regional_rhythms.html').read_text(encoding='utf-8')
        javascript=(base/'static/js/main.js').read_text(encoding='utf-8')
        self.assertIn("chart_id='fourth-chart'",template)
        self.assertIn("charts().line('fourth-chart',d.history",javascript)
        self.assertNotIn('Country Share Map',template)

    def test_replacements_come_from_filtered_observations(self):
        from pathlib import Path
        code=(Path(__file__).resolve().parent/'queries.py').read_text(encoding='utf-8')
        self.assertIn('Observed Artist Chart Days',code)
        self.assertIn('New Entry Observations',code)
        self.assertIn('Ranked Tracks in Comparison',code)


class WeeklyAlbumV8Tests(SimpleTestCase):
    def test_weekly_page_content(self):
        r=self.client.get(reverse('weekly'))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'Weekly Album Insights')
        self.assertContains(r,'id="album-spotlight"')
        self.assertContains(r,'id="detail-explorer"')

    @patch('analytics.views.queries.kpi_thresholds', return_value={})
    @patch('analytics.views.queries.weekly_album_insights',return_value={'metrics':[],'history':[],'top':[],'leaders':[]})
    def test_weekly_api(self,service,thresholds):
        r=self.client.get('/api/weekly/?country=PH')
        self.assertEqual(r.status_code,200)
        service.assert_called_once_with('PH',None,None,None)

    @patch('analytics.views.queries.weekly_album_markets',return_value=[{'code':'GLOBAL','name':'Global'}])
    def test_weekly_filters(self,service):
        r=self.client.get('/api/filter-options/weekly/')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['scopes'][0]['value'],'weekly')

    @patch('analytics.views.queries.weekly_album_bounds',return_value={'earliest':'2025-11-06','latest':'2026-11-12'})
    def test_weekly_date_bounds(self,service):
        r=self.client.get('/api/metadata/weekly/')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['bounds']['latest'],'2026-11-12')


class V104WeeklyLongevityTrendTests(SimpleTestCase):
    def test_weekly_page_has_top10_staying_power_trend(self):
        response = self.client.get('/weekly-albums/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top 10 Album Staying Power Over Time')
        self.assertContains(response, 'id="fifth-chart"')

    def test_weekly_trend_is_from_ranked_weekly_album_observations(self):
        from pathlib import Path
        base = Path(__file__).resolve().parent.parent
        query = (base / 'analytics/queries.py').read_text(encoding='utf-8')
        js = (base / 'static/js/main.js').read_text(encoding='utf-8')
        self.assertIn('f.`rank` BETWEEN 1 AND 10 THEN f.weeks_on_chart', query)
        self.assertIn("charts().line('fifth-chart',d.history", js)


class V9GuideAndWeeklyTests(SimpleTestCase):
    def test_root_is_standalone_guide(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'YOUR ANALYTICS GUIDE')
        self.assertNotContains(response,'id="metrics"')
        self.assertContains(response,'Open Weekly Album Insights')

    def test_weekly_page_keeps_ranks_not_streams(self):
        response=self.client.get('/weekly-albums/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'YOUR GUIDE TO THIS PAGE')
        self.assertContains(response,'New Albums on the Weekly Chart')

    @patch('analytics.views.queries.filter_availability',return_value={
        'countries':[{'code':'GLOBAL','name':'Global'}],
        'scopes':[{'value':'daily','label':'Daily Songs'},{'value':'weekly','label':'Weekly Albums'}],
        'notes':['Weekly Albums is unavailable in these controls because its source has no streams or daily chart positions.']})
    def test_global_filters_exclude_weekly(self,service):
        response=self.client.get('/api/filter-options/global/')
        self.assertEqual(response.status_code,200)
        self.assertEqual([x['value'] for x in response.json()['scopes']],['daily'])
        self.assertEqual(response.json()['notes'],[])

    def test_global_rejects_outdated_weekly_scope(self):
        response=self.client.get('/api/global/?scope=weekly')
        self.assertEqual(response.status_code,400)


class V10ThresholdTests(SimpleTestCase):
    @patch('analytics.queries.kpi_thresholds', return_value={
        'Stream Momentum': {'high_value': 5, 'low_value': -5, 'description': 'Monthly change'},
        'Top 10 Chart Strength': {'high_value': 3, 'moderate_upper': 6, 'low_value': 10,
                                  'description': 'Average rank'},
        'New Entries vs Historical Baseline': {'high_value': 120, 'low_value': 80,
                                               'description': 'Historical baseline'},
    })
    def test_warehouse_rules_assign_correct_tones(self, _thresholds):
        from .queries import apply_kpi_thresholds
        data = {'metrics': [
            {'label': 'Stream Momentum', 'value': 6},
            {'label': 'Top 10 Chart Strength', 'value': 5},
            {'label': 'New Entries vs Historical Baseline', 'value': 70},
            {'label': 'Total Streams', 'value': 1000},
        ]}
        result = apply_kpi_thresholds(data)
        self.assertEqual([m.get('tone') for m in result['metrics']],
                         ['positive', 'neutral', 'negative', None])
        self.assertEqual(result['metrics'][0]['status'], 'Rising')
        self.assertEqual(result['metrics'][1]['status'], 'Moderate')
        self.assertEqual(result['metrics'][2]['status'], 'Low')
        self.assertEqual(result['metrics'][0]['threshold_source'], 'MySQL fact_kpi_thresholds')


class V102LayoutTests(SimpleTestCase):
    def test_weekly_new_entries_span_all_columns(self):
        response=self.client.get('/weekly-albums/')
        self.assertContains(response,'weekly-wide-trend')
        self.assertContains(response,'New Albums on the Weekly Chart')

    def test_artist_has_top_markets_instead_of_map_or_unavailable(self):
        response=self.client.get('/artist-deep-dive/')
        self.assertContains(response,'Top Countries by Artist Streams')
        self.assertContains(response,'id="artist-market-chart"')
        self.assertNotContains(response,'id="artist-map"')
        self.assertNotContains(response,'Metrics unavailable for this selection')


class V105WeeklyRankDistributionTests(SimpleTestCase):
    def test_weekly_page_has_rank_distribution(self):
        response = self.client.get('/weekly-albums/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Where Albums Rank on the Weekly Chart')
        self.assertContains(response, 'id="sixth-chart"')

    def test_rank_distribution_respects_artist_market_and_dates(self):
        from unittest.mock import patch
        from datetime import date
        from analytics import queries
        observed_sql = []

        def fake_rows(sql, params=()):
            observed_sql.append((sql, params))
            if 'rank_band' in sql:
                return [{'rank_band': 'Top 2-10', 'observations': 12}]
            return []

        with patch.object(queries, 'album_bridge_present', return_value=True), \
             patch.object(queries, 'rows', side_effect=fake_rows), \
             patch.object(queries, 'one', return_value={}):
            payload = queries.weekly_album_insights('PH', date(2026, 1, 1), date(2026, 2, 1), 42)
        self.assertEqual(payload['rank_distribution'][1]['observations'], 12)
        self.assertEqual(sum(x['observations'] for x in payload['rank_distribution']), 12)
        matching = [entry for entry in observed_sql if 'rank_band' in entry[0]]
        self.assertEqual(len(matching), 1)
        sql, args = matching[0]
        self.assertIn('g.country_code=%s', sql)
        self.assertIn('b.artist_id=%s', sql)
        self.assertEqual(args, ['PH', date(2026, 1, 1), date(2026, 2, 1), 42])


class V106WeeklyPresentationTests(SimpleTestCase):
    def test_weekly_page_retains_named_global_charts(self):
        response = self.client.get('/weekly-albums/')
        self.assertEqual(response.status_code, 200)
        for title in ('New Albums on the Weekly Chart',
                      'Top 10 Album Staying Power Over Time',
                      'Where Albums Rank on the Weekly Chart'):
            self.assertContains(response, title)

    def test_weekly_js_has_artist_specific_two_chart_mode(self):
        from pathlib import Path
        code=(Path(__file__).resolve().parent.parent/'static/js/main.js').read_text(encoding='utf-8')
        self.assertIn("const artistSelected=Boolean(filter().read('artist',''))",code)
        self.assertIn("showPanel('main-chart',artistSelected",code)
        self.assertIn("showPanel('secondary-chart',false)",code)
        self.assertIn("showPanel('third-chart',false)",code)
        self.assertIn("showPanel('fourth-chart',!artistSelected",code)
        self.assertIn("showPanel('fifth-chart',!artistSelected",code)
        self.assertIn("showPanel('sixth-chart',hasMeasure",code)

    @patch('analytics.views.queries.kpi_thresholds', return_value={})
    @patch('analytics.views.queries.weekly_album_insights', return_value={
        'metrics':[], 'history':[], 'top':[], 'leaders':[], 'rank_distribution':[]})
    def test_weekly_artist_is_forwarded_to_database_query(self, service, thresholds):
        response=self.client.get('/api/weekly/?artist_id=42&country=PH')
        self.assertEqual(response.status_code,200)
        service.assert_called_once_with('PH',None,None,42)
