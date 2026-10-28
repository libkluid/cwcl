"""Page layer: render the store into a static site (Hugo)."""

from __future__ import annotations

from .hugo import write_content

__all__ = ["write_content"]
