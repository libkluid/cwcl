"""Load layer: fetch raw postings from each source.

Each source module exposes a uniform interface:

* ``rows(**kwargs) -> Iterator[dict]`` — list-level rows, each a dict with at
  least ``source``, ``key``, ``title``, ``url`` and ``posted_on`` (or ``None``)
* ``detail(http, key) -> dict`` — detail-level fields (``title``, ``posted_on``,
  ``body``)

:data:`SOURCES` maps a source name to its module so the merge layer can iterate
sources generically.
"""

from __future__ import annotations

from types import ModuleType

from . import changwon, gne, gojobs
from ._http import client

SOURCES: dict[str, ModuleType] = {
    "gne": gne,
    "gojobs": gojobs,
    "changwon": changwon,
}
NAMES: tuple[str, ...] = tuple(SOURCES)

__all__ = ["NAMES", "SOURCES", "client"]
