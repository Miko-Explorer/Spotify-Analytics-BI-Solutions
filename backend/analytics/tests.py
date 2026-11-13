"""Basic route, input validation, and KPI formula tests (no MySQL required)."""
from datetime import date
from unittest.mock import patch
from django.test import SimpleTestCase
from django.urls import reverse
from .queries import percent, movement

class DashboardTests(SimpleTestCase):
    def test_pages_render(self):
        for name in ('global','regional','velocity','artist'):
            result=self.client.get(reverse(name))
            self.assertEqual(result.status_code,200)
            self.assertContains(result,'id="metrics"')

    @patch('analytics.views.queries.global_pulse',return_value={'metrics':[],'history':[],'top':[]})
    def test_global_api_filters(self,service):
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
        for route in ('global', 'regional', 'velocity', 'artist'):
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

    @patch('analytics.queries.rows', return_value=[{'code':'PH','name':'Philippines'}])
    def test_yearly_scope_not_on_velocity(self, mock_rows):
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
