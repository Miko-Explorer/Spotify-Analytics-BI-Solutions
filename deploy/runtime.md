# YFitOps Analytics runtime

Repository: `Miko-Explorer/Spotify-Analytics-BI-Solutions`. Domains:
`yfitopsanalytics.shop` and `www.yfitopsanalytics.shop`. Shared MySQL schema:
`2026_3dsa_2_spotifyanalytics`. Other project schemas are outside scope.

Install `backend/requirements-production.txt` with CPython 3.14.4 on Linux x86_64,
matching the existing EC2 interpreter. All production dependencies are pinned;
the combined root requirements include notebooks and are not the release input.
Use the host's existing private environment file, loaded by the service outside
the immutable release. No secrets, data, environments or venvs go in Git/artifacts.

Required environment: `DJANGO_SECRET_KEY` (persistent private random key),
`DJANGO_DEBUG=false`,
`DJANGO_ALLOWED_HOSTS=yfitopsanalytics.shop,www.yfitopsanalytics.shop,127.0.0.1,localhost`,
`DW_DB_HOST`, `DW_DB_PORT=3306`, `DW_DB_NAME=2026_3dsa_2_spotifyanalytics`,
`DW_EXPECTED_SCHEMA=2026_3dsa_2_spotifyanalytics`, `DW_DB_USER`, `DW_DB_PASSWORD`.
For remote MySQL set `DW_DB_SSL_CA` to the private trusted CA file path: certificate
and hostname verification are both enabled when configured. Never disable either.
Runtime credentials need SELECT only on this schema; no ETL/schema-changing grants.
Legacy `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` remain supported fallbacks.

From the release root:

```sh
python3 -m pip install --requirement backend/requirements-production.txt
python3 backend/manage.py check
python3 backend/manage.py collectstatic --noinput
python3 -m gunicorn --chdir backend config.wsgi:application --bind 127.0.0.1:8134 --workers 2 --threads 2 --timeout 120 --access-logfile - --error-logfile -
```

Port 8134 is a proposed project-only loopback port; host setup must first confirm
it is unused. Serve `/static/` from the selected release's `backend/staticfiles/`
or set `DJANGO_STATIC_ROOT` explicitly. Nginx terminates HTTPS and must overwrite
`X-Forwarded-Proto` from its own `$scheme`; Gunicorn must remain loopback-only.
Enable `DJANGO_HSTS_SECONDS` only after the public TLS names are verified.
Health: `GET /health/` must return HTTP 200 and `status=ok`. It asserts selected
schema and SELECT access to all required columns using zero-row queries. It does
not require chart data or reveal credentials. Any schema/query failure returns 503.
An empty initialized warehouse is healthy and charts show no matching observations.

## One-time empty warehouse baseline

The original `etl/sql/spotify_analytics_dw_ddl.sql` is destructive and uses a
different database. The original staging, bridge loader and refresh scripts also
select/reference other schemas. They are research inputs, never deployment SQL.
Do not execute them against production or include them in automatic migrations.

`deploy/bootstrap/warehouse.sql` contains only 23 additive CREATE TABLE statements
including the optional album-artist bridge. It does not select/create/drop a
database or insert fabricated/reference/chart data. `bootstrap_warehouse.py`
requires the existing exact schema to be completely empty and refuses a rerun.
Have the operator independently review the exact SQL digest, verify restricted
schema grants and TLS, and save a verified private backup before applying it once.
Use a separate bootstrap identity, never the runtime account or shared admin:

```sh
# Private environment: BOOTSTRAP_DB_HOST, BOOTSTRAP_DB_PORT, BOOTSTRAP_DB_USER,
# BOOTSTRAP_DB_PASSWORD, BOOTSTRAP_DB_SSL_CA (required for remote hosts).
python3 deploy/bootstrap_warehouse.py --confirm-empty-schema 2026_3dsa_2_spotifyanalytics
```

MySQL DDL is not transactionally reversible. Failure can leave a partial baseline;
stop, inspect privately and reconcile before retrying. Existing populated schemas
must be compared to `analytics/warehouse_contract.py` and repaired using separately
reviewed additive migrations, never by invoking bootstrap or destructive reloads.
No Django model/migration owns these tables. An automatic future migration stage
must use a separate reviewed SQL path, restricted identity, approved digests,
private backup and durable pending/applied ledger; app-only releases skip SQL.

## Data availability

The repository intentionally omits `charts_songs_daily_365D.csv`,
`charts_artists_daily_365D.csv`, `charts_albums_weekly_52W.csv`, and `artists.csv`.
See `data/raw/README.md`. Bootstrap creates empty structures only. Analytics become
populated after a separately authorized, schema-scoped real-data ETL/import; the
legacy cross-schema ETL requires adaptation and must not run on a deployment.

## Verification boundaries

Local route/KPI/health tests use mocks and inert configuration without a database.
CI must also install the locked wheels and start Gunicorn on matching Linux Python.
Production checks must verify the actual selected schema, empty/populated API
responses and public HTTPS routing after activation. A healthy empty schema proves
structure and access, not that the absent datasets have been loaded.
