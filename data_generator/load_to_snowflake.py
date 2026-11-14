"""
Load the generated CSV files from data/raw/ into Snowflake (MARKETING_DB.RAW).

Uses the same login as dbt: the environment variables SNOWFLAKE_ACCOUNT,
SNOWFLAKE_USER and SNOWFLAKE_PRIVATE_KEY_PATH, plus the TRANSFORMER role.

Every column is loaded as text (VARCHAR), exactly as it appears in the CSV.
RAW keeps the data as it arrived; dbt's staging models cast and clean it.

Run from the project root, with .venv activated:
    python data_generator/load_to_snowflake.py
"""

import csv
import os
import sys
from pathlib import Path

import snowflake.connector

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

TABLES = ["campaigns", "ad_spend", "customers", "web_sessions", "events", "orders"]

DATABASE = "MARKETING_DB"
SCHEMA = "RAW"
ROLE = "TRANSFORMER"
WAREHOUSE = "TRANSFORM_WH"

REQUIRED_ENV_VARS = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_PATH"]


def connect() -> snowflake.connector.SnowflakeConnection:
    """Log in to Snowflake with key-pair authentication (no password)."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}. "
                 "Open a new terminal after running setx.")

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT",                       # = key-pair login
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role=ROLE,
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
    )


def csv_info(path: Path) -> tuple[list[str], int]:
    """Return the CSV's column names (from the header row) and its number of data rows."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        n_rows = sum(1 for _ in reader)
    return header, n_rows


def main() -> None:
    files = {name: DATA_DIR / f"{name}.csv" for name in TABLES}
    not_found = [str(p) for p in files.values() if not p.exists()]
    if not_found:
        sys.exit("CSV files not found. Run data_generator/generate_data.py first.\n"
                 + "\n".join(not_found))

    conn = connect()
    cur = conn.cursor()
    print(f"Connected to {os.environ['SNOWFLAKE_ACCOUNT']} as {ROLE}. Loading into {DATABASE}.{SCHEMA}:")

    try:
        # A file format tells Snowflake how to read our CSVs.
        #   SKIP_HEADER = 1            -> the first line holds column names, not data
        #   FIELD_OPTIONALLY_ENCLOSED  -> values may be wrapped in "double quotes"
        #   EMPTY_FIELD_AS_NULL        -> an empty cell becomes NULL
        #   TRIM_SPACE = FALSE         -> keep spaces around values (part of the mess!)
        cur.execute("""
            CREATE OR REPLACE FILE FORMAT CSV_FORMAT
              TYPE = CSV
              SKIP_HEADER = 1
              FIELD_OPTIONALLY_ENCLOSED_BY = '"'
              EMPTY_FIELD_AS_NULL = TRUE
              TRIM_SPACE = FALSE
        """)

        # A stage is a temporary upload area inside Snowflake.
        cur.execute("CREATE STAGE IF NOT EXISTS CSV_STAGE FILE_FORMAT = CSV_FORMAT")

        for name, path in files.items():
            columns, csv_rows = csv_info(path)
            table = name.upper()

            # 1. (Re)create the table: every CSV column as VARCHAR, plus _LOADED_AT,
            #    the time the row arrived (dbt's freshness checks will use it).
            column_defs = ",\n  ".join(f"{col.upper()} VARCHAR" for col in columns)
            cur.execute(f"""
                CREATE OR REPLACE TABLE {table} (
                  {column_defs},
                  _LOADED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
                )
            """)

            # 2. Upload the file to the stage (Snowflake compresses it to .csv.gz).
            file_url = "file://" + path.as_posix()
            cur.execute(f"PUT '{file_url}' @CSV_STAGE OVERWRITE = TRUE AUTO_COMPRESS = TRUE")

            # 3. Copy the staged file into the table, then delete it from the stage (PURGE).
            #    ON_ERROR = ABORT_STATEMENT -> if any row fails, load nothing.
            column_list = ", ".join(col.upper() for col in columns)
            cur.execute(f"""
                COPY INTO {table} ({column_list})
                FROM @CSV_STAGE/{path.name}.gz
                FILE_FORMAT = (FORMAT_NAME = CSV_FORMAT)
                ON_ERROR = ABORT_STATEMENT
                PURGE = TRUE
                FORCE = TRUE
            """)

            # 4. Compare row counts: Snowflake table vs CSV file.
            loaded_rows = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            status = "OK" if loaded_rows == csv_rows else "MISMATCH"
            print(f"  {table:<13} {loaded_rows:>8,} rows loaded (CSV: {csv_rows:>8,})  {status}")
    finally:
        cur.close()
        conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
