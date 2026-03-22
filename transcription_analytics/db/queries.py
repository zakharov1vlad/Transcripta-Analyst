import pandas as pd
from sqlalchemy import text
from db.connection import get_engine

def fetch_df(sql: str, params: dict = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

def fetch_one(sql: str, params: dict = None):
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        row = result.fetchone()
        return row[0] if row else None
