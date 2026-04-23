"""MCP 서버 — etf-analyzer의 주요 기능 4개를 MCP 도구로 노출.

블랙박스 원칙: 내부 구현(파싱/필터/알고리즘)은 노출 X.
4개 도구만 공개:
  - search_etf       : ETF 리스트 검색
  - get_etf_info     : 단일 ETF 상세
  - compare_etfs     : 여러 ETF 비교
  - recommend_portfolio : 포트폴리오 추천

Claude Desktop 연결:
    "mcpServers": {
      "etf-analyzer": {
        "url": "https://etf-analyzer.replit.app/mcp",
        "headers": {"X-API-Key": "<ETF_API_KEY>"}
      }
    }
"""
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor

from mcp.server.fastmcp import FastMCP

from router import pick_source
from naver_etf import get_naver_etf_list, get_naver_etf_detail
from yfinance_etf import get_yf_etf_info, get_yf_etf_holdings
from portfolio_engine import recommend as _portfolio_recommend
from llm_narrative import explain_etf, explain_comparison, explain_portfolio
from curated_us_etfs import CURATED_US_ETFS

# ─────────────────────────────────────────────
# FastMCP + DNS rebinding 보호 비활성화 (Replit 원격 호스트 허용)
# ─────────────────────────────────────────────
_transport_security = None
_candidate_imports = [
    "mcp.server.transport_security",
    "mcp.server.fastmcp.utilities.transport_security",
    "mcp.server.fastmcp.transport_security",
    "mcp.server.auth.transport_security",
]
for _modpath in _candidate_imports:
    try:
        _mod = __import__(_modpath, fromlist=["TransportSecuritySettings"])
        _TSS = getattr(_mod, "TransportSecuritySettings", None)
        if _TSS:
            _transport_security = _TSS(enable_dns_rebinding_protection=False)
            break
    except (ImportError, AttributeError, TypeError):
        continue

if _transport_security is not None:
    mcp = FastMCP("etf-analyzer", transport_security=_transport_security)
else:
    # Fallback: 일반 생성 후 속성 직접 패치 시도
    mcp = FastMCP("etf-analyzer")
    for _attr in ("_settings", "settings"):
        _s = getattr(mcp, _attr, None)
        if _s is not None and hasattr(_s, "transport_security"):
            try:
                _s.transport_security.enable_dns_rebinding_protection = False
            except AttributeError:
                pass


# ─────────────────────────────────────────────
# Tool 1. search_etf
# ─────────────────────────────────────────────
@mcp.tool()
def search_etf(
    query: str = "",
    market: str = "BOTH",
    category: int = 0,
    limit: int = 20,
) -> dict:
    """ETF를 검색·필터링합니다.

    Args:
        query: 검색어 (이름 부분일치). 공백이면 전체.
        market: KR(한국), US(해외), BOTH(둘 다).
        category: 한국 카테고리 0~7 (0:전체, 1:국내시장지수, 2:국내업종/테마, 3:파생, 4:해외주식, 5:원자재, 6:채권, 7:기타).
        limit: 최대 반환 개수 (기본 20).

    Returns:
        {kr: {count, items}, us: {count, items}}  (market=BOTH 기준)
    """
    market = market.upper()
    results = {"query": query, "market": market}
    q_lower = query.lower().strip()

    if market in ("KR", "BOTH"):
        kr = get_naver_etf_list(category)
        if q_lower:
            kr = [x for x in kr if q_lower in (x.get("itemname") or "").lower()]
        results["kr"] = {"count": len(kr), "items": kr[:limit]}

    if market in ("US", "BOTH"):
        us = CURATED_US_ETFS
        if q_lower:
            us = [e for e in us
                  if q_lower in e["symbol"].lower()
                  or q_lower in e.get("name_hint", "").lower()]
        results["us"] = {"count": len(us), "items": us[:limit]}

    return results


