"""Store layer: a JSONL-backed, committed dataset.

The dlt/DuckDB destination is ephemeral, so the accumulated documents live in a
committed ``data/jobs.jsonl``: one document per line, keyed by ``id``, merged
last-write-wins and optionally pruned by age. The page layer renders from here,
so the published site keeps history across runs.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

FIELDS = ("id", "source", "title", "posted_on", "closes_on", "url", "body")


def _slim(doc: dict) -> dict:
    return {key: doc.get(key) for key in FIELDS}


def load(path: str | Path) -> dict[str, dict]:
    """Read the store into ``{id: document}`` (missing file -> empty)."""
    file = Path(path)
    if not file.exists():
        return {}
    store: dict[str, dict] = {}
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            continue
        if doc.get("id"):
            store[doc["id"]] = doc
    return store


def save(path: str | Path, store: dict[str, dict]) -> int:
    """Write the store deterministically (by date then id) and return its size."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(store.values(), key=lambda d: (d.get("posted_on") or "", d.get("id") or ""))
    with file.open("w", encoding="utf-8") as handle:
        for doc in ordered:
            handle.write(json.dumps(_slim(doc), ensure_ascii=False) + "\n")
    return len(ordered)


def upsert(
    existing: dict[str, dict],
    fetched: list[dict],
    *,
    retention_days: int | None = None,
    today: date | None = None,
) -> dict[str, dict]:
    """Merge freshly fetched documents into the store, then apply retention."""
    merged = dict(existing)
    for doc in fetched:
        if doc.get("id"):
            merged[doc["id"]] = _slim(doc)

    if retention_days is not None:
        cutoff = ((today or date.today()) - timedelta(days=retention_days)).isoformat()
        merged = {
            key: doc
            for key, doc in merged.items()
            if not doc.get("posted_on") or doc["posted_on"] >= cutoff
        }
    return merged


def read_documents(path: str | Path) -> list[dict]:
    """All documents, newest first (for rendering)."""
    docs = list(load(path).values())
    docs.sort(key=lambda d: (d.get("posted_on") or "", d.get("title") or ""), reverse=True)
    return docs


def load_ids(path: str | Path) -> set[str]:
    """Read a newline-separated id ledger (missing file -> empty)."""
    file = Path(path)
    if not file.exists():
        return set()
    return {line.strip() for line in file.read_text(encoding="utf-8").splitlines() if line.strip()}


def save_ids(path: str | Path, ids: set[str]) -> int:
    """Write the id ledger, sorted, and return its size."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(ids)
    file.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    return len(ordered)
