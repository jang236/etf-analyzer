"""한국 ETF 데이터 수집 (네이버 금융).

소스:
- 리스트 JSON: https://finance.naver.com/api/sise/etfItemList.nhn (EUC-KR)
- 상세 HTML:   https://finance.naver.com/item/main.naver?code=XXXXXX
- 구성종목 전체: /item/coinfo.naver?code=XXXXXX&target=cu_more
"""
import json
import re
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
    """네이버 ETF 리스트 전체 조회."""
    resp = requests.get(
        NAVER_ETF_LIST_API,
        params={"etfType": category, "targetColumn": sort_by, "sortOrder": sort_order},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    data = json.loads(resp.content.decode("euc-kr"))
    if data.get("resultCode") != "success":
        return []
    items = data.get("result", {}).get("etfItemList", [])
    # 카테고리 레이블 추가
    for it in items:
        it["category_name"] = CATEGORY_MAP.get(it.get("etfTabCode"), "기타")
    return items


def _parse_int(text: str) -> Optional[int]:
    if not text:
        return None
    try:
        return int(re.sub(r"[^0-9\-]", "", text))
    except ValueError:
        return None


def _parse_float(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"-?\d+\.?\d*", text.replace(",", ""))
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


def get_naver_etf_detail(code: str) -> Dict:
    """단일 한국 ETF 상세 정보.

    Returns:
        {code, name, price, change_amount, change_rate,
         nav, market_cap, listed_shares, underlying_index,
         asset_manager, listing_date, fund_type, expense_info,
         period_returns: {1M, 3M, 6M, 1Y},
         holdings_top: [...], nav_history: [...], overview}
    """
    resp = requests.get(
        NAVER_ETF_DETAIL,
        params={"code": code},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    # 네이버 상세 페이지는 UTF-8
    soup = BeautifulSoup(resp.content, "lxml", from_encoding="utf-8")

    result = {
        "code": code,
        "source": "naver",
        "name": None,
        "price": None,
        "change_amount": None,
        "change_rate": None,
        "nav": None,
        "market_cap": None,
        "listed_shares": None,
        "underlying_index": None,
        "asset_manager": None,
        "listing_date": None,
        "expense_info": None,
        "holdings_top": [],
        "nav_history": [],
        "overview": None,
    }

    # 종목명
    title = soup.select_one(".wrap_company h2 a")
    if title:
        result["name"] = title.get_text(strip=True)

    # 현재가
    price_tag = soup.select_one(".no_today .blind")
    if price_tag:
        result["price"] = _parse_int(price_tag.get_text())

    # 전일비·등락률 (에서 no_exday .blind 2개가 보통)
    exday_blinds = soup.select(".no_exday .blind")
    if len(exday_blinds) >= 2:
        result["change_amount"] = _parse_int(exday_blinds[0].get_text())
        result["change_rate"] = _parse_float(exday_blinds[1].get_text())

    # ─────────────────────────────────────
    # 구성종목 (table.tb_type1_a)
    # ─────────────────────────────────────
    holdings_table = soup.select_one("table.tb_type1_a")
    if holdings_table:
        for tr in holdings_table.select("tbody tr"):
            cells = tr.select("td")
            if len(cells) < 6:
                continue
            link = tr.select_one("a[href*='code=']")
            if not link:
                continue
            href = link.get("href", "")
            stock_code_m = re.search(r"code=(\d+)", href)
            if not stock_code_m:
                continue
            stock_code = stock_code_m.group(1)
            if stock_code == code:  # 자기 자신 제외
                continue
            name = link.get_text(strip=True)
            shares = _parse_int(cells[1].get_text())
            weight_pct = _parse_float(cells[2].get_text())
            price = _parse_int(cells[3].get_text())
            change_rate = _parse_float(cells[5].get_text())
            result["holdings_top"].append({
                "code": stock_code,
                "name": name,
                "shares": shares,
                "weight_pct": weight_pct,
                "price": price,
                "change_rate": change_rate,
            })
            # 중복 제거 (첫 발견만 유지)
            seen_codes = set()
            deduped = []
            for h in result["holdings_top"]:
                if h["code"] not in seen_codes:
                    seen_codes.add(h["code"])
                    deduped.append(h)
            result["holdings_top"] = deduped[:10]  # TOP 10만

    # ─────────────────────────────────────
    # NAV 추이 (table.tb_type1 within section etf_nav)
    # ─────────────────────────────────────
    nav_section = soup.select_one(".etf_nav")
    if nav_section:
        nav_table = nav_section.select_one("table.tb_type1")
        if nav_table:
            for tr in nav_table.select("tbody tr"):
                cells = tr.select("td")
                if len(cells) >= 4:
                    texts = [c.get_text(strip=True) for c in cells]
                    if texts[0] and re.match(r"\d{4}\.\d{2}\.\d{2}", texts[0]):
                        result["nav_history"].append({
                            "date": texts[0],
                            "close": _parse_int(texts[1]),
                            "nav": _parse_float(texts[2]),
                            "deviation_pct": _parse_float(texts[3]),
                        })
            result["nav_history"] = result["nav_history"][:5]

    # ─────────────────────────────────────
    # 개요 (summary_info)
    # ─────────────────────────────────────
    summary = soup.select_one(".summary_info")
    if summary:
        txt = summary.get_text(separator=" ", strip=True)
        txt = re.sub(r"^ETF개요\s*", "", txt)
        txt = re.sub(r"출처\s*:\s*[가-힣A-Za-z]+$", "", txt).strip()
        result["overview"] = re.sub(r"\s+", " ", txt)[:500]

    # ─────────────────────────────────────
    # 메타 정보 (aside_invest_info — 여러 table의 th/td 페어)
    # ─────────────────────────────────────
    aside = soup.select_one(".aside_invest_info")
    result["period_returns"] = {}

    if aside:
        for table in aside.select("table"):
            for tr in table.select("tr"):
                th = tr.select_one("th")
                td = tr.select_one("td")
                if not (th and td):
                    continue
                label = re.sub(r"\s+", " ", th.get_text(strip=True))
                value = re.sub(r"\s+", " ", td.get_text(strip=True))
                if not label or not value:
                    continue

                # 레이블 매핑
                if label == "기초지수":
                    result["underlying_index"] = value
                elif label == "자산운용사":
                    result["asset_manager"] = value
                elif label == "상장일":
                    result["listing_date"] = value
                elif label == "시가총액":
                    result["market_cap"] = value
                elif label == "상장주식수":
                    result["listed_shares"] = _parse_int(value)
                elif label == "유형":
                    result["fund_type"] = value
                elif label == "NAV" and result["nav"] is None:
                    result["nav"] = _parse_float(value)
                elif "수익률" in label:
                    # "1개월 수익률" → "1M", etc.
                    short = (label.replace("수익률", "").strip()
                             .replace("개월", "M").replace("년", "Y"))
                    result["period_returns"][short] = value

        # 펀드보수: aside 텍스트에서 "0.XX%" 패턴 (자산운용사 앞에 위치)
        aside_text = aside.get_text(separator="|", strip=True)
        fee_match = re.search(r"(\d+\.\d+)\s*%\s*\|\s*자산운용사", aside_text)
        if not fee_match:
            fee_match = re.search(r"펀드보수.*?(\d+\.\d+\s*%)", aside_text)
        if fee_match:
            result["expense_info"] = fee_match.group(1) + ("%" if "%" not in fee_match.group(1) else "")

    return result


def get_naver_etf_holdings_full(code: str) -> List[Dict]:
    """한국 ETF 전체 구성종목 (coinfo 더보기 페이지).

    Returns: 전체 구성종목 리스트.
    """
    resp = requests.get(
        NAVER_ETF_COINFO,
        params={"code": code, "target": "cu_more"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "lxml")

    holdings = []
    # coinfo 페이지는 iframe 구조일 수 있음 → 직접 파싱 시도
    for table in soup.select("table.tb_type1_a, table.tb_type1"):
        headers = [th.get_text(strip=True) for th in table.select("th")]
        if "구성종목" in " ".join(headers) or "구성자산" in " ".join(headers):
            for tr in table.select("tbody tr"):
                cells = tr.select("td")
                if len(cells) < 3:
                    continue
                link = tr.select_one("a[href*='code=']")
                if not link:
                    continue
                href = link.get("href", "")
                m = re.search(r"code=(\d+)", href)
                if not m:
                    continue
                stock_code = m.group(1)
                if stock_code == code:
                    continue
                holdings.append({
                    "code": stock_code,
                    "name": link.get_text(strip=True),
                    "shares": _parse_int(cells[1].get_text()) if len(cells) > 1 else None,
                    "weight_pct": _parse_float(cells[2].get_text()) if len(cells) > 2 else None,
                })
            break  # 첫 번째 구성종목 테이블만
    return holdings
