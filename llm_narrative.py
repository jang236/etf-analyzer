"""LLM 기반 한국어 설명 생성 (Gemini).

🔒 규칙 엔진이 생성한 숫자/구조화 결과를 자연어로 재구성.
    LLM 자체엔 투자 로직을 맡기지 않음 (신뢰성·재현성 유지).

GEMINI_API_KEY 미설정 시: 템플릿 기반 fallback.
API 오류 시: 조용히 fallback.
"""
import os
from typing import Dict, List, Optional

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# LLM 호출 여부 (import 시점에 결정)
try:
    if GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _LLM_AVAILABLE = True
        _MODEL_NAME = "gemini-2.0-flash"  # 빠르고 저렴
    else:
        _LLM_AVAILABLE = False
except ImportError:
    _LLM_AVAILABLE = False


DISCLAIMER_HEADER = (
    "※ 본 설명은 정보 제공 목적이며 투자 자문이 아닙니다.\n\n"
)


def _llm_call(prompt: str, max_tokens: int = 600) -> Optional[str]:
    """Gemini 호출. 실패 시 None."""
    if not _LLM_AVAILABLE:
        return None
    try:
        model = genai.GenerativeModel(_MODEL_NAME)
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": 0.4,  # 일관성 위주
            },
        )
        return response.text.strip()
    except Exception:
        return None


# ─────────────────────────────────────────────
# explain_etf: 단일 ETF 설명 + 장단점
# ─────────────────────────────────────────────
def explain_etf(etf_data: Dict) -> str:
    """ETF 상세 데이터를 한국어로 설명."""
    source = etf_data.get("source", "")
    name = etf_data.get("name") or etf_data.get("code", "Unknown")

    # 템플릿 fallback
    template = _template_etf(etf_data)

    if not _LLM_AVAILABLE:
        return DISCLAIMER_HEADER + template

    # LLM 호출 — 구조화 데이터를 자연어로 풀어쓰기
    if source == "naver":
        prompt = _prompt_kr_etf(etf_data)
    else:
        prompt = _prompt_us_etf(etf_data)

    llm_text = _llm_call(prompt)
    return DISCLAIMER_HEADER + (llm_text or template)


def _template_etf(etf_data: Dict) -> str:
    """LLM 없을 때 기본 설명 (사실만 나열)."""
    parts = []
    name = etf_data.get("name") or etf_data.get("symbol") or etf_data.get("code", "")
    parts.append(f"【{name}】")

    if etf_data.get("source") == "naver":
        if etf_data.get("underlying_index"):
            parts.append(f"기초지수: {etf_data['underlying_index']}")
        if etf_data.get("asset_manager"):
            parts.append(f"운용사: {etf_data['asset_manager']}")
        if etf_data.get("expense_info"):
            parts.append(f"펀드보수: {etf_data['expense_info']}")
        if etf_data.get("market_cap"):
            parts.append(f"시가총액: {etf_data['market_cap']}")
        periods = etf_data.get("period_returns", {})
        if periods:
            parts.append(f"수익률 (1M/3M/1Y): {periods.get('1M','-')} / {periods.get('3M','-')} / {periods.get('1Y','-')}")
        if etf_data.get("holdings_top"):
            top = etf_data["holdings_top"][:5]
            top_str = ", ".join(f"{h['name']}({h['weight_pct']}%)" for h in top)
            parts.append(f"주요 구성종목: {top_str}")
        if etf_data.get("overview"):
            parts.append(f"개요: {etf_data['overview'][:200]}")
    else:
        if etf_data.get("expense_ratio_pct") is not None:
            parts.append(f"총보수: {etf_data['expense_ratio_pct']}%")
        if etf_data.get("dividend_yield_pct"):
            parts.append(f"배당수익률: {etf_data['dividend_yield_pct']}%")
        if etf_data.get("aum_usd"):
            aum_b = etf_data["aum_usd"] / 1e9
            parts.append(f"순자산: ${aum_b:.1f}B")
        if etf_data.get("category"):
            parts.append(f"카테고리: {etf_data['category']}")
        if etf_data.get("ytd_return_pct") is not None:
            parts.append(f"YTD 수익률: {etf_data['ytd_return_pct']}%")

    return "\n".join(parts)


def _prompt_kr_etf(data: Dict) -> str:
    periods = data.get("period_returns", {})
    top_holdings = data.get("holdings_top", [])[:5]
    top_str = ", ".join(f"{h['name']} {h['weight_pct']}%" for h in top_holdings)

    return f"""다음은 한국 상장 ETF의 구조화된 데이터입니다. 투자자 관점에서 한국어로 설명해주세요.
설명에는 (1) 이 ETF의 성격, (2) 장점, (3) 단점/주의사항, (4) 어떤 투자자에게 적합한지를 포함하세요.
과장된 추천 표현(꼭 사세요, 추천 등)은 사용하지 마세요. 400자 내외로 간결하게.

ETF명: {data.get('name', '')}
기초지수: {data.get('underlying_index', 'N/A')}
운용사: {data.get('asset_manager', 'N/A')}
펀드보수: {data.get('expense_info', 'N/A')}
시가총액: {data.get('market_cap', 'N/A')}
수익률(1M/3M/6M/1Y): {periods.get('1M','-')}/{periods.get('3M','-')}/{periods.get('6M','-')}/{periods.get('1Y','-')}
주요 구성종목: {top_str}
유형: {data.get('fund_type', 'N/A')}
개요: {(data.get('overview') or '')[:300]}
"""


