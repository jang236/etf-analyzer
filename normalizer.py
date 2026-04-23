"""네이버 / yfinance 응답을 공통 스키마로 변환.

공통 ETF 스키마:
{
    "code": str,
    "name": str,
    "market": "KR" | "US",
    "price": float,
    "currency": "KRW" | "USD" | ...,
    "change_pct": float,
    "volume": int,
    "aum": float,            # KR: 억원, US: USD
    "expense_ratio_pct": float,
    "dividend_yield_pct": float,
    "category": str,
    "source": "naver" | "yfinance",
}
"""
from typing import Dict


def normalize_etf(raw: Dict, source: str) -> Dict:
    if source == "naver":
        return _from_naver(raw)
    if source == "yfinance":
        return _from_yfinance(raw)
    return raw


def _from_naver(raw: Dict) -> Dict:
    return {
        "code": raw.get("itemcode") or raw.get("code"),
        "name": raw.get("itemname") or raw.get("name"),
        "market": "KR",
        "price": raw.get("nowVal") or raw.get("price"),
        "currency": "KRW",
        "change_pct": raw.get("changeRate"),
        "volume": raw.get("quant"),
        "trading_value_100m_krw": raw.get("amonut"),
        "aum_100m_krw": raw.get("marketSum"),
        "nav": raw.get("nav"),
        "return_3m_pct": raw.get("threeMonthEarnRate"),
        "source": "naver",
    }


def _from_yfinance(raw: Dict) -> Dict:
    return {
        "code": raw.get("symbol"),
        "name": raw.get("name"),
        "market": "US",
        "price": raw.get("price"),
        "currency": raw.get("currency", "USD"),
        "expense_ratio_pct": raw.get("expense_ratio_pct"),
        "dividend_yield_pct": raw.get("dividend_yield_pct"),
        "aum_usd": raw.get("aum_usd"),
        "category": raw.get("category"),
        "fund_family": raw.get("fund_family"),
        "inception_date": raw.get("inception_date"),
        "summary_en": raw.get("summary_en"),
        "ytd_return_pct": raw.get("ytd_return_pct"),
        "fifty_two_week_high": raw.get("fifty_two_week_high"),
        "fifty_two_week_low": raw.get("fifty_two_week_low"),
        "source": "yfinance",
    }
