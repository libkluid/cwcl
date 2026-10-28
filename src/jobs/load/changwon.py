"""창원시 통합 일자리 플랫폼 — "오늘의 채용정보".

``changwon.go.kr/cwportal/14605.web`` is the city's aggregated feed. It mixes
direct public hiring (국립마산검역소, 창원농업기술센터 등) with private listings,
so filter on 업직종/회사명/모집내용 for cleaning roles.

Verified flow
-------------
GET  /cwportal/14605.web?cpage=<n>            -> server-rendered ``table.t3``
GET  /cwportal/14605.web?amode=view&idx=<id>  -> detail page

Each ``tbody tr`` is 근무지 | 업직종 | 회사명/모집내용(a with .title/.txt) |
고용형태 | 급여 | 등록일 | 마감일. robots.txt sets ``Crawl-delay: 10`` for ``*``;
``/cwportal/...`` is allowed, so honour the delay.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

from selectolax.lexbor import LexborHTMLParser

from ._http import clean, client, fetch, html_to_text, iso_date

PAGE_URL = "https://www.changwon.go.kr/cwportal/14605.web"

_ENTRY = re.compile(r"idx=(\d+)")
_PAGEINFO = re.compile(r"\(\s*\d+\s*/\s*(\d+)\s*페이지\)")
DEFAULT_MATCH = ("청소", "미화", "환경")


def rows(
    max_pages: int | None = 5,
    delay: float = 10.0,
    match: tuple[str, ...] | None = DEFAULT_MATCH,
    skip_keys: set[int] | None = None,
    seen_keys: set[int] | None = None,
) -> Iterator[dict]:
    skip = skip_keys or set()
    with client(referer=PAGE_URL) as http:
        page = 1
        while max_pages is None or page <= max_pages:
            resp = fetch(http, "GET", PAGE_URL, params={"cpage": str(page)})
            if resp is None:
                break
            page_rows, total_pages = _parse_rows(resp.text)
            if not page_rows:
                break
            if seen_keys is not None:
                seen_keys.update(row["key"] for row in page_rows)
            for row in page_rows:
                if row["key"] in skip:
                    continue
                if match is None:
                    yield row
                    continue
                haystack = " ".join(
                    filter(None, (row.get("job_type"), row.get("company"), row.get("title")))
                )
                if any(needle in haystack for needle in match):
                    yield row
            # Newest-first list: stop once a whole page is already known.
            if skip and all(row["key"] in skip for row in page_rows):
                break
            if total_pages is not None and page >= total_pages:
                break
            page += 1
            time.sleep(delay)


def _parse_rows(html: str) -> tuple[list[dict], int | None]:
    tree = LexborHTMLParser(html)

    total_pages = None
    info = tree.css_first(".info1")
    if info is not None:
        found = _PAGEINFO.search(info.text())
        if found:
            total_pages = int(found.group(1))

    out: list[dict] = []
    for tr in tree.css("table.t3 tbody tr"):
        anchor = tr.css_first("a")
        if anchor is None:
            continue
        found = _ENTRY.search(anchor.attributes.get("href") or "")
        if not found:
            continue
        idx = int(found.group(1))
        cell = tr.css_first("th")
        tds = tr.css("td")
        title_node = anchor.css_first("p.title")
        text_node = anchor.css_first("p.txt")

        out.append(
            {
                "source": "changwon",
                "key": idx,
                "title": clean(text_node.text(strip=True)) if text_node else None,
                "url": f"{PAGE_URL}?amode=view&idx={idx}",
                "posted_on": iso_date(tds[4].text()) if len(tds) > 4 else None,
                "workplace": clean(cell.text(strip=True)) if cell is not None else None,
                "job_type": clean(tds[0].text(strip=True)) if len(tds) > 0 else None,
                "company": clean(title_node.text(strip=True)) if title_node else None,
                "closes_on": iso_date(tds[5].text()) if len(tds) > 5 else None,
            }
        )
    return out, total_pages


def detail(http, idx: int) -> dict:
    resp = http.get(PAGE_URL, params={"amode": "view", "idx": idx})
    resp.raise_for_status()
    tree = LexborHTMLParser(resp.text)

    title_node = tree.css_first(".work_list_box.recruit_view h5")
    body = None
    for box in tree.css("div"):
        heading = box.css_first("h5")
        if heading is not None and "상세 모집요강" in heading.text():
            cell = box.css_first("td")
            if cell is not None:
                body = html_to_text(cell.html)
            break
    return {
        "title": clean(title_node.text()) if title_node is not None else None,
        "body": body,
    }