def _prompt_us_etf(data: Dict) -> str:
    aum_b = (data.get('aum_usd') or 0) / 1e9
    return f"""Below is structured data for a US-listed ETF. Explain in KOREAN (한국어) for a retail investor.
Include: (1) what this ETF is, (2) pros, (3) cons/cautions, (4) suitable investor profile.
Avoid overly promotional language. Be concise, around 400 Korean characters.

ETF: {data.get('name', '')} ({data.get('symbol', '')})
Expense ratio: {data.get('expense_ratio_pct', 'N/A')}%
Dividend yield: {data.get('dividend_yield_pct', 'N/A')}%
AUM: ${aum_b:.1f}B
Category: {data.get('category', 'N/A')}
Fund family: {data.get('fund_family', 'N/A')}
YTD return: {data.get('ytd_return_pct', 'N/A')}%
3Y avg return: {data.get('three_year_avg_return_pct', 'N/A')}%
Summary: {(data.get('summary_en') or '')[:400]}
"""


# ─────────────────────────────────────────────
# explain_comparison: 여러 ETF 비교 해설
# ─────────────────────────────────────────────
def explain_comparison(comparison_result: Dict) -> str:
    """compare_etfs() 결과를 해설."""
    items = comparison_result.get("comparison", [])
    overlap = comparison_result.get("holdings_overlap", [])

    template = _template_comparison(items, overlap)
    if not _LLM_AVAILABLE:
        return DISCLAIMER_HEADER + template

    prompt = f"""다음은 여러 ETF의 비교 데이터입니다. 한국어로 해설해주세요.
특히: (1) 유사/차이점, (2) 각각의 적합한 시나리오, (3) 구성종목 중복도가 높으면 분산 효과 제한 언급.
과도한 승자 판정보다 투자자가 직접 판단할 수 있는 정보를 제공하세요. 500자 내외.

ETF 데이터:
{items}

구성종목 중복도 (Jaccard):
{overlap}
"""
    llm_text = _llm_call(prompt, max_tokens=800)
    return DISCLAIMER_HEADER + (llm_text or template)


def _template_comparison(items: List[Dict], overlap: List[Dict]) -> str:
    lines = ["【ETF 비교】\n"]
    for it in items:
        name = it.get("name") or it.get("code")
        price = it.get("price")
        market = it.get("market")
        fee = it.get("expense_info") or (f"{it.get('expense_ratio_pct')}%" if it.get('expense_ratio_pct') else "?")
        lines.append(f"- {name} ({market}): 가격 {price} / 보수 {fee}")
    if overlap:
        lines.append("\n구성종목 중복도 (높을수록 분산 효과 제한):")
        for o in overlap:
            pair = " vs ".join(o["pair"])
            j = o.get("jaccard_similarity")
            lines.append(f"  {pair}: {j if j is not None else '(데이터 부족)'}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# explain_portfolio: 포트폴리오 해설
# ─────────────────────────────────────────────
def explain_portfolio(portfolio_result: Dict) -> str:
    """recommend() 결과를 해설."""
    template = _template_portfolio(portfolio_result)
    if not _LLM_AVAILABLE:
        return DISCLAIMER_HEADER + template

    inputs = portfolio_result.get("inputs", {})
    portfolio = portfolio_result.get("portfolio", [])
    metrics = portfolio_result.get("metrics", {})
    warnings = portfolio_result.get("warnings", [])

    prompt = f"""다음은 사용자 프로필 기반으로 구성된 ETF 포트폴리오 예시입니다.
한국어로 해설해주세요. 포함할 내용: (1) 구성 이유, (2) 각 ETF의 역할, (3) 주의사항, (4) 리밸런싱 팁.
추천/자문 단어 피하고 "예시", "정보" 등 중립적 표현 사용. 600자 내외.

사용자 프로필: {inputs}
목표 자산배분: {portfolio_result.get('target_allocation', {})}
포트폴리오:
{portfolio}

지표: {metrics}
경고: {warnings}
"""
    llm_text = _llm_call(prompt, max_tokens=1000)
    return DISCLAIMER_HEADER + (llm_text or template)


def _template_portfolio(r: Dict) -> str:
    lines = ["【포트폴리오 예시】"]
    lines.append(f"프로필: 리스크 {r['inputs']['risk']}, 월 {r['inputs']['amount_krw']:,}원, "
                 f"{r['inputs']['horizon_years']}년, 시장 {r['inputs']['market_mix']}")
    lines.append("")
    for p in r.get("portfolio", []):
        lines.append(f"- {p['name']} ({p['code']}): {p['weight_pct']}% "
                     f"→ {p.get('allocated_amount_krw', 0):,}원 [{p['role']}]")
    m = r.get("metrics", {})
    lines.append("")
    lines.append(f"가중평균 보수: {m.get('weighted_expense_ratio_pct', '-')}%")
    lines.append(f"시장 분산: KR {m.get('market_distribution', {}).get('kr_pct', 0)}% / US {m.get('market_distribution', {}).get('us_pct', 0)}%")
    if r.get("warnings"):
        lines.append(f"주의: {'; '.join(r['warnings'])}")
    return "\n".join(lines)


def is_available() -> bool:
    """LLM 사용 가능 여부."""
    return _LLM_AVAILABLE
