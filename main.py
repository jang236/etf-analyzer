"""
etf-analyzer — 한국/해외 ETF 분석 & 포트폴리오 추천 MCP 서비스

보안 강화 (Day 1 적용):
- OpenAPI/docs 비공개화
- CORS 화이트리스트
- 레이트리밋 300/min
- X-API-Key 인증 미들웨어
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

from fastapi import FastAPI, Depends, HTTPException, Query, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("etf-analyzer")
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from pydantic import BaseModel

from auth import verify_api_key
from router import pick_source, detect_market_from_query
from naver_etf import get_naver_etf_list, get_naver_etf_detail, get_naver_etf_holdings_full
from yfinance_etf import (
    get_yf_etf_info, get_yf_etf_holdings,
    get_yf_etf_returns, get_yf_etf_history, get_yf_etf_dividends,
)
from etf_cache import (
    init_db, get_cached, set_cached, clear_cache, cache_stats,
    TTL_DETAIL, TTL_LIST, TTL_HOLDINGS, TTL_RETURNS,
)
from portfolio_engine import recommend as portfolio_recommend
from llm_narrative import explain_etf, explain_comparison, explain_portfolio, is_available as llm_available
from stock_final_client import get_stock_analysis, is_available as stock_final_available

# MCP 서버 (optional — 실패해도 앱은 동작)
_MCP_AVAILABLE = False
_mcp_server = None
try:
    from mcp_server import mcp as _mcp_server
    _MCP_AVAILABLE = True
    logger.info("MCP server module loaded")
except Exception as e:
    logger.warning(f"MCP server unavailable: {type(e).__name__}: {e}")

KST = timezone(timedelta(hours=9))


# ─────────────────────────────────────────────
# Lifespan (FastAPI 신식) — on_event("startup") 대체
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("DB initialized")
    except Exception as e:
        logger.error(f"DB init failed: {e}")
    yield


# FastAPI 앱
app = FastAPI(
    title="etf-analyzer",
    description="한국/해외 ETF 분석 & 포트폴리오 추천 서비스",
    version="0.5.1",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
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


# ─────────────────────────────────────────────
# MCP 경로 인증 미들웨어
# (FastAPI dependencies는 Starlette mount 하위엔 적용 안 됨)
# ─────────────────────────────────────────────
@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/mcp"):
        expected_key = os.environ.get("ETF_API_KEY")
        if expected_key:
            provided = request.headers.get("x-api-key")
            if provided != expected_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or missing X-API-Key for MCP endpoint"},
                )
    return await call_next(request)


# ─────────────────────────────────────────────
# 캐시 헬퍼
# ─────────────────────────────────────────────
def _cached_fetch(key: str, ttl: int, fetcher):
    """캐시 조회 → 미스 시 fetcher() 실행 + 저장."""
    cached = get_cached(key, ttl)
    if cached is not None:
        cached["_cache"] = "hit"
        return cached
    data = fetcher()
    if isinstance(data, dict):
        data["_cache"] = "miss"
        set_cached(key, data)
    return data


# ─────────────────────────────────────────────
# Public endpoints
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "etf-analyzer",
        "version": "0.5.1",
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
            "cache": "ready",
            "portfolio_engine": "ready",
            "llm_narrative": "available" if llm_available() else "stub (set GEMINI_API_KEY)",
            "stock_final_client": "configured",
            "mcp": "mounted" if _MCP_AVAILABLE else "unavailable (install mcp pkg)",
        },
    }


# ─────────────────────────────────────────────
# Protected: ETF 조회
# ─────────────────────────────────────────────
@app.get("/v1/etfs", dependencies=[Depends(verify_api_key)])
def list_etfs(
    market: Optional[str] = Query(None, description="KR, US, or None for both"),
    category: Optional[int] = Query(None, description="Naver category 0~7 (KR only)"),
    min_aum: Optional[float] = Query(None, description="최소 순자산 (KR: 억원)"),
    limit: int = Query(50, ge=1, le=500),
):
    """ETF 리스트 (필터 지원)."""
    market = (market or "").upper()
    cat = category or 0
    key = f"list:{market or 'BOTH'}:cat{cat}:aum{min_aum or 0}"

    def _fetch():
        results = {"market": market or "BOTH"}
        if market in ("KR", ""):
            kr_items = get_naver_etf_list(cat)
            if min_aum is not None:
                kr_items = [x for x in kr_items if (x.get("marketSum") or 0) >= min_aum]
            results["kr"] = {"count": len(kr_items), "items": kr_items[:limit]}
        if market in ("US", ""):
            from curated_us_etfs import CURATED_US_ETFS
            results["us"] = {
                "count": len(CURATED_US_ETFS),
                "items": CURATED_US_ETFS[:limit],
            }
        return results

    return _cached_fetch(key, TTL_LIST, _fetch)


# 주의: /compare 가 /{code}보다 먼저 정의돼야 FastAPI 라우팅 우선됨
@app.get("/v1/etfs/compare", dependencies=[Depends(verify_api_key)])
def compare_etfs(
    codes: str = Query(..., description="쉼표 구분 2~5개 코드. 예: 069500,SPY,QQQ"),
    verbose: bool = Query(False, description="LLM 한국어 해설 포함"),
):
    """여러 ETF를 병렬 조회 후 공통 지표 비교."""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) < 2:
        raise HTTPException(400, "최소 2개 이상의 코드가 필요합니다.")
    if len(code_list) > 5:
        raise HTTPException(400, "한번에 최대 5개까지 비교 가능합니다.")

    def _fetch_one(code):
        source = pick_source(code)
        key = f"detail:{source}:{code}"
        if source == "naver":
            return _cached_fetch(key, TTL_DETAIL, lambda: get_naver_etf_detail(code))
        return _cached_fetch(key, TTL_DETAIL, lambda: get_yf_etf_info(code))

    # 병렬 fetch
    with ThreadPoolExecutor(max_workers=5) as ex:
        raw = list(ex.map(_fetch_one, code_list))

    # 공통 지표 추출 + 정규화
    comparison = []
    holdings_by_code = {}
    for code, data in zip(code_list, raw):
        source = pick_source(code)
        if source == "naver":
            comparison.append({
                "code": code,
                "market": "KR",
                "name": data.get("name"),
                "price": data.get("price"),
                "currency": "KRW",
                "change_rate_pct": data.get("change_rate"),
                "expense_info": data.get("expense_info"),
                "market_cap": data.get("market_cap"),
                "underlying_index": data.get("underlying_index"),
                "asset_manager": data.get("asset_manager"),
                "period_returns": data.get("period_returns", {}),
            })
            holdings_by_code[code] = {h["code"] for h in (data.get("holdings_top") or [])}
        else:
            comparison.append({
                "code": code,
                "market": "US",
                "name": data.get("name"),
                "price": data.get("price"),
                "currency": data.get("currency"),
                "expense_ratio_pct": data.get("expense_ratio_pct"),
                "dividend_yield_pct": data.get("dividend_yield_pct"),
                "aum_usd": data.get("aum_usd"),
                "category": data.get("category"),
                "ytd_return_pct": data.get("ytd_return_pct"),
                "three_year_avg_return_pct": data.get("three_year_avg_return_pct"),
            })
            # yfinance holdings 별도 조회
            h_key = f"holdings:{code}"
            hdata = _cached_fetch(
                h_key, TTL_HOLDINGS,
                lambda c=code: {"items": get_yf_etf_holdings(c, top_n=10)},
            )
            holdings_by_code[code] = {
                h.get("symbol") for h in (hdata.get("items") or []) if h.get("symbol")
            }

    # 쌍별 Jaccard 유사도 (구성종목 중복도)
    overlap = []
    cl = list(holdings_by_code.items())
    for i in range(len(cl)):
        for j in range(i + 1, len(cl)):
            a_code, a_set = cl[i]
            b_code, b_set = cl[j]
            if a_set and b_set:
                inter = len(a_set & b_set)
                union = len(a_set | b_set)
                jaccard = round(inter / union, 3) if union else 0
            else:
                jaccard = None
            overlap.append({
                "pair": [a_code, b_code],
                "jaccard_similarity": jaccard,
                "common_count": len(a_set & b_set) if a_set and b_set else 0,
            })

    result = {
        "codes": code_list,
        "count": len(comparison),
        "comparison": comparison,
        "holdings_overlap": overlap,
    }
    if verbose:
        result["narrative"] = explain_comparison(result)
    return result


@app.get("/v1/etfs/{code}", dependencies=[Depends(verify_api_key)])
def get_etf(code: str, verbose: bool = Query(False, description="LLM 한국어 해설 포함")):
    """단일 ETF 상세. 자동 라우팅 + 캐시. verbose=true 면 LLM 설명 첨부."""
    source = pick_source(code)
    key = f"detail:{source}:{code}"
    try:
        if source == "naver":
            data = _cached_fetch(key, TTL_DETAIL, lambda: get_naver_etf_detail(code))
        else:
            data = _cached_fetch(key, TTL_DETAIL, lambda: get_yf_etf_info(code))
        response = {"source": source, "data": data}
        if verbose:
            response["narrative"] = explain_etf(data)
        return response
    except Exception as e:
        raise HTTPException(500, f"Data fetch failed: {type(e).__name__}")


@app.get("/v1/etfs/{code}/holdings", dependencies=[Depends(verify_api_key)])
def get_etf_holdings(code: str, top_n: int = Query(10, ge=1, le=50), full: bool = False):
    """ETF 구성종목."""
    source = pick_source(code)
    key = f"holdings:{source}:{code}:full{int(full)}:n{top_n}"

    def _fetch():
        if source == "naver":
            if full:
                items = get_naver_etf_holdings_full(code)
            else:
                detail = get_naver_etf_detail(code)
                items = (detail.get("holdings_top") or [])[:top_n]
            return {"source": "naver", "code": code, "holdings": items}
        items = get_yf_etf_holdings(code, top_n=top_n)
        return {"source": "yfinance", "code": code, "holdings": items}

    return _cached_fetch(key, TTL_HOLDINGS, _fetch)


@app.get("/v1/etfs/{code}/returns", dependencies=[Depends(verify_api_key)])
def get_etf_returns(code: str):
    """기간별 수익률 (1M/3M/6M/1Y 등)."""
    source = pick_source(code)
    key = f"returns:{source}:{code}"

    def _fetch():
        if source == "naver":
            detail = get_naver_etf_detail(code)
            return {
                "source": "naver",
                "code": code,
                "period_returns": detail.get("period_returns", {}),
            }
        return {
            "source": "yfinance",
            "code": code,
            **get_yf_etf_returns(code),
        }

    return _cached_fetch(key, TTL_RETURNS, _fetch)


@app.get("/v1/etfs/{code}/history", dependencies=[Depends(verify_api_key)])
def get_etf_history(code: str, period: str = Query("1y", pattern=r"^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$")):
    """과거 가격 (해외 ETF만 — 네이버는 미구현)."""
    source = pick_source(code)
    if source == "naver":
        return {
            "source": "naver",
            "code": code,
            "status": "not_implemented",
            "message": "한국 ETF 과거 가격은 Phase 3+ 에서 지원 예정입니다.",
        }
    key = f"history:yf:{code}:{period}"

    def _fetch():
        return {
            "source": "yfinance",
            "code": code,
            "period": period,
            "data": get_yf_etf_history(code, period=period),
        }

    return _cached_fetch(key, TTL_RETURNS, _fetch)


# ─────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────
@app.post("/v1/admin/refresh", dependencies=[Depends(verify_api_key)])
def admin_refresh(
    prefix: str = Query("", description="삭제할 캐시 키 prefix (비우면 전체)"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """캐시 무효화 — X-Admin-Key 추가 검증."""
    admin_key = os.environ.get("ETF_ADMIN_KEY")
    if admin_key and x_admin_key != admin_key:
        raise HTTPException(403, "Forbidden: admin key required")
    deleted = clear_cache(prefix)
    return {"status": "ok", "deleted": deleted, "prefix": prefix}


@app.get("/v1/admin/cache-stats", dependencies=[Depends(verify_api_key)])
def admin_cache_stats():
    """캐시 통계."""
    return cache_stats()


# ─────────────────────────────────────────────
# Portfolio recommendation
# ─────────────────────────────────────────────
class PortfolioRequest(BaseModel):
    risk: str = "balanced"              # conservative / balanced / aggressive
    amount_krw: int = 500_000
    horizon_years: int = 10
    theme: Optional[str] = None         # 반도체 / AI / 배당 / 리츠 등
    market_mix: str = "global"          # global / kr_only / us_only


@app.post("/v1/portfolio/recommend", dependencies=[Depends(verify_api_key)])
def recommend_portfolio(req: PortfolioRequest, verbose: bool = Query(False)):
    """사용자 프로필 기반 포트폴리오 추천. verbose=true 면 LLM 해설 첨부."""
    try:
        result = portfolio_recommend(
            risk=req.risk,
            amount_krw=req.amount_krw,
            horizon_years=req.horizon_years,
            theme=req.theme,
            market_mix=req.market_mix,
        )
        if verbose:
            result["narrative"] = explain_portfolio(result)
        return result
    except Exception as e:
        raise HTTPException(500, f"Portfolio engine failed: {type(e).__name__}: {str(e)[:200]}")


# ─────────────────────────────────────────────
# stock-final drill-down: ETF 구성종목 → 개별 종목 분석
# ─────────────────────────────────────────────
@app.get(
    "/v1/etfs/{etf_code}/holdings/{stock_code}",
    dependencies=[Depends(verify_api_key)],
)
def get_holding_analysis(etf_code: str, stock_code: str):
    """ETF 구성종목 중 하나의 개별 종목 상세 분석 (stock-final 릴레이).

    현재 한국 종목(stock_code)만 지원. 해외 종목은 yfinance로 가능하지만
    stock-final에 연결하는 특성상 한국 종목이 먼저.
    """
    # 캐시 (stock-final 결과도 캐시)
    from etf_cache import TTL_DETAIL
    key = f"stockfinal:{stock_code}"

    def _fetch():
        return get_stock_analysis(stock_code)

    result = _cached_fetch(key, TTL_DETAIL, _fetch)
    return {
        "etf_code": etf_code,
        "stock_code": stock_code,
        "analysis": result,
    }


# ─────────────────────────────────────────────
# MCP 서버 마운트 (Streamable HTTP 트랜스포트)
# ─────────────────────────────────────────────
if _MCP_AVAILABLE and _mcp_server is not None:
    try:
        _mcp_app = None
        # mcp>=1.3.0: streamable_http_app()
        if hasattr(_mcp_server, "streamable_http_app"):
            _mcp_app = _mcp_server.streamable_http_app()
        elif hasattr(_mcp_server, "sse_app"):
            _mcp_app = _mcp_server.sse_app()

        if _mcp_app is not None:
            app.mount("/mcp", _mcp_app)
            logger.info("MCP mounted at /mcp")
        else:
            logger.warning("MCP server has no ASGI app method")
            _MCP_AVAILABLE = False
    except Exception as e:
        logger.error(f"MCP mount failed: {type(e).__name__}: {e}")
        _MCP_AVAILABLE = False
