"""Run the SQL in sql/ with DuckDB, straight against the Parquet file.

The same numbers are produced in pandas (src/analysis.py); tests/test_sql.py checks that the
two agree, so the SQL can be lifted into a warehouse (Snowflake, BigQuery, SQL Server) with
confidence.
"""
import duckdb
import pandas as pd

from . import config as cfg

QUERIES = sorted(p.stem for p in cfg.SQL_DIR.glob("*.sql"))


def connect(parquet=cfg.PROCESSED) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW companies AS SELECT * FROM read_parquet('{parquet.as_posix()}')")
    return con


def run(name: str, con=None) -> pd.DataFrame:
    con = con or connect()
    return con.execute((cfg.SQL_DIR / f"{name}.sql").read_text()).df()


def run_all() -> dict:
    con = connect()
    return {name: run(name, con) for name in QUERIES}
