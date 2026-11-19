"""The one-time baseline must never overwrite an existing warehouse."""
import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'deploy' / 'bootstrap_warehouse.py'
SPEC = importlib.util.spec_from_file_location('warehouse_bootstrap', SCRIPT)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class BootstrapGuardTests(TestCase):
    def run_existing_schema(self, selected_schema, table_count):
        environment = {'BOOTSTRAP_DB_HOST': '127.0.0.1',
                       'BOOTSTRAP_DB_USER': 'inert_bootstrap',
                       'BOOTSTRAP_DB_PASSWORD': 'inert'}
        with patch.dict('os.environ', environment, clear=True), \
             patch('sys.argv', ['bootstrap', '--confirm-empty-schema', bootstrap.SCHEMA]), \
             patch.object(bootstrap.pymysql, 'connect') as connect:
            cursor = connect.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = [(selected_schema,), (table_count,)]
            with self.assertRaises(SystemExit):
                bootstrap.main()
            statements = [call.args[0] for call in cursor.execute.call_args_list]
            self.assertTrue(all(statement.startswith('SELECT ') for statement in statements))
            connect.return_value.close.assert_called_once()

    def test_existing_warehouse_is_never_modified(self):
        self.run_existing_schema(bootstrap.SCHEMA, 1)

    def test_wrong_selected_database_is_never_modified(self):
        self.run_existing_schema('another_project', 0)
