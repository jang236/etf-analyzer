"""SQLite 기반 ETF 데이터 캐시.

Phase 2 이후 본격 활용. 스키마만 먼저 정의.

테이블:
- etf_master: 정적/준정적 정보 (자주 안 변함)
- etf_eod: 일단위 시세
- etf_holdings: 주간 구성종목 스냅샷
"""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("ETF_DB_PATH", "etf_cache.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_master (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('KR', 'US')),
    category TEXT,
    expense_ratio_pct REAL,
    underlying_index TEXT,
    asset_manager TEXT,
    inception_date TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_etf_master_market ON etf_master(market);
CREATE INDEX IF NOT EXISTS idx_etf_master_category ON etf_master(category);

CREATE TABLE IF NOT EXISTS etf_eod (
    code TEXT,
    date DATE,
    close_price REAL,
    nav REAL,
    volume INTEGER,
    aum REAL,
    return_1m_pct REAL,
    return_3m_pct REAL,
    return_1y_pct REAL,
    PRIMARY KEY (code, date),
    FOREIGN KEY (code) REFERENCES etf_master(code)
);

CREATE TABLE IF NOT EXISTS etf_holdings (
    etf_code TEXT,
    stock_code TEXT,
    stock_name TEXT,
    weight_pct REAL,
    snapshot_date DATE,
    PRIMARY KEY (etf_code, stock_code, snapshot_date),
    FOREIGN KEY (etf_code) REFERENCES etf_master(code)
);

CREATE INDEX IF NOT EXISTS idx_holdings_snapshot ON etf_holdings(snapshot_date);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """DB 초기화 (최초 1회)."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"✅ DB initialized at {DB_PATH}")
