"""경상남도교육청 구인·구직포털 — 교육공무직원(청소원).

The education office hires school/facility cleaners directly (교육공무직원),
making this the highest-volume source of direct public-sector cleaning jobs.

Verified flow
-------------
GET  BD_recruitmentList.do?regionSearch=창원&jobSearch=교육공무직원
                           &jobDetailSearch=청소원&q_rowPerPage=10&q_currPage=1
GET  BD_recruitmentDetail.do?regSn=<id>

``chckSrch`` only pre-checks the filter UI; the server filters on
``regionSearch`` / ``jobSearch`` / ``jobDetailSearch``. The detail link is an
``openDetail('<regSn>')`` onclick on ``span.tit a``. robots.txt is absent (404).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

from selectolax.lexbor import LexborHTMLParser

from ._http import clean, client, fetch, html_to_text, iso_date

LIST_URL = "https://www.gne.go.kr/works/user/recruitment/BD_recruitmentList.do"
DETAIL_URL = "https://www.gne.go.kr/works/user/recruitment/BD_recruitmentDetail.do"

_REG_SN = re.compile(r"openDetail\('(\d+)'\)")


def rows(
    region: str = "창원",
    job: str = "교육공무직원",
    job_detail: str = "청소원",
    max_pages: int = 3,
    delay: float = 1.0,
) -> Iterator[dict]:
    params_base = {
        "regionSearch": region,
        "jobSearch": job,
        "jobDetailSearch": job_detail,
        "q_rowPerPage": "10",
    }
    with client() as http:
        for page in range(1, max_pages + 1):
            resp = fetch(http, "GET", LIST_URL, params={**params_base, "q_currPage": str(page)})
            if resp is None:
                break
            page_rows = _parse_rows(resp.text, region)
            if not page_rows:
                break
            yield from page_rows
            if page < max_pages:
                time.sleep(delay)


def _parse_rows(html: str, region: str) -> list[dict]:
    tree = LexborHTMLParser(html)
    out: list[dict] = []
    for tr in tree.css("table tbody tr"):
        cells = tr.css("td")
        if not cells:
            continue
        anchor = tr.css_first("span.tit a")
        if anchor is None:
            continue
        found = _REG_SN.search(anchor.attributes.get("onclick") or "")
        if not found:
            continue
        reg_sn = int(found.group(1))

        category = tr.css_first("span.cate")
        job_detail = None
        if category is not None:
            head, _, tail = (clean(category.text(strip=True)) or "").partition("｜")
            job_detail = clean(tail.partition(" ")[2]) or None

        period = None
        if len(cells) > 2:
            spans = [clean(s.text(strip=True)) for s in cells[2].css("span")]
            period = spans[1] if len(spans) > 1 else None

        closes_on = iso_date(period.split("~")[-1]) if period and "~" in period else None

        status = None
        if len(cells) > 3:
            spans = [clean(s.text(strip=True)) for s in cells[3].css("span")]
            status = spans[1] if len(spans) > 1 else None

        out.append(
            {
                "source": "gne",
                "key": reg_sn,
                "title": clean(anchor.text(strip=True)),
                "url": f"{DETAIL_URL}?regSn={reg_sn}",
                "posted_on": None,
                "closes_on": closes_on,
                "status": status,
                "job_detail": job_detail,
                "apply_period": period,
            }
        )
    return out


def detail(http, reg_sn: int) -> dict:
    resp = http.get(DETAIL_URL, params={"regSn": reg_sn})
    resp.raise_for_status()
    tree = LexborHTMLParser(resp.text)

    posted_on = None
    for li in tree.css(".bd-view__vetc li"):
        title = li.css_first("span.tit")
        text = li.css_first("span.txt")
        if title is not None and text is not None and "등록일" in title.text():
            posted_on = iso_date(text.text())
            break

    body_node = tree.css_first(".bd-view__vcontent .txt")
    return {
        "posted_on": posted_on,
        "body": html_to_text(body_node.html if body_node is not None else None),
    }
