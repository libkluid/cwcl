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
    skip_keys: set[int] | None,
    seen_keys: set[int] | None,
) -> dict:
    kwargs: dict = {"max_pages": max_pages}
    if delay is not None:
        kwargs["delay"] = delay
    if skip_keys:
        kwargs["skip_keys"] = skip_keys
    if seen_keys is not None:
        kwargs["seen_keys"] = seen_keys
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


def _skip_keys(name: str, known_ids: set[str] | None) -> set[int] | None:
    """Source-local key set for documents already in the store."""
    if not known_ids:
        return None
    prefix = f"{name}:"
    keys: set[int] = set()
    for doc_id in known_ids:
        if doc_id.startswith(prefix):
            try:
                keys.add(int(doc_id[len(prefix):]))
            except ValueError:
                continue
    return keys or None


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
    known_ids: set[str] | None = None,
    encountered: set[str] | None = None,
) -> Iterator[dict]:
    """Yield normalised documents for each selected source.

    ``known_ids`` are document ids already in the store; matching list rows are
    skipped (no detail request) and pagination stops once a page is fully known,
    so repeat runs only fetch what is new. Every list-row key seen is added to
    ``encountered`` (as ``<source>:<key>``) so mixed pages can also stop early.
    ``delay=None`` keeps each source's list-page default; ``limit`` caps output.
    """
    selected = tuple(s for s in sources if s in SOURCES)
    emitted = 0

    with client() as http:
        for name in selected:
            module = SOURCES[name]
            local_seen: set[int] = set()
            kwargs = _row_kwargs(
                name,
                max_pages=max_pages,
                delay=delay,
                region=region,
                keyword=keyword,
                gojobs_areas=gojobs_areas,
                changwon_match=changwon_match,
                skip_keys=_skip_keys(name, known_ids),
                seen_keys=local_seen if encountered is not None else None,
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

            if encountered is not None:
                encountered.update(f"{name}:{key}" for key in local_seen)
