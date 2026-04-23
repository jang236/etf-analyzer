"""포트폴리오 추천 엔진 (블랙박스).

🔒 내부 로직은 MCP에 직접 노출 X.
    외부에는 `recommend()` 결과만 제공.

추천 방식: 규칙 기반 (Core-Satellite + 리스크별 자산배분)
- Step 1: 리스크 → 자산배분 (주식/채권/대체)
- Step 2: 자산배분 → 버킷 (한/미/Core/Satellite)
- Step 3: 각 버킷에서 후보 필터링 → 선택
- Step 4: 포트폴리오 검증 + 지표 계산
"""
import re
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────
# 정책 상수
# ─────────────────────────────────────────────
RISK_PROFILES = {
    "conservative": {"equity": 0.30, "bond": 0.50, "alternative": 0.20},
    "balanced":     {"equity": 0.60, "bond": 0.30, "alternative": 0.10},
    "aggressive":   {"equity": 0.80, "bond": 0.10, "alternative": 0.10},
}
CORE_WEIGHT = 0.70
SATELLITE_WEIGHT = 0.30
MIN_AUM_KR = 1000       # 억원
MIN_AUM_US = 1_000_000_000  # $1B
MAX_EXPENSE_PCT = 0.30
DISCLAIMER = (
    "본 서비스는 정보 제공 목적이며 투자 자문이 아닙니다. "
    "최종 투자 판단은 본인 책임이며, 과거 수익률이 미래 수익을 보장하지 않습니다."
)

# ─────────────────────────────────────────────
# 버킷별 선호 KR ETF (AUM 기반 기본 선택을 보정)
# 예: 채권 AUM TOP은 CD금리형(단기)이지만 밸런스 포트폴리오엔 국고채10년이 적합
# ─────────────────────────────────────────────
KR_PREFERRED = {
    "core_equity_kr": ["069500", "102110", "278530", "152100", "148020"],
    "bond_kr": ["114260", "148070", "302190", "272910", "130730"],  # 국고채10년 시리즈 + 통안채
    "alternative": ["132030", "411060", "319640", "157490"],  # 골드(H)/금현물/골드선물/은선물
}

# ─────────────────────────────────────────────
# 채권 버킷에서 제외할 이름 패턴 (MMF, 단기채, 파생형)
# ─────────────────────────────────────────────
BOND_EXCLUDE_PATTERNS = r"(CD금리|머니마켓|MMF|단기자금|단기채|레버리지|인버스)"
ALT_INCLUDE_PATTERNS = r"(골드|금현물|실버|은|원유|구리|부동산|리츠|원자재)"


# ─────────────────────────────────────────────
# 잘 알려진 한국 ETF 보수 (네이버 리스트에 총보수 없어서 하드코딩)
# ─────────────────────────────────────────────
KR_EXPENSE_FALLBACK = {
    "069500": 0.15,  # KODEX 200
    "102110": 0.05,  # TIGER 200
    "278530": 0.05,  # KODEX 200TR
    "152100": 0.05,  # ARIRANG 200
    "148020": 0.15,  # KBSTAR 200
    "360750": 0.07,  # TIGER 미국S&P500
    "379800": 0.05,  # KODEX 미국S&P500
    "133690": 0.07,  # TIGER 미국나스닥100
    "395580": 0.05,  # KODEX 미국나스닥100TR
    "114260": 0.15,  # KODEX 국고채10년
    "148070": 0.15,  # KOSEF 국고채10년
    "302190": 0.15,  # TIGER 국고채10년
    "132030": 0.50,  # KODEX 골드선물(H)
    "411060": 0.25,  # ACE KRX금현물
    "459580": 0.02,  # KODEX CD금리액티브(합성)
    "396500": 0.45,  # TIGER 반도체TOP10
    "102780": 0.15,  # KODEX 반도체
    "091160": 0.15,  # KODEX 반도체
    "117700": 0.15,  # KODEX 구리선물(H)
    "157490": 0.15,  # KODEX 은선물(H)
}


