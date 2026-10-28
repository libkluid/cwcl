"""Page layer: turn stored documents into Hugo content.

Each document becomes ``site/content/jobs/<slug>.md`` with YAML front matter
(``title``, ``date``, ``source``, ``url``, ``body``). The Hugo site under
``site/`` renders the list and detail pages; run ``hugo`` afterwards to build.
"""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_CONTENT_DIR = "site/content/jobs"


class _Dumper(yaml.SafeDumper):
    """Dumper that writes multi-line strings as YAML literal blocks."""


def _represent_str(dumper: yaml.SafeDumper, data: str):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _represent_str)


def slug(doc_id: str) -> str:
    """Filesystem/Hugo-safe slug for a document id."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in doc_id)


def _front_matter(doc: dict) -> dict:
    matter: dict = {"title": doc.get("title") or "(제목 없음)"}
    if doc.get("posted_on"):
        matter["date"] = doc["posted_on"]
    if doc.get("closes_on"):
        matter["closes_on"] = doc["closes_on"]
    matter["source"] = doc.get("source")
    matter["source_url"] = doc.get("url")
    matter["body"] = doc.get("body") or ""
    return matter


def write_content(docs: list[dict], content_dir: str | Path = DEFAULT_CONTENT_DIR) -> int:
    """(Re)write one markdown file per document. ``_index.md`` is preserved."""
    directory = Path(content_dir)
    directory.mkdir(parents=True, exist_ok=True)

    for stale in directory.glob("*.md"):
        if stale.name != "_index.md":
            stale.unlink()

    for doc in docs:
        matter = yaml.dump(
            _front_matter(doc),
            Dumper=_Dumper,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
        (directory / f"{slug(str(doc.get('id', '')))}.md").write_text(
            f"---\n{matter}---\n", encoding="utf-8"
        )
    return len(docs)
