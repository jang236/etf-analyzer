"""해외 ETF 큐레이션 시드 리스트 (100+개).

Phase 1~4 동안 시작점. 네이버처럼 "전체 리스트 API"가 없는 yfinance를 위해
주요 미국 ETF를 카테고리별로 큐레이션.
"""

CURATED_US_ETFS = [
    # ═══ Core (광범위 시장, 10) ═══
    {"symbol": "SPY", "category": "core_us", "name_hint": "S&P 500"},
    {"symbol": "VOO", "category": "core_us", "name_hint": "S&P 500 (Vanguard)"},
    {"symbol": "IVV", "category": "core_us", "name_hint": "S&P 500 (iShares)"},
    {"symbol": "QQQ", "category": "core_us", "name_hint": "NASDAQ 100"},
    {"symbol": "VTI", "category": "core_us", "name_hint": "Total US Market"},
    {"symbol": "DIA", "category": "core_us", "name_hint": "Dow Jones"},
    {"symbol": "MDY", "category": "core_us", "name_hint": "S&P MidCap"},
    {"symbol": "IWM", "category": "core_us", "name_hint": "Russell 2000"},
    {"symbol": "VEA", "category": "core_intl", "name_hint": "Developed ex-US"},
    {"symbol": "VWO", "category": "core_intl", "name_hint": "Emerging Markets"},

    # ═══ Sector (섹터, 11) ═══
    {"symbol": "XLK", "category": "sector", "name_hint": "Technology"},
    {"symbol": "XLF", "category": "sector", "name_hint": "Financials"},
    {"symbol": "XLV", "category": "sector", "name_hint": "Healthcare"},
    {"symbol": "XLE", "category": "sector", "name_hint": "Energy"},
    {"symbol": "XLI", "category": "sector", "name_hint": "Industrials"},
    {"symbol": "XLY", "category": "sector", "name_hint": "Consumer Discretionary"},
    {"symbol": "XLP", "category": "sector", "name_hint": "Consumer Staples"},
    {"symbol": "XLU", "category": "sector", "name_hint": "Utilities"},
    {"symbol": "XLRE", "category": "sector", "name_hint": "Real Estate"},
    {"symbol": "XLB", "category": "sector", "name_hint": "Materials"},
    {"symbol": "XLC", "category": "sector", "name_hint": "Communication"},

    # ═══ Theme (테마, 15) ═══
    {"symbol": "ARKK", "category": "theme", "name_hint": "Innovation (ARK)"},
    {"symbol": "ARKW", "category": "theme", "name_hint": "Next Gen Internet"},
    {"symbol": "ARKG", "category": "theme", "name_hint": "Genomics"},
    {"symbol": "SOXX", "category": "theme", "name_hint": "Semiconductors"},
    {"symbol": "SMH", "category": "theme", "name_hint": "Semiconductor ETF"},
    {"symbol": "ICLN", "category": "theme", "name_hint": "Clean Energy"},
    {"symbol": "LIT", "category": "theme", "name_hint": "Lithium & Battery"},
    {"symbol": "HACK", "category": "theme", "name_hint": "Cybersecurity"},
    {"symbol": "IBB", "category": "theme", "name_hint": "Biotech"},
    {"symbol": "XBI", "category": "theme", "name_hint": "Biotech (SPDR)"},
    {"symbol": "BOTZ", "category": "theme", "name_hint": "Robotics & AI"},
    {"symbol": "ROBO", "category": "theme", "name_hint": "Robotics"},
    {"symbol": "KWEB", "category": "theme", "name_hint": "China Internet"},
    {"symbol": "FINX", "category": "theme", "name_hint": "Fintech"},
    {"symbol": "BLOK", "category": "theme", "name_hint": "Blockchain"},

    # ═══ Dividend (배당, 6) ═══
    {"symbol": "SCHD", "category": "dividend", "name_hint": "Dividend Equity"},
    {"symbol": "VYM", "category": "dividend", "name_hint": "High Dividend"},
    {"symbol": "HDV", "category": "dividend", "name_hint": "Core Dividend"},
    {"symbol": "DVY", "category": "dividend", "name_hint": "Select Dividend"},
    {"symbol": "SPYD", "category": "dividend", "name_hint": "S&P 500 Dividend"},
    {"symbol": "NOBL", "category": "dividend", "name_hint": "Aristocrats"},

    # ═══ International (국제, 10) ═══
    {"symbol": "EFA", "category": "intl", "name_hint": "MSCI EAFE"},
    {"symbol": "IEFA", "category": "intl", "name_hint": "Core MSCI EAFE"},
    {"symbol": "EEM", "category": "intl", "name_hint": "MSCI Emerging"},
    {"symbol": "IEMG", "category": "intl", "name_hint": "Core Emerging"},
    {"symbol": "VXUS", "category": "intl", "name_hint": "Total International"},
    {"symbol": "ACWI", "category": "intl", "name_hint": "MSCI ACWI"},
    {"symbol": "EWJ", "category": "intl", "name_hint": "Japan"},
    {"symbol": "EWG", "category": "intl", "name_hint": "Germany"},
    {"symbol": "EWY", "category": "intl", "name_hint": "South Korea"},
    {"symbol": "FXI", "category": "intl", "name_hint": "China Large-Cap"},

    # ═══ Bond (채권, 10) ═══
    {"symbol": "AGG", "category": "bond", "name_hint": "Core US Aggregate"},
    {"symbol": "BND", "category": "bond", "name_hint": "Total Bond (Vanguard)"},
    {"symbol": "TLT", "category": "bond", "name_hint": "20+ Year Treasury"},
    {"symbol": "IEF", "category": "bond", "name_hint": "7-10 Year Treasury"},
    {"symbol": "SHY", "category": "bond", "name_hint": "1-3 Year Treasury"},
    {"symbol": "LQD", "category": "bond", "name_hint": "Investment Grade Corp"},
    {"symbol": "HYG", "category": "bond", "name_hint": "High Yield Corp"},
    {"symbol": "JNK", "category": "bond", "name_hint": "High Yield (SPDR)"},
    {"symbol": "MUB", "category": "bond", "name_hint": "Muni Bond"},
    {"symbol": "TIP", "category": "bond", "name_hint": "TIPS"},

    # ═══ Commodity / Alternative (원자재·대체, 6) ═══
    {"symbol": "GLD", "category": "commodity", "name_hint": "Gold"},
    {"symbol": "SLV", "category": "commodity", "name_hint": "Silver"},
    {"symbol": "GLDM", "category": "commodity", "name_hint": "Gold (low cost)"},
    {"symbol": "USO", "category": "commodity", "name_hint": "Oil"},
    {"symbol": "DBC", "category": "commodity", "name_hint": "Diversified Commodity"},
    {"symbol": "VNQ", "category": "reit", "name_hint": "US Real Estate"},

    # ═══ Style/Factor (스타일/팩터, 10) ═══
    {"symbol": "VUG", "category": "factor", "name_hint": "Growth (Vanguard)"},
    {"symbol": "VTV", "category": "factor", "name_hint": "Value (Vanguard)"},
    {"symbol": "MTUM", "category": "factor", "name_hint": "Momentum"},
    {"symbol": "QUAL", "category": "factor", "name_hint": "Quality"},
    {"symbol": "USMV", "category": "factor", "name_hint": "Min Volatility"},
    {"symbol": "SCHG", "category": "factor", "name_hint": "Large Cap Growth"},
    {"symbol": "SCHV", "category": "factor", "name_hint": "Large Cap Value"},
    {"symbol": "IJR", "category": "factor", "name_hint": "Small Cap"},
    {"symbol": "IJH", "category": "factor", "name_hint": "Mid Cap"},
    {"symbol": "VBR", "category": "factor", "name_hint": "Small Cap Value"},

    # ═══ Leveraged/Inverse (레버리지/인버스, 10) ═══
    # ⚠️ 장기 보유 부적합. 추천 시 자동 경고 필요.
    {"symbol": "TQQQ", "category": "leveraged", "name_hint": "3x NASDAQ 100"},
    {"symbol": "SQQQ", "category": "inverse", "name_hint": "-3x NASDAQ 100"},
    {"symbol": "SOXL", "category": "leveraged", "name_hint": "3x Semiconductor"},
    {"symbol": "SOXS", "category": "inverse", "name_hint": "-3x Semiconductor"},
    {"symbol": "UPRO", "category": "leveraged", "name_hint": "3x S&P 500"},
    {"symbol": "SPXS", "category": "inverse", "name_hint": "-3x S&P 500"},
    {"symbol": "TNA", "category": "leveraged", "name_hint": "3x Small Cap"},
    {"symbol": "TZA", "category": "inverse", "name_hint": "-3x Small Cap"},
    {"symbol": "TMF", "category": "leveraged", "name_hint": "3x Long Treasury"},
    {"symbol": "TMV", "category": "inverse", "name_hint": "-3x Long Treasury"},
]


def get_by_category(category: str) -> list:
    """카테고리별 ETF 필터."""
    return [e for e in CURATED_US_ETFS if e["category"] == category]


def get_symbols_by_category(category: str) -> list:
    """카테고리별 심볼 리스트."""
    return [e["symbol"] for e in CURATED_US_ETFS if e["category"] == category]


def is_leveraged_or_inverse(symbol: str) -> bool:
    """레버리지/인버스 여부 (포트폴리오 추천 시 경고용)."""
    for e in CURATED_US_ETFS:
        if e["symbol"] == symbol:
            return e["category"] in ("leveraged", "inverse")
    return False