# ─────────────────────────────────────────────
# 버킷 구성 (리스크·마켓믹스별 비중 분배)
# ─────────────────────────────────────────────
def _compute_buckets(risk: str, market_mix: str) -> List[Dict]:
    """리스크 + 시장믹스 → 버킷 비중 리스트 반환.

    각 버킷: {"name", "target_weight", "role", "market"}
    """
    alloc = RISK_PROFILES.get(risk, RISK_PROFILES["balanced"])
    eq = alloc["equity"]
    bond = alloc["bond"]
    alt = alloc["alternative"]

    buckets = []

    # 주식
    if market_mix == "kr_only":
        buckets.append({"name": "core_equity_kr", "target_weight": eq * CORE_WEIGHT, "role": "core", "market": "KR"})
        buckets.append({"name": "satellite_equity_kr", "target_weight": eq * SATELLITE_WEIGHT, "role": "satellite", "market": "KR"})
    elif market_mix == "us_only":
        buckets.append({"name": "core_equity_us", "target_weight": eq * CORE_WEIGHT, "role": "core", "market": "US"})
        buckets.append({"name": "satellite_equity_us", "target_weight": eq * SATELLITE_WEIGHT, "role": "satellite", "market": "US"})
    else:  # global
        buckets.append({"name": "core_equity_kr", "target_weight": eq * 0.5 * CORE_WEIGHT, "role": "core", "market": "KR"})
        buckets.append({"name": "core_equity_us", "target_weight": eq * 0.5 * CORE_WEIGHT, "role": "core", "market": "US"})
        buckets.append({"name": "satellite_equity", "target_weight": eq * SATELLITE_WEIGHT, "role": "satellite", "market": "GLOBAL"})

    # 채권
    if bond > 0:
        if market_mix == "kr_only":
            buckets.append({"name": "bond_kr", "target_weight": bond, "role": "bond", "market": "KR"})
        elif market_mix == "us_only":
            buckets.append({"name": "bond_us", "target_weight": bond, "role": "bond", "market": "US"})
        else:
            buckets.append({"name": "bond_kr", "target_weight": bond * 0.5, "role": "bond", "market": "KR"})
            buckets.append({"name": "bond_us", "target_weight": bond * 0.5, "role": "bond", "market": "US"})

    # 대체 (원자재/리츠/금) — market_mix별로 분기
    if alt > 0:
        if market_mix == "kr_only":
            buckets.append({"name": "alternative", "target_weight": alt, "role": "alternative", "market": "KR"})
        elif market_mix == "us_only":
            buckets.append({"name": "alternative", "target_weight": alt, "role": "alternative", "market": "US"})
        else:
            buckets.append({"name": "alternative", "target_weight": alt, "role": "alternative", "market": "GLOBAL"})

    return buckets


# ─────────────────────────────────────────────
# 후보 수집 + 필터링
# ─────────────────────────────────────────────
def _collect_kr_candidates(bucket_name: str, theme: Optional[str]) -> List[Dict]:
    """네이버 ETF 리스트에서 버킷에 맞는 후보 추출."""
    from naver_etf import get_naver_etf_list
    from etf_cache import get_cached, set_cached, TTL_LIST

    # 버킷 → 네이버 카테고리 매핑
    cat_map = {
        "core_equity_kr": 1,            # 국내시장지수
        "satellite_equity_kr": 2,       # 국내업종/테마
        "satellite_equity": 2,          # (global 라우팅 경유)
        "bond_kr": 6,                   # 채권
        "alternative": 5,               # 원자재
    }
    cat = cat_map.get(bucket_name, 0)

    key = f"port:kr_list:{cat}"
    cached = get_cached(key, TTL_LIST)
    if cached is not None:
        items = cached.get("items", [])
    else:
        items = get_naver_etf_list(cat)
        set_cached(key, {"items": items})

    # AUM 필터
    filtered = [x for x in items if (x.get("marketSum") or 0) >= MIN_AUM_KR]

    # 공통: 레버리지·인버스 제외
    filtered = [
        x for x in filtered
        if not re.search(r"(레버리지|레버|인버스|2X|-1X|숏|bear|bull.*3x)",
                         x.get("itemname", ""), re.IGNORECASE)
    ]

    # 버킷별 추가 필터
    if bucket_name == "bond_kr":
        # 단기자금성(MMF/CD금리) 제외 — 장기 포트폴리오엔 부적합
        filtered = [
            x for x in filtered
            if not re.search(BOND_EXCLUDE_PATTERNS, x.get("itemname", ""))
        ]
    elif bucket_name == "alternative":
        # 원자재·리츠 관련만
        filtered = [
            x for x in filtered
            if re.search(ALT_INCLUDE_PATTERNS, x.get("itemname", ""))
        ]

    # 선호 목록이 있으면 그 중에서 우선 선택
    preferred_codes = KR_PREFERRED.get(bucket_name, [])
    if preferred_codes:
        preferred_items = [x for x in filtered if x.get("itemcode") in preferred_codes]
        if preferred_items:
            # 선호 순서대로 정렬
            order = {c: i for i, c in enumerate(preferred_codes)}
            preferred_items.sort(key=lambda x: order.get(x["itemcode"], 999))
            return preferred_items

    # 테마 필터 (satellite only)
    if theme and "satellite" in bucket_name:
        theme_lower = theme.lower()
        filtered = [x for x in filtered if theme_lower in x.get("itemname", "").lower()]

    # AUM 내림차순
    filtered.sort(key=lambda x: x.get("marketSum") or 0, reverse=True)
    return filtered


