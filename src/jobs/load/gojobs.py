"""나라일터(인사혁신처) — 국가기관·지자체·교육청 직접 채용 공고.

``gojobs.go.kr`` aggregates direct hiring by public bodies, including 국가기관
환경미화·청사미화 and 지자체 공무직 cleaning roles (no staffing agencies).

Verified flow
-------------
The landing page renders no rows and ``fn_apmList`` is undefined until you enter
through the menu, so reproduce that:

1. GET  apmList.do?menuNo=401&selMenuNo=400&wd=1000   (session + context)
2. POST apmList.do  with the full ``listForm`` fields, ``searchKeyword``,
   ``pageIndex`` and the work-area codes below. The response is server-rendered.

Work area is filtered server-side via ``searchWorkareacode`` (a 시군구 code from
``setGunCode.do``; the parent 시도 code goes in ``serachAreaClassCd``). Note the
시군구 codes are *not* hierarchical — 창원시 의창구/성산구 each carry their own
postings, so query them separately.

Row links are ``href="javascript:fn_apmView('<jobsecode>','<empmnsn>')"``;
detail pages are ``GET apmView.do?empmnsn=<id>``.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

from selectolax.lexbor import LexborHTMLParser

from ._http import clean, client, fetch, html_to_text, iso_date

LIST_URL = "https://www.gojobs.go.kr/apmList.do"
DETAIL_URL = "https://www.gojobs.go.kr/apmView.do"
GUNCODE_URL = "https://www.gojobs.go.kr/setGunCode.do"
WARMUP_URL = f"{LIST_URL}?menuNo=401&selMenuNo=400&wd=1000"

SIDO_GYEONGNAM = "48000"
DEFAULT_AREAS = ("48121", "48123")  # 창원시 의창구, 창원시 성산구

_VIEW = re.compile(r"fn_apmView\('([^']*)',\s*'?(\d+)'?\)")

_FORM = {
    "flag": "",
    "searchDetail": "",
    "searchJobsecode": "020",
    "searchEmpmnsecode": "",
    "recentEmploy": "",
    "empmnsn": "0",
    "employStep": "",
    "prgl": "apmList",
    "searchWorkareaname": "",
    "areanm": "",
    "menuNo": "401",
    "selMenuNo": "400",
    "upperMenuNo": "",
    "wd": "1000",
    "isShowBtn": "N",
    "listViewYn": "Y",
    "searchSdate": "",
    "searchEdate": "",
    "searchPeriod": "find",
    "searchWorkareacode": "",
    "serachAreaClassCd": SIDO_GYEONGNAM,
    "searchType": "",
    "searchOrdr": "",
    "searchSelectninsttnm": "",
    "detailKeyword": "",
}


def _area_names(http, sido: str, codes: tuple[str, ...]) -> dict[str, str]:
    """Map 시군구 codes to the exact names the search backend requires."""
    mapping: dict[str, str] = {}
    resp = fetch(http, "POST", GUNCODE_URL, data={"code": sido})
    if resp is not None:
        try:
            for item in resp.json().get("gunCode", []):
                mapping[item["code"]] = item.get("codeNm") or item.get("codeFullNm") or ""
        except Exception:
            mapping = {}
    return {code: mapping.get(code, "") for code in codes}


def rows(
    keyword: str = "청소",
    areas: tuple[str, ...] = DEFAULT_AREAS,
    max_pages: int = 10,
    delay: float = 1.0,
    skip_keys: set[int] | None = None,
    seen_keys: set[int] | None = None,
) -> Iterator[dict]:
    seen: set[int] = set()
    skip = skip_keys or set()
    with client(referer=WARMUP_URL) as http:
        if fetch(http, "GET", WARMUP_URL) is None:
            return
        names = _area_names(http, SIDO_GYEONGNAM, areas)
        for area in areas:
            name = names.get(area)
            if not name:  # without the exact name the backend ignores the filter
                continue
            for page in range(1, max_pages + 1):
                resp = fetch(
                    http,
                    "POST",
                    LIST_URL,
                    data={
                        **_FORM,
                        "searchKeyword": keyword,
                        "pageIndex": str(page),
                        "serachAreaClassCd": SIDO_GYEONGNAM,
                        "searchWorkareacode": area,
                        "searchWorkareaname": name,
                    },
                )
                if resp is None:
                    break
                page_rows = _parse_rows(resp.text)
                if not page_rows:
                    break
                if seen_keys is not None:
                    seen_keys.update(row["key"] for row in page_rows)
                for row in page_rows:
                    if row["key"] in skip or row["key"] in seen:
                        continue
                    seen.add(row["key"])
                    yield row
                # Newest-first list: stop once a whole page is already known.
                if skip and all(row["key"] in skip for row in page_rows):
                    break
                if page < max_pages:
                    time.sleep(delay)


def _parse_rows(html: str) -> list[dict]:
    tree = LexborHTMLParser(html)
    out: list[dict] = []
    for tr in tree.css("tr"):
        anchor = tr.css_first("a")
        if anchor is None:
            continue
        found = _VIEW.search(anchor.attributes.get("href") or "")
        if not found:
            continue
        cells = [clean(td.text(strip=True)) for td in tr.css("td")]
        if len(cells) < 5:
            continue
        empmnsn = int(found.group(2))
        out.append(
            {
                "source": "gojobs",
                "key": empmnsn,
                "title": clean(anchor.text(strip=True)),
                "url": f"{DETAIL_URL}?empmnsn={empmnsn}",
                "posted_on": iso_date(cells[3]),
                "closes_on": iso_date(cells[4]),
                "institution": cells[2],
            }
        )
    return out


def detail(http, empmnsn: int) -> dict:
    resp = http.get(DETAIL_URL, params={"empmnsn": empmnsn})
    resp.raise_for_status()
    tree = LexborHTMLParser(resp.text)

    fields: dict[str, str] = {}
    table = tree.css_first("#apmViewTbl")
    if table is not None:
        for tr in table.css("tr"):
            headers = tr.css("th")
            cells = tr.css("td")
            if headers and cells:
                fields[clean(headers[0].text()) or ""] = clean(cells[0].text())

    body_node = tree.css_first("textarea#content")
    return {
        "posted_on": iso_date(fields.get("등록일") or fields.get("공고게시일")),
        "closes_on": iso_date(fields.get("접수마감일")),
        "body": html_to_text(body_node.text() if body_node is not None else None),
    }
