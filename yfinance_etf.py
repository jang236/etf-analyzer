"""해외 ETF 데이터 수집 (yfinance).

yfinance는 Yahoo Finance의 비공식 래퍼. 개인/베타 규모에 안정적.
대규모 공개 시 FMP 등 공식 API 추가 고려.
"""
import yfinance as yf
from typing import Dict, List
from datetime import datetime


def _safe_pct(raw, already_percent: bool = False) -> float:
    """수익률 값을 percent 단위로 표준화.

    yfinance는 필드마다 percent/decimal이 혼재되어 있어 명시적 지정 필요.
    """
    if raw is None:
        return 0.0
    try:
        v = float(raw)
    except (ValueError, TypeError):
        return 0.0
    return round(v if already_percent else v * 100, 3)


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
            # yfinance netExpenseRatio: already in percent form (e.g. 0.0945 = 0.09%)
            "expense_ratio_pct": info.get("netExpenseRatio"),
            # yield: decimal (0.0114 = 1.14%)
            "dividend_yield_pct": _safe_pct(info.get("yield"), already_percent=False),
            "aum_usd": info.get("totalAssets"),
            "category": info.get("category"),
            "fund_family": info.get("fundFamily"),
            "inception_date": info.get("fundInceptionDate"),
            "summary_en": (info.get("longBusinessSummary") or "")[:800],
            # ytdReturn: already in percent form (empirically)
            "ytd_return_pct": _safe_pct(info.get("ytdReturn"), already_percent=True),
            # threeYearAverageReturn: decimal form
            "three_year_avg_return_pct": _safe_pct(
                info.get("threeYearAverageReturn"), already_percent=False
            ),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "beta_3y": info.get("beta3Year"),
            "nav_price": info.get("navPrice"),
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
            weight_pct = round(float(weight) * 100, 3) if weight is not None else None
            out.append({
                "symbol": stock_symbol,
                "name": row.get("Name"),
                "weight_pct": weight_pct,
            })
        return out
    except Exception:
        return []


def get_yf_etf_history(symbol: str, period: str = "1y") -> List[Dict]:
    """해외 ETF 과거 가격."""
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


def get_yf_etf_returns(symbol: str) -> Dict:
    """주요 기간 수익률 계산 (from historical prices)."""
    try:
        t = yf.Ticker(symbol)
        # 5년치 가져와서 여러 구간 계산
        hist = t.history(period="5y")
        if hist.empty or len(hist) < 2:
            return {}
        closes = hist["Close"]
        latest = float(closes.iloc[-1])
        result = {"latest_close": round(latest, 2)}
        periods = {
            "1m_pct": 21,
            "3m_pct": 63,
            "6m_pct": 126,
            "1y_pct": 252,
            "3y_pct": 756,
            "5y_pct": 1260,
        }
        for label, days in periods.items():
            if len(closes) > days:
                past = float(closes.iloc[-days])
                if past > 0:
                    result[label] = round((latest / past - 1) * 100, 2)
        return result
    except Exception:
        return {}


def batch_download_prices(symbols: List[str], period: str = "1d") -> Dict:
    """여러 해외 ETF 가격 일괄 다운로드."""
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