# ─────────────────────────────────────────────
# Tool 2. get_etf_info
# ─────────────────────────────────────────────
@mcp.tool()
def get_etf_info(code_or_name: str, verbose: bool = False) -> dict:
    """단일 ETF의 상세 정보를 반환합니다.

    한국 ETF 6자리 코드(예: 069500) 또는 미국 티커(예: SPY, QQQ)를 자동 감지.

    Args:
        code_or_name: ETF 코드 또는 심볼.
        verbose: True면 한국어 해설 포함.

    Returns:
        {source, data, narrative?}
    """
    source = pick_source(code_or_name)
    try:
        if source == "naver":
            data = get_naver_etf_detail(code_or_name)
        else:
            data = get_yf_etf_info(code_or_name)
        response = {"source": source, "data": data}
        if verbose:
            response["narrative"] = explain_etf(data)
        return response
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:200]}"}


# ─────────────────────────────────────────────
# Tool 3. compare_etfs
# ─────────────────────────────────────────────
@mcp.tool()
def compare_etfs(codes: str, verbose: bool = False) -> dict:
    """여러 ETF(2~5개)를 비교합니다.

    Args:
        codes: 쉼표 구분 코드. 예: "069500,SPY,QQQ".
        verbose: True면 한국어 해설 포함.

    Returns:
        {codes, comparison: [...], holdings_overlap: [...], narrative?}
    """
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not (2 <= len(code_list) <= 5):
        return {"error": "codes는 2~5개여야 합니다."}

    def _fetch_one(code):
        src = pick_source(code)
        if src == "naver":
            return src, get_naver_etf_detail(code)
        return src, get_yf_etf_info(code)

    with ThreadPoolExecutor(max_workers=5) as ex:
        raw = list(ex.map(_fetch_one, code_list))

    comparison = []
    holdings_by_code = {}
    for code, (src, data) in zip(code_list, raw):
        if src == "naver":
            comparison.append({
                "code": code, "market": "KR",
                "name": data.get("name"),
                "price": data.get("price"),
                "currency": "KRW",
                "expense_info": data.get("expense_info"),
                "market_cap": data.get("market_cap"),
                "underlying_index": data.get("underlying_index"),
                "period_returns": data.get("period_returns", {}),
            })
            holdings_by_code[code] = {h["code"] for h in (data.get("holdings_top") or [])}
        else:
            comparison.append({
                "code": code, "market": "US",
                "name": data.get("name"),
                "price": data.get("price"),
                "currency": data.get("currency"),
                "expense_ratio_pct": data.get("expense_ratio_pct"),
                "dividend_yield_pct": data.get("dividend_yield_pct"),
                "aum_usd": data.get("aum_usd"),
                "category": data.get("category"),
                "ytd_return_pct": data.get("ytd_return_pct"),
            })
            try:
                h = get_yf_etf_holdings(code, top_n=10)
                holdings_by_code[code] = {x.get("symbol") for x in h if x.get("symbol")}
            except Exception:
                holdings_by_code[code] = set()

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
        "comparison": comparison,
        "holdings_overlap": overlap,
    }
    if verbose:
        result["narrative"] = explain_comparison(result)
    return result


# ─────────────────────────────────────────────
# Tool 4. recommend_portfolio
# ─────────────────────────────────────────────
@mcp.tool()
def recommend_portfolio(
    risk: str = "balanced",
    amount_krw: int = 500000,
    horizon_years: int = 10,
    theme: str = "",
    market_mix: str = "global",
    verbose: bool = False,
) -> dict:
    """사용자 프로필에 맞는 ETF 포트폴리오를 추천합니다.

    Args:
        risk: conservative(안정) / balanced(균형) / aggressive(공격).
        amount_krw: 월 투자액(원). 기본 500,000.
        horizon_years: 투자 기간(년). 기본 10.
        theme: 선호 테마 (반도체/AI/배당/리츠/에너지 등). 선택.
        market_mix: global(한·미 혼합) / kr_only / us_only. 기본 global.
        verbose: True면 한국어 해설 포함.

    Returns:
        {portfolio: [{code, name, weight_pct, role, market, allocated_amount_krw}],
         metrics, warnings, disclaimer, narrative?}
    """
    try:
        result = _portfolio_recommend(
            risk=risk,
            amount_krw=amount_krw,
            horizon_years=horizon_years,
            theme=(theme or None),
            market_mix=market_mix,
        )
        if verbose:
            result["narrative"] = explain_portfolio(result)
        return result
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:200]}"}
