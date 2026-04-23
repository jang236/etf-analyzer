"""해외 ETF 데이터 수집 (yfinance).

yfinance는 Yahoo Finance의 비공식 래퍼. 공개 범위가 베타 규모인 동안
충분히 안정적. 대규모 공개 시 FMP 등 공식 API 추가 고려.
"""
import yfinance as yf
from typing import Dict, List
from datetime import datetime


def get_yf_etf_info(symbol: str) -> Dict:
    """단일 해외 ETF 기본 정보."""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        return {
            "symbol": symbol,
            "source": "yfinance",
            "name": info.get("longName") or info.get("shortName"),
            "price": info.get("regularMarketPrice") or info.get("previousClose"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "expense_ratio_pct": info.get("netExpenseRatio"),  # 이미 percent 단위
            "dividend_yield_pct": round((info.get("yield") or 0) * 100, 3),
            "aum_usd": info.get("totalAssets"),
            "category": info.get("category"),
            "fund_family": info.get("fundFamily"),
            "inception_date": info.get("fundInceptionDate"),
            "summary_en": (info.get("longBusinessSummary") or "")[:800],
            "ytd_return_pct": round((info.get("ytdReturn") or 0) * 100, 2),
            "three_year_avg_return_pct": round((info.get("threeYearAverageReturn") or 0) * 100, 2),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "source": "yfinance",
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        }


def get_yf_etf_holdings(symbol: str, top_n: int = 10) -> List[Dict]:
    """해외 ETF 구성종목 TOP N."""
    try:
        t = yf.Ticker(symbol)
        fd = t.get_funds_data()
        df = fd.top_holdings
        if df is None or df.empty:
            return []
        out = []
        for stock_symbol, row in df.head(top_n).iterrows():
            weight = row.get("Holding Percent")
            if weight is not None:
                weight = round(float(weight) * 100, 3)
            out.append({
                "symbol": stock_symbol,
                "name": row.get("Name"),
                "weight_pct": weight,
            })
        return out
    except Exception as e:
        return []


def get_yf_etf_history(symbol: str, period: str = "1y") -> List[Dict]:
    """해외 ETF 과거 가격 (수익률 계산용).

    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    """
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist.empty:
            return []
        return [
            {"date": idx.strftime("%Y-%m-%d"),
             "close": round(float(row["Close"]), 4),
             "volume": int(row["Volume"])}
            for idx, row in hist.iterrows()
        ]
    except Exception:
        return []


def get_yf_etf_dividends(symbol: str) -> List[Dict]:
    """해외 ETF 분배금 이력."""
    try:
        t = yf.Ticker(symbol)
        div = t.dividends
        if div.empty:
            return []
        return [
            {"date": idx.strftime("%Y-%m-%d"), "amount": float(amt)}
            for idx, amt in div.items()
        ]
    except Exception:
        return []


def batch_download_prices(symbols: List[str], period: str = "1d") -> Dict:
    """여러 해외 ETF 가격 일괄 다운로드 (EOD 배치용)."""
    try:
        data = yf.download(
            " ".join(symbols),
            period=period,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        return {"status": "ok", "symbols_count": len(symbols)}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}
