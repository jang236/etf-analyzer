"""stock-final API 클라이언트.

기존 프로젝트(https://stock-final.replit.app)의 재무분석 API를 래핑.
ETF 구성종목(개별 주식) drill-down 용도.

장애 처리: 응답 지연/실패 시 stub 반환 (etf-analyzer가 죽지 않음).
"""
import os
import requests
from typing import Dict, Optional

STOCK_FINAL_BASE = os.environ.get(
    "STOCK_FINAL_BASE", "https://stock-final.replit.app"
)
TIMEOUT = 8  # stock-final이 느릴 수 있어 여유있게


def get_stock_analysis(name_or_code: str) -> Dict:
    """개별 종목의 주가·재무·뉴스 통합 분석 요청.

    Uses stock-final's /analyze-company endpoint.
    """
    url = f"{STOCK_FINAL_BASE}/analyze-company"
    try:
        resp = requests.get(
            url,
            params={"company_name": name_or_code},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return {"status": "ok", "data": resp.json()}
        return {
            "status": "error",
            "http_status": resp.status_code,
            "message": "stock-final API 응답 오류",
        }
    except requests.Timeout:
        return {
            "status": "timeout",
            "message": f"stock-final 응답 지연 ({TIMEOUT}s 초과)",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"{type(e).__name__}: {str(e)[:120]}",
        }


def get_stock_price_only(name_or_code: str) -> Dict:
    """가벼운 가격만 조회 (/stock/{name})."""
    url = f"{STOCK_FINAL_BASE}/stock/{name_or_code}"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            return {"status": "ok", "data": resp.json()}
        return {"status": "error", "http_status": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)[:120]}


def is_available() -> bool:
    """stock-final 서버 가용성 체크."""
    try:
        resp = requests.get(f"{STOCK_FINAL_BASE}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
