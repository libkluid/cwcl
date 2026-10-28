"""Store layer: accumulate normalised documents as committed JSONL.

* ``data/jobs.jsonl`` — the display store (retention-pruned)
* ``data/seen.txt``   — id ledger of everything ever collected (never pruned),
  used to skip already-fetched postings on repeat runs
"""

from __future__ import annotations

from .jsonl import (
    load,
    load_ids,
    read_documents,
    save,
    save_ids,
    upsert,
)

__all__ = [
    "load",
    "load_ids",
    "read_documents",
    "save",
    "save_ids",
    "upsert",
]
