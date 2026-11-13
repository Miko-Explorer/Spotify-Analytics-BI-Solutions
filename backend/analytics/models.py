"""The warehouse is managed by ETL SQL, not Django migrations.

API reads use parameterized queries in analytics/queries.py. No ORM table
creation, modification, or migrations are needed for these existing tables.
"""
