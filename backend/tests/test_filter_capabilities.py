"""Filter availability contract tests. These tests do not query a live warehouse."""
from unittest.mock import patch
from django.test import SimpleTestCase
from analytics import queries


class FilterOptionsTests(SimpleTestCase):
    @patch('analytics.queries.rows', return_value=[{'code': 'PH', 'name': 'Philippines'}])
    def test_regional_scope_only_daily(self, mocked_rows):
        result = queries.filter_availability('regional')
        self.assertEqual([item['value'] for item in result['scopes']], ['daily'])
        self.assertEqual([item['code'] for item in result['countries']], ['PH'])

    @patch('analytics.queries.one', return_value={'ok': 1})
    def test_yearly_global_scope_requires_global_chart(self, mocked):
        result = queries.filter_availability('global', scope='yearly')
        self.assertEqual(result['countries'][0]['code'], 'GLOBAL')
        self.assertIn('yearly', [s['value'] for s in result['scopes']])

    @patch('analytics.queries.one', return_value={})
    def test_yearly_global_unavailable_when_no_chart(self, mocked):
        result = queries.filter_availability('global', scope='yearly')
        self.assertEqual(result['countries'], [])

    def test_unknown_dashboard(self):
        with self.assertRaises(ValueError):
            queries.filter_availability('missing')