def _collect_us_candidates(bucket_name: str, theme: Optional[str]) -> List[Dict]:
    """큐레이션 미국 ETF 리스트에서 후보 추출."""
    from curated_us_etfs import CURATED_US_ETFS

    # 버킷 → 큐레이션 카테고리 매핑
    cat_map = {
        "core_equity_us": ("core_us",),
        "satellite_equity_us": ("theme", "sector", "factor", "dividend"),
        "satellite_equity": ("theme", "sector", "factor"),
        "bond_us": ("bond",),
        "alternative": ("commodity", "reit"),
    }
    cats = cat_map.get(bucket_name, ())
    if not cats:
        return []

    candidates = [e for e in CURATED_US_ETFS if e["category"] in cats]

    # 테마 필터
    if theme and "satellite" in bucket_name:
        theme_lower = theme.lower()
        candidates = [
            e for e in candidates
            if theme_lower in e.get("name_hint", "").lower()
        ]

    return candidates


# ─────────────────────────────────────────────
# 버킷별 선택
# ─────────────────────────────────────────────
def _pick_kr(bucket: Dict, theme: Optional[str]) -> Optional[Dict]:
    """한국 버킷에서 하나 선택 (AUM 최대)."""
    cands = _collect_kr_candidates(bucket["name"], theme)
    if not cands:
        return None
    top = cands[0]
    return {
        "code": top["itemcode"],
        "name": top["itemname"],
        "market": "KR",
        "weight_pct": round(bucket["target_weight"] * 100, 2),
        "role": bucket["role"],
        "bucket": bucket["name"],
        "expense_ratio_pct": KR_EXPENSE_FALLBACK.get(top["itemcode"]),
        "aum_krw_100m": top.get("marketSum"),
        "price": top.get("nowVal"),
        "category": top.get("category_name"),
    }


def _pick_us(bucket: Dict, theme: Optional[str]) -> Optional[Dict]:
    """미국 버킷에서 하나 선택 (큐레이션 순서의 첫 매칭)."""
    cands = _collect_us_candidates(bucket["name"], theme)
    if not cands:
        # 테마 필터로 없으면 테마 없이 다시 시도
        cands = _collect_us_candidates(bucket["name"], None)
    if not cands:
        return None
    top = cands[0]
    return {
        "code": top["symbol"],
        "name": f'{top["symbol"]} ({top["name_hint"]})',
        "market": "US",
        "weight_pct": round(bucket["target_weight"] * 100, 2),
        "role": bucket["role"],
        "bucket": bucket["name"],
        "category": top["category"],
    }


def _pick_global(bucket: Dict, theme: Optional[str]) -> Optional[Dict]:
    """글로벌 버킷 라우팅. role 기반 dispatch."""
    role = bucket.get("role")

    # 대체자산: KR 원자재 우선 (골드/리츠), 없으면 US commodity/reit
    if role == "alternative":
        kr = _pick_kr({**bucket, "name": "alternative"}, None)
        if kr:
            return kr
        return _pick_us({**bucket, "name": "alternative"}, None)

    # Satellite 주식: 테마 있으면 US 테마 ETF 우선, 없으면 KR 테마
    if role == "satellite":
        if theme:
            us = _pick_us({**bucket, "name": "satellite_equity_us"}, theme)
            if us:
                return us
            kr = _pick_kr({**bucket, "name": "satellite_equity_kr"}, theme)
            if kr:
                return kr
        # 테마 없음 → KR 국내 업종/테마 TOP (가장 익숙하고 접근성 좋음)
        return _pick_kr({**bucket, "name": "satellite_equity_kr"}, None)

    # 기타 — 기본은 KR
    return _pick_kr({**bucket, "name": bucket.get("name", "satellite_equity_kr")}, theme)


