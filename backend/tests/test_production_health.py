"""Health checks must reject wrong schemas and tolerate a genuine empty warehouse."""
from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings

from analytics.warehouse_contract import REQUIRED_COLUMNS


@override_settings(DW_EXPECTED_SCHEMA='2026_3dsa_2_spotifyanalytics')
class ProductionHealthTests(SimpleTestCase):
    @patch('analytics.views.connection')
    def test_verifies_empty_tables_without_row_counts(self, connection):
        cursor = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.return_value = ('2026_3dsa_2_spotifyanalytics',)
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tables_verified'], len(REQUIRED_COLUMNS))
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(statements[0], 'SELECT DATABASE()')
        self.assertEqual(len(statements), 1 + len(REQUIRED_COLUMNS))
        self.assertTrue(all('WHERE 1=0' in sql for sql in statements[1:]))

    @patch('analytics.views.connection')
    def test_wrong_database_fails_before_table_queries(self, connection):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('another_project',)
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'schema_mismatch')
        cursor.execute.assert_called_once_with('SELECT DATABASE()')

    @patch('analytics.views.connection')
    def test_missing_schema_objects_or_connection_fail_closed(self, connection):
        connection.cursor.side_effect = DatabaseError('private connection details')
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private', response.content.decode())
