"""한국/해외 ETF 자동 라우팅.

규칙:
- 6자리 숫자 코드: 한국 → naver
- KODEX/TIGER/ACE/KBSTAR/SOL/HANARO/KOSEF/ARIRANG 접두어: 한국 → naver
- 그 외 알파벳 심볼: 해외 → yfinance
"""

KR_PREFIXES = (
    "KODEX", "TIGER", "ACE", "KBSTAR", "SOL", "HANARO",
    "KOSEF", "ARIRANG", "HK", "WOORI", "SMART", "FOCUS",
    "TIMEFOLIO", "RISE",
)


def pick_source(code_or_name: str) -> str:
    """단일 코드/이름 → 데이터 소스 결정."""
    if not code_or_name:
        return "yfinance"
    c = code_or_name.strip()
    # 6자리 숫자
    if c.isdigit() and len(c) == 6:
        return "naver"
    # 한국 ETF 접두어
    if c.upper().startswith(KR_PREFIXES):
        return "naver"
    # 기본: 해외
    return "yfinance"


def detect_market_from_query(query: str) -> str:
    """자연어 쿼리에서 시장 힌트 추출.

    Returns: "KR" | "US" | "BOTH"
    """
    if not query:
        return "BOTH"
    q = query.lower()
    kr_kw = ["한국", "국내", "korea", "domestic"]
    us_kw = ["미국", "해외", "us", "usa", "america", "global"]
    has_kr = any(k in q for k in kr_kw)
    has_us = any(k in q for k in us_kw)
    if has_kr and not has_us:
        return "KR"
    if has_us and not has_kr:
        return "US"
    return "BOTH"
