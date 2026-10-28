"""Merge layer: list rows + detail pages -> normalised documents (via dlt)."""

from __future__ import annotations

from .normalize import iter_documents
from .pipeline import load, sync

__all__ = ["iter_documents", "load", "sync"]
