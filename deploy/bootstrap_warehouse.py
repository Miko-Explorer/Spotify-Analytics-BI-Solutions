"""One-time additive baseline for the existing, empty project schema only.

Use a schema-restricted bootstrap identity, after reviewing warehouse.sql and
backing up this exact schema. Never call from ordinary application startup.
"""
import argparse
import os
from pathlib import Path
import sys

import pymysql

SCHEMA = '2026_3dsa_2_spotifyanalytics'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-empty-schema', required=True, choices=[SCHEMA])
    parser.parse_args()
    options = dict(host=os.environ['BOOTSTRAP_DB_HOST'],
                   port=int(os.getenv('BOOTSTRAP_DB_PORT', '3306')),
                   user=os.environ['BOOTSTRAP_DB_USER'],
                   password=os.environ['BOOTSTRAP_DB_PASSWORD'],
                   database=SCHEMA, charset='utf8mb4', connect_timeout=8,
                   read_timeout=60, write_timeout=30, local_infile=False)
    ca = os.getenv('BOOTSTRAP_DB_SSL_CA')
    if ca:
        options.update(ssl_ca=ca, ssl_verify_cert=True, ssl_verify_identity=True)
    elif options['host'] not in ('localhost', '127.0.0.1', '::1'):
        raise SystemExit('A verified BOOTSTRAP_DB_SSL_CA is required for remote MySQL.')
    sql_path = Path(__file__).resolve().parent / 'bootstrap' / 'warehouse.sql'
    # This format deliberately allows CREATE TABLE statements only.
    sql = '\n'.join(line for line in sql_path.read_text().splitlines()
                    if not line.lstrip().startswith('--'))
    statements = [statement.strip() for statement in sql.split(';') if statement.strip()]
    if not statements or any(not statement.startswith('CREATE TABLE ') for statement in statements):
        raise SystemExit('Bootstrap accepts only the reviewed CREATE TABLE baseline.')
    connection = pymysql.connect(**options)
    started = False
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE()')
            if cursor.fetchone()[0] != SCHEMA:
                raise SystemExit('Unexpected selected schema.')
            cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s', (SCHEMA,))
            if cursor.fetchone()[0]:
                raise SystemExit('Schema is not empty; bootstrap refuses to modify existing objects.')
            for statement in statements:
                started = True
                cursor.execute(statement)
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
            from analytics.warehouse_contract import REQUIRED_COLUMNS
            for table, columns in REQUIRED_COLUMNS.items():
                projection = ', '.join(f'`{column}`' for column in columns)
                cursor.execute(f'SELECT {projection} FROM `{table}` WHERE 1=0')
        print(f'Created and verified {len(REQUIRED_COLUMNS)} empty tables in {SCHEMA}. No data imported.')
    except Exception:
        if started:
            print('DDL may be partially applied. Stop and reconcile privately; do not automatically retry.', file=sys.stderr)
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    main()
