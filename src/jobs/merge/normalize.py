"""Merge layer: combine list rows and detail pages into one document schema.

Every emitted document has the shape the store and page layers rely on::

    {"id", "source", "title", "posted_on", "url", "body"}

``id`` is ``<source>:<key>`` and is the merge/dedup key.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from ..load import NAMES, SOURCES, client


def _row_kwargs(
    name: str,
    *,
    max_pages: int,
    delay: float | None,
    region: str,
    keyword: str,
    gojobs_areas: tuple[str, ...] | None,
    changwon_match: tuple[str, ...] | None,
) -> dict:
    kwargs: dict = {"max_pages": max_pages}
    if delay is not None:
        kwargs["delay"] = delay
    if name == "gne":
        kwargs["region"] = region
    elif name == "gojobs":
        kwargs["keyword"] = keyword
        if gojobs_areas is not None:
            kwargs["areas"] = gojobs_areas
    elif name == "changwon":
        if changwon_match is not None:
            kwargs["match"] = changwon_match
    return kwargs


def iter_documents(
    sources: tuple[str, ...] = NAMES,
    *,
    max_pages: int = 5,
    delay: float | None = None,
    detail_delay: float = 1.0,
    limit: int | None = None,
    region: str = "창원",
    keyword: str = "청소",
    gojobs_areas: tuple[str, ...] | None = None,
    changwon_match: tuple[str, ...] | None = None,
) -> Iterator[dict]:
    """Yield normalised documents for each selected source.

    ``delay=None`` keeps each source's list-page default; ``detail_delay`` is the
    pause between detail requests; ``limit`` caps the number of documents emitted.
    """
    selected = tuple(s for s in sources if s in SOURCES)
    emitted = 0

    with client() as http:
        for name in selected:
            module = SOURCES[name]
            kwargs = _row_kwargs(
                name,
                max_pages=max_pages,
                delay=delay,
                region=region,
                keyword=keyword,
                gojobs_areas=gojobs_areas,
                changwon_match=changwon_match,
            )
            for row in module.rows(**kwargs):
                key = row.get("key")
                if key is None:
                    continue
                try:
                    extra = module.detail(http, key)
                except Exception as exc:  # skip the bad row, keep the run going
                    print(f"[merge] skipped {name}:{key}: {exc}")
                    continue

                yield {
                    "id": f"{name}:{key}",
                    "source": name,
                    "title": row.get("title") or extra.get("title"),
                    "posted_on": row.get("posted_on") or extra.get("posted_on"),
                    "closes_on": row.get("closes_on") or extra.get("closes_on"),
                    "url": row.get("url"),
                    "body": extra.get("body"),
                }

                emitted += 1
                if limit is not None and emitted >= limit:
                    return
                time.sleep(detail_delay)
