"""Load one cleaned Spotify DataFrame into its MySQL staging table.

Run only after creating spotify_analytics_stg using the staging DDL.
Each call atomically replaces one staging table's rows.
"""

from datetime import date, datetime
from pathlib import Path
import os
import math

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
SCHEMA = "spotify_analytics_stg"

# Whitelist DataFrame destinations. Never interpolate user-supplied table names.
TABLES = {
    "clean_songs_daily_365D": "clean_songs_daily_365D",
    "clean_artists_daily_365D": "clean_artists_daily_365D",
    "clean_albums_weekly_52W": "clean_albums_weekly_52W",
    "clean_artists": "clean_artists",
}


def _value(value):
    """Convert pandas missing values and scalars to MySQL-compatible types."""
    if value is None:
        return None
    if isinstance(value, (list, dict, tuple, set)):
        raise TypeError(f"Unsupported structured value: {type(value).__name__}")
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        return value.item()
    return value


def load_dataframe(df: pd.DataFrame, table: str, batch_size: int = 2000) -> int:
    """Transactionally replace one staging table with cleaned DataFrame rows."""
    if table not in TABLES:
        raise ValueError(f"Unknown staging table: {table}")
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if df.empty:
        raise ValueError("Refusing to clear a staging table with an empty DataFrame")
    if not df.columns.is_unique:
        raise ValueError("DataFrame has duplicate column names")
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    settings = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": SCHEMA,
        "connection_timeout": 15,
    }
    if not settings["user"]:
        raise ValueError("Set DB_USER in the project .env file")

    connection = mysql.connector.connect(**settings)
    cursor = connection.cursor()
    try:
        connection.start_transaction()
        # Compare against the actual MySQL staging DDL.
        cursor.execute(
            """SELECT COLUMN_NAME, IS_NULLABLE, COLUMN_DEFAULT, EXTRA
               FROM INFORMATION_SCHEMA.COLUMNS
               WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
               ORDER BY ORDINAL_POSITION""",
            (SCHEMA, TABLES[table]),
        )
        definitions = cursor.fetchall()
        if not definitions:
            raise ValueError(f"Table not found: {SCHEMA}.{table}")

        db_columns = [row[0] for row in definitions]
        unexpected = sorted(set(df.columns) - set(db_columns))
        required_missing = [
            name for name, nullable, default, extra in definitions
            if name not in df.columns and nullable == "NO"
            and default is None and "auto_increment" not in extra.lower()
        ]
        if unexpected or required_missing:
            raise ValueError(
                f"Schema mismatch for {table}. "
                f"Unexpected DataFrame columns: {unexpected}. "
                f"Missing required SQL columns: {required_missing}"
            )

        columns = [name for name in db_columns if name in df.columns]
        # Pandas nullable columns become SQL NULL. MySQL enforces data constraints.
        if table == "clean_artists" and df["artist_uri"].duplicated().any():
            raise ValueError("Duplicate artist_uri values violate staging primary key")

        quoted_columns = ", ".join(f"`{col}`" for col in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_sql = (
            f"INSERT INTO `{SCHEMA}`.`{TABLES[table]}` "
            f"({quoted_columns}) VALUES ({placeholders})"
        )
        # DELETE is transactional in InnoDB. A failed insert rolls back the deletion.
        cursor.execute(f"DELETE FROM `{SCHEMA}`.`{TABLES[table]}`")

        count = 0
        view = df.loc[:, columns]
        for start in range(0, len(view), batch_size):
            batch = view.iloc[start:start + batch_size]
            rows = [tuple(_value(value) for value in row)
                    for row in batch.itertuples(index=False, name=None)]
            cursor.executemany(insert_sql, rows)
            count += len(rows)

        cursor.execute(f"SELECT COUNT(*) FROM `{SCHEMA}`.`{TABLES[table]}`")
        actual = cursor.fetchone()[0]
        if actual != count:
            raise RuntimeError(f"Row count mismatch: loaded {count}; table has {actual}")
        connection.commit()
        print(f"Loaded {count:,} rows into {SCHEMA}.{table}")
        return count
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
