"""한국/해외 ETF 자동 라우팅.

규칙:
- 6자리 한국 종목코드: 한국 → naver
  (전부 숫자 "069500" + 영문 섞인 신형 코드 "0148J0" 모두 포함.
   2023년 이후 신규 상장분은 영숫자 코드를 쓴다.)
- KODEX/TIGER/ACE/KBSTAR/SOL/HANARO/KOSEF/ARIRANG 접두어: 한국 → naver
- 그 외 알파벳 심볼(SPY, QQQ 등): 해외 → yfinance
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
    # 6자리 한국 종목코드: 영숫자이면서 숫자를 1개 이상 포함
    # ("069500" 전부 숫자, "0148J0" 숫자+영문 신형 코드 모두 매칭.
    #  SPY/QQQ 같은 순수 알파벳 티커는 숫자가 없어 제외됨)
    if len(c) == 6 and c.isalnum() and any(ch.isdigit() for ch in c):
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
