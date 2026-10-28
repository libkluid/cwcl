"""Command-line entrypoint for the 창원 direct-hire cleaning-job dataset.

Subcommands
-----------
``sync``    load + merge (via dlt) and merge results into the JSONL store
``render``  turn the JSONL store into Hugo content under ``site/content/jobs``
``build``   ``sync`` + ``render`` (the GitHub Actions entrypoint; then run hugo)

The dlt/DuckDB destination is ephemeral; the accumulated dataset is the
committed ``data/jobs.jsonl`` store, which the Hugo site is built from.

Examples
--------
::

    uv run jobs sync --max-pages 3 --detail-delay 0.5
    uv run jobs render
    uv run jobs build --max-pages 3
    hugo --source site --minify
"""

from __future__ import annotations

import argparse
import sys

from . import load, store
from .merge import sync
from .page import write_content

DEFAULT_STORE = "data/jobs.jsonl"
DEFAULT_CONTENT_DIR = "site/content/jobs"


def _resolve_sources(values: list[str] | None) -> tuple[str, ...]:
    if not values or "all" in values:
        return load.NAMES
    return tuple(name for name in load.NAMES if name in values)


def _parse_tokens(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    return tuple(part.strip() for part in value.split(",") if part.strip()) or None


def _add_sync_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sources", nargs="*", choices=("all", *load.NAMES))
    parser.add_argument("--max-pages", type=int, default=5, help="page cap per source (default: 5).")
    parser.add_argument("--delay", type=float, default=None, help="list page delay override (seconds).")
    parser.add_argument("--detail-delay", type=float, default=1.0, help="delay between detail requests.")
    parser.add_argument("--limit", type=int, default=None, help="stop after N documents.")
    parser.add_argument("--region", default="창원", help="gne region filter (default: 창원).")
    parser.add_argument("--keyword", default="청소", help="gojobs search term (default: 청소).")
    parser.add_argument(
        "--gojobs-areas",
        default="48121,48123",
        metavar="CODES",
        help="gojobs work-area codes (default: 48121,48123 = 창원시 의창구/성산구; "
        "48120=창원시). Empty string clears the filter.",
    )
    parser.add_argument(
        "--match",
        default=None,
        metavar="A,B",
        help="changwon: substrings to keep a row (source default when unset).",
    )
    parser.add_argument("--store", default=DEFAULT_STORE, help=f"JSONL store (default: {DEFAULT_STORE}).")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=180,
        help="drop store rows older than N days (default: 180; 0 disables).",
    )
    parser.add_argument("--pipeline-name", default="changwon_jobs", help="dlt pipeline name.")
    parser.add_argument("--dataset-name", default="raw", help="dlt dataset/schema name.")
    parser.add_argument("--destination", default="duckdb", help="dlt destination (default: duckdb).")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobs", description="Collect direct-hire public-sector cleaning jobs in 창원시."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sync_cmd = sub.add_parser("sync", help="load + merge and update the JSONL store")
    _add_sync_options(sync_cmd)

    render_cmd = sub.add_parser("render", help="render the store into Hugo content")
    render_cmd.add_argument("--store", default=DEFAULT_STORE)
    render_cmd.add_argument("--content-dir", default=DEFAULT_CONTENT_DIR)

    build_cmd = sub.add_parser("build", help="sync + render")
    _add_sync_options(build_cmd)
    build_cmd.add_argument("--content-dir", default=DEFAULT_CONTENT_DIR)

    return parser


def _sync_kwargs(args: argparse.Namespace) -> dict:
    kwargs: dict = {
        "sources": _resolve_sources(getattr(args, "sources", None)),
        "max_pages": args.max_pages,
        "detail_delay": args.detail_delay,
        "limit": args.limit,
        "region": args.region,
        "keyword": args.keyword,
        "gojobs_areas": _parse_tokens(args.gojobs_areas),
    }
    if args.delay is not None:
        kwargs["delay"] = args.delay
    match = _parse_tokens(args.match)
    if match is not None:
        kwargs["changwon_match"] = match
    return kwargs


def _run_sync(args: argparse.Namespace) -> int:
    kwargs = _sync_kwargs(args)
    print(f"Syncing → sources={', '.join(kwargs['sources'])}")
    docs = sync(
        pipeline_name=args.pipeline_name,
        dataset_name=args.dataset_name,
        destination=args.destination,
        **kwargs,
    )

    existing = store.load(args.store)
    merged = store.upsert(existing, docs, retention_days=args.retention_days or None)
    total = store.save(args.store, merged)
    print(f"Store: fetched {len(docs)}, kept {total} → {args.store}")
    return 0


def _run_render(args: argparse.Namespace) -> int:
    docs = store.read_documents(args.store)
    count = write_content(docs, args.content_dir)
    print(f"Rendered {count} pages → {args.content_dir}")
    return 0


def _run_build(args: argparse.Namespace) -> int:
    _run_sync(args)
    _run_render(args)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handlers = {"sync": _run_sync, "render": _run_render, "build": _run_build}
    try:
        return handlers[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
