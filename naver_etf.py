"""한국 ETF 데이터 수집 (네이버 금융).

소스:
- 리스트: https://finance.naver.com/api/sise/etfItemList.nhn (JSON, EUC-KR)
- 상세:  https://finance.naver.com/item/main.naver?code=XXXXXX
- 구성종목 전체: /item/coinfo.naver?code=XXXXXX&target=cu_more
"""
import json
import requests
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

NAVER_ETF_LIST_API = "https://finance.naver.com/api/sise/etfItemList.nhn"
NAVER_ETF_DETAIL = "https://finance.naver.com/item/main.naver"
NAVER_ETF_COINFO = "https://finance.naver.com/item/coinfo.naver"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TIMEOUT = 15

CATEGORY_MAP = {
    0: "전체",
    1: "국내시장지수",
    2: "국내업종/테마",
    3: "국내파생",
    4: "해외주식",
    5: "원자재",
    6: "채권",
    7: "기타",
}


def get_naver_etf_list(category: int = 0,
                      sort_by: str = "market_sum",
                      sort_order: str = "desc") -> List[Dict]:
    """네이버 ETF 리스트 전체 조회.

    Args:
        category: 0(전체), 1~7 카테고리
        sort_by: market_sum, changeRate, quant 등
        sort_order: desc / asc

    Returns:
        리스트 of dict {itemcode, itemname, nowVal, changeRate, nav,
                       threeMonthEarnRate, quant, amonut, marketSum, etfTabCode}
    """
    resp = requests.get(
        NAVER_ETF_LIST_API,
        params={
            "etfType": category,
            "targetColumn": sort_by,
            "sortOrder": sort_order,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    # 네이버 ETF API는 EUC-KR
    data = json.loads(resp.content.decode("euc-kr"))
    if data.get("resultCode") != "success":
        return []
    return data.get("result", {}).get("etfItemList", [])


def get_naver_etf_detail(code: str) -> Dict:
    """단일 한국 ETF 상세 정보 (HTML 파싱).

    Returns: {code, name, price, nav, fee, underlying_index,
              holdings_top, ...}
    """
    resp = requests.get(
        NAVER_ETF_DETAIL,
        params={"code": code},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    soup = BeautifulSoup(resp.text, "lxml")

    result = {
        "code": code,
        "source": "naver",
        "name": None,
        "price": None,
        "holdings_top": [],
        "nav_history": [],
    }

    # 종목명
    title = soup.select_one(".wrap_company h2 a")
    if title:
        result["name"] = title.get_text(strip=True)

    # 현재가 (블링크 제거된 값)
    price_tag = soup.select_one(".no_today .blind")
    if price_tag:
        try:
            result["price"] = int(price_tag.get_text().replace(",", ""))
        except ValueError:
            pass

    # 구성종목 TOP (table.tb_type1 중 구성종목 섹션)
    # TODO Phase 2: 구성종목 파싱 정교화
    # 현재는 링크 기반으로 스텁 반환
    for a in soup.select("a[href*='main.naver?code=']")[:15]:
        stock_code = a.get("href", "").split("code=")[-1]
        if stock_code and stock_code != code and stock_code.isdigit():
            result["holdings_top"].append({
                "code": stock_code,
                "name": a.get_text(strip=True),
            })

    return result


def get_naver_etf_holdings_full(code: str) -> List[Dict]:
    """한국 ETF 전체 구성종목 (coinfo 더보기 페이지).

    TODO Phase 2: coinfo 페이지 파싱
    """
    resp = requests.get(
        NAVER_ETF_COINFO,
        params={"code": code, "target": "cu_more"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    # TODO 파싱 로직
    return []