# ─────────────────────────────────────────────
# 검증 및 지표
# ─────────────────────────────────────────────
def _calculate_metrics(portfolio: List[Dict]) -> Dict:
    """포트폴리오 전체 지표 계산."""
    total_weight = sum(p["weight_pct"] for p in portfolio)

    # 가중평균 보수 (KR은 hardcode, US는 yfinance 미사용 — Phase 4에서 보강)
    weighted_expense_parts = []
    for p in portfolio:
        exp = p.get("expense_ratio_pct")
        if exp is not None:
            weighted_expense_parts.append((p["weight_pct"] / 100) * exp)
    weighted_expense = round(sum(weighted_expense_parts), 3) if weighted_expense_parts else None

    # 시장 분산
    kr_weight = sum(p["weight_pct"] for p in portfolio if p["market"] == "KR")
    us_weight = sum(p["weight_pct"] for p in portfolio if p["market"] == "US")

    # 역할별 분포
    role_dist = {}
    for p in portfolio:
        role_dist.setdefault(p["role"], 0)
        role_dist[p["role"]] += p["weight_pct"]
    role_dist = {k: round(v, 2) for k, v in role_dist.items()}

    return {
        "total_weight_pct": round(total_weight, 2),
        "weighted_expense_ratio_pct": weighted_expense,
        "market_distribution": {
            "kr_pct": round(kr_weight, 2),
            "us_pct": round(us_weight, 2),
        },
        "role_distribution": role_dist,
    }


def _validate_portfolio(portfolio: List[Dict]) -> Tuple[bool, List[str]]:
    """포트폴리오 제약 검증. 경고 리스트 반환."""
    warnings = []
    total = sum(p["weight_pct"] for p in portfolio)

    if abs(total - 100) > 1.5:
        warnings.append(f"비중 합계 {total:.2f}% (100% 근사 아님)")

    # 단일 종목 최대 노출 (ETF 레벨; 개별 holding 레벨은 Phase 4에서)
    max_single_weight = max((p["weight_pct"] for p in portfolio), default=0)
    if max_single_weight > 40:
        warnings.append(f"단일 ETF 노출 {max_single_weight}% (40% 초과)")

    # 레버리지/인버스 포함 여부
    from curated_us_etfs import is_leveraged_or_inverse
    for p in portfolio:
        if p["market"] == "US" and is_leveraged_or_inverse(p["code"]):
            warnings.append(f"{p['code']} 레버리지/인버스 ETF — 장기 보유 부적합")

    return (len(warnings) == 0, warnings)


# ─────────────────────────────────────────────
# 메인 엔트리
# ─────────────────────────────────────────────
def recommend(
    risk: str = "balanced",
    amount_krw: int = 500_000,
    horizon_years: int = 10,
    theme: Optional[str] = None,
    market_mix: str = "global",
) -> Dict:
    """ETF 포트폴리오 추천.

    Args:
        risk: conservative / balanced / aggressive
        amount_krw: 월 투자액
        horizon_years: 투자 기간
        theme: 선호 테마 (반도체, AI, 배당, 리츠 등)
        market_mix: global / kr_only / us_only

    Returns: 포트폴리오 + 지표 + 경고 + 면책
    """
    # 입력 정규화
    if risk not in RISK_PROFILES:
        risk = "balanced"
    if market_mix not in ("global", "kr_only", "us_only"):
        market_mix = "global"

    buckets = _compute_buckets(risk, market_mix)

    # 버킷별 선택
    portfolio = []
    skipped = []
    for bucket in buckets:
        market = bucket["market"]
        if market == "KR":
            pick = _pick_kr(bucket, theme)
        elif market == "US":
            pick = _pick_us(bucket, theme)
        else:  # GLOBAL
            pick = _pick_global(bucket, theme)

        if pick:
            portfolio.append(pick)
        else:
            skipped.append(bucket["name"])

    # 스킵된 버킷이 있으면 비중 재조정 (나머지에 비례 증배)
    if skipped and portfolio:
        current_total = sum(p["weight_pct"] for p in portfolio)
        if 0 < current_total < 100:
            scale = 100 / current_total
            for p in portfolio:
                p["weight_pct"] = round(p["weight_pct"] * scale, 2)

    # 투자 금액 배분
    for p in portfolio:
        p["allocated_amount_krw"] = round(amount_krw * p["weight_pct"] / 100)

    # 검증 & 지표
    valid, warnings = _validate_portfolio(portfolio)
    metrics = _calculate_metrics(portfolio)
    if skipped:
        warnings.append(f"다음 버킷은 적합 후보가 없어 스킵됨: {skipped}")

    return {
        "inputs": {
            "risk": risk,
            "amount_krw": amount_krw,
            "horizon_years": horizon_years,
            "theme": theme,
            "market_mix": market_mix,
        },
        "target_allocation": RISK_PROFILES[risk],
        "portfolio": portfolio,
        "metrics": metrics,
        "valid": valid,
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }
