"""포트폴리오 추천 엔진 (블랙박스).

🔒 이 모듈의 내부 로직은 MCP로 직접 노출 X.
    외부에는 `recommend()` 최종 결과만 제공.

추천 방식: 규칙 기반 (Core-Satellite + 리스크별 자산배분)
상세 구현은 Phase 3.
"""
from typing import Dict, List, Optional

# 리스크 유형별 자산 배분
RISK_PROFILES = {
    "conservative": {"equity": 0.30, "bond": 0.50, "alternative": 0.20},
    "balanced":     {"equity": 0.60, "bond": 0.30, "alternative": 0.10},
    "aggressive":   {"equity": 0.80, "bond": 0.10, "alternative": 0.10},
}

# Core-Satellite 분할
CORE_WEIGHT = 0.70
SATELLITE_WEIGHT = 0.30

# 후보 ETF 필터 기준
MIN_AUM_KR = 1000  # 억원
MIN_AUM_US = 1e9   # USD
MAX_EXPENSE_PCT = 0.30
MIN_DAYS_LISTED = 365


def recommend(
    risk: str = "balanced",
    amount_krw: int = 500000,
    horizon_years: int = 10,
    theme: Optional[str] = None,
    market_mix: str = "global",
) -> Dict:
    """포트폴리오 추천 메인 엔트리.

    Args:
        risk: conservative / balanced / aggressive
        amount_krw: 월 투자액 (원)
        horizon_years: 투자 기간 (년)
        theme: 선호 테마 (반도체/배당/AI/리츠 등)
        market_mix: global (한·미 혼합) / kr_only / us_only

    Returns:
        포트폴리오 구성 + 지표 + 면책 문구
    """
    allocation = RISK_PROFILES.get(risk, RISK_PROFILES["balanced"])

    # TODO Phase 3: 실제 ETF 선택 로직
    return {
        "status": "stub",
        "message": "Portfolio engine will be implemented in Phase 3",
        "inputs": {
            "risk": risk,
            "amount_krw": amount_krw,
            "horizon_years": horizon_years,
            "theme": theme,
            "market_mix": market_mix,
        },
        "allocation_target": allocation,
        "disclaimer": (
            "본 서비스는 정보 제공 목적이며 투자 자문이 아닙니다. "
            "최종 투자 판단은 본인 책임입니다."
        ),
    }


def _validate_portfolio(portfolio: List[Dict]) -> Dict:
    """포트폴리오 자동 검증 (TODO Phase 3).

    - 단일종목 노출 <= 15%
    - 섹터 집중도 <= 40%
    - ETF 중복 구성종목 Jaccard <= 0.7
    - 가중평균 보수 <= 0.25%
    """
    return {"valid": True, "warnings": []}
