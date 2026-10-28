"""Store layer: accumulate normalised documents as committed JSONL."""

from __future__ import annotations

from .jsonl import load, read_documents, save, upsert

__all__ = ["load", "read_documents", "save", "upsert"]
