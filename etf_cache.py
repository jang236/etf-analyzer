"""SQLite 기반 ETF 데이터 캐시.

테이블:
- kv_cache: 범용 TTL 캐시 (detail/list/holdings/returns)
- etf_master: 정적/준정적 정보 (Phase 3+ 활용)
- etf_eod: 일단위 시세 (Phase 3+ 활용)
- etf_holdings: 주간 구성종목 스냅샷 (Phase 3+ 활용)
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional, Dict

DB_PATH = os.environ.get("ETF_DB_PATH", "etf_cache.db")

# ─────────────────────────────────────────────
# TTL 정책 (초 단위)
# ─────────────────────────────────────────────
TTL_DETAIL = 3600          # 1시간: ETF 상세 (시세 변동)
TTL_LIST = 3600            # 1시간: ETF 리스트
TTL_HOLDINGS = 86400       # 24시간: 구성종목 (일 단위 변동)
TTL_RETURNS = 3600         # 1시간: 기간 수익률
TTL_HISTORY = 3600         # 1시간: 과거 가격

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv_cache (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    cached_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kv_cached_at ON kv_cache(cached_at);

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
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS etf_holdings (
    etf_code TEXT,
    stock_code TEXT,
    stock_name TEXT,
    weight_pct REAL,
    snapshot_date DATE,
    PRIMARY KEY (etf_code, stock_code, snapshot_date)
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
    """DB 초기화 — 앱 startup에서 호출."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


# ─────────────────────────────────────────────
# KV 캐시 API
# ─────────────────────────────────────────────
def get_cached(key: str, ttl_seconds: int) -> Optional[Dict]:
    """TTL 내의 캐시된 값을 반환. 만료되면 None."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT payload, cached_at FROM kv_cache WHERE cache_key = ?",
                (key,)
            ).fetchone()
        if not row:
            return None
        if time.time() - row["cached_at"] > ttl_seconds:
            return None
        return json.loads(row["payload"])
    except (sqlite3.Error, json.JSONDecodeError):
        return None


def set_cached(key: str, data: Dict) -> None:
    """캐시 upsert. 저장 실패는 조용히 무시 (서비스 기능엔 영향 없음)."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv_cache (cache_key, payload, cached_at) VALUES (?, ?, ?)",
                (key, json.dumps(data, ensure_ascii=False), time.time())
            )
            conn.commit()
    except (sqlite3.Error, TypeError):
        pass


def clear_cache(prefix: str = "") -> int:
    """prefix로 시작하는 캐시 키 삭제. 빈 prefix면 전체 삭제. 반환: 삭제된 레코드 수."""
    try:
        with get_conn() as conn:
            if prefix:
                cur = conn.execute(
                    "DELETE FROM kv_cache WHERE cache_key LIKE ?",
                    (f"{prefix}%",)
                )
            else:
                cur = conn.execute("DELETE FROM kv_cache")
            conn.commit()
            return cur.rowcount
    except sqlite3.Error:
        return 0


def cache_stats() -> Dict:
    """캐시 통계 (관리/디버깅용)."""
    try:
        with get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM kv_cache").fetchone()["n"]
            oldest = conn.execute(
                "SELECT MIN(cached_at) AS t FROM kv_cache"
            ).fetchone()["t"]
            newest = conn.execute(
                "SELECT MAX(cached_at) AS t FROM kv_cache"
            ).fetchone()["t"]
            return {
                "total_entries": total,
                "oldest_timestamp": oldest,
                "newest_timestamp": newest,
            }
    except sqlite3.Error:
        return {"total_entries": 0}


if __name__ == "__main__":
    init_db()
    print(f"DB initialized at {DB_PATH}")
