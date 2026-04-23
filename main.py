"""
etf-analyzer — 한국/해외 ETF 분석 & 포트폴리오 추천 MCP 서비스

보안 강화 (Day 1 적용):
- OpenAPI/docs 비공개화
- CORS 화이트리스트
- 레이트리밋 300/min
- X-API-Key 인증 미들웨어
"""
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from auth import verify_api_key
from router import pick_source, detect_market_from_query
from naver_etf import get_naver_etf_list, get_naver_etf_detail
from yfinance_etf import get_yf_etf_info, get_yf_etf_holdings

KST = timezone(timedelta(hours=9))

# FastAPI 앱 생성 (스키마 전면 비공개)
app = FastAPI(
    title="etf-analyzer",
    description="한국/해외 ETF 분석 & 포트폴리오 추천 서비스",
    version="0.1.0",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)

# CORS 화이트리스트
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat.openai.com",
        "https://chatgpt.com",
        "https://claude.ai",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 레이트리밋
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."},
    )


app.add_middleware(SlowAPIMiddleware)


# ───────────────────────────────────────────────
# Public endpoints (인증 불필요)
# ───────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "etf-analyzer",
        "version": "0.1.0",
        "status": "ready",
        "message": "한국/해외 ETF 분석 및 포트폴리오 추천 서비스",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(KST).isoformat(),
        "components": {
            "naver": "ready",
            "yfinance": "ready",
            "portfolio_engine": "stub",
        },
    }


# ───────────────────────────────────────────────
# Protected endpoints (X-API-Key 헤더 필수)
# ───────────────────────────────────────────────
@app.get("/v1/etfs/{code}", dependencies=[Depends(verify_api_key)])
def get_etf(code: str):
    """단일 ETF 상세 정보. 코드/심볼로 자동 라우팅 (네이버 or yfinance)."""
    source = pick_source(code)
    try:
        if source == "naver":
            data = get_naver_etf_detail(code)
        else:
            data = get_yf_etf_info(code)
        return {"source": source, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data fetch failed: {type(e).__name__}")


@app.get("/v1/etfs", dependencies=[Depends(verify_api_key)])
def list_etfs(
    market: Optional[str] = Query(None, description="KR, US, or None for both"),
    category: Optional[int] = Query(None, description="Naver category 0~7 (KR only)"),
    min_aum: Optional[float] = Query(None, description="최소 순자산 (한국 억원 / 해외 백만달러)"),
):
    """ETF 리스트 조회 (필터링 지원)."""
    market = (market or "").upper()
    results = {"market": market or "BOTH"}
    if market in ("KR", ""):
        kr_items = get_naver_etf_list(category or 0)
        if min_aum is not None:
            kr_items = [x for x in kr_items if (x.get("marketSum") or 0) >= min_aum]
        results["kr"] = {"count": len(kr_items), "items": kr_items[:50]}
    if market in ("US", ""):
        # Phase 1: 큐레이션 리스트 기반
        from curated_us_etfs import CURATED_US_ETFS
        results["us"] = {"count": len(CURATED_US_ETFS), "items": CURATED_US_ETFS[:50]}
    return results


@app.get("/v1/etfs/{code}/holdings", dependencies=[Depends(verify_api_key)])
def get_etf_holdings(code: str, top_n: int = 10):
    """ETF 구성종목 TOP N."""
    source = pick_source(code)
    if source == "naver":
        # TODO Phase 2: 네이버 coinfo 파싱
        return {"source": "naver", "status": "not_implemented", "code": code}
    else:
        holdings = get_yf_etf_holdings(code, top_n=top_n)
        return {"source": "yfinance", "code": code, "holdings": holdings}


# TODO Phase 2: /v1/etfs/compare?codes=...
# TODO Phase 3: /v1/portfolio/recommend (POST with risk/amount/horizon)
