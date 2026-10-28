"""Merge layer: load normalised documents through a dlt pipeline.

Documents are produced by :mod:`jobs.merge.normalize`, loaded via
``pipeline.run`` (dlt handles schema + ``merge`` upsert), and returned so the
store layer can persist them. The destination (DuckDB) is treated as ephemeral;
the accumulated dataset lives in the JSONL store.
"""

from __future__ import annotations

import dlt

from .normalize import iter_documents

TABLE = "job_documents"
_COLUMNS = {
    "posted_on": {"data_type": "date", "nullable": True},
    "closes_on": {"data_type": "date", "nullable": True},
}


def load(
    docs: list[dict],
    *,
    pipeline_name: str = "changwon_jobs",
    dataset_name: str = "raw",
    destination: str = "duckdb",
) -> dlt.Pipeline:
    """Load documents into the dlt destination (merge/upsert by ``id``)."""
    pipeline = dlt.pipeline(
        pipeline_name=pipeline_name,
        destination=destination,
        dataset_name=dataset_name,
    )
    pipeline.run(
        docs,
        table_name=TABLE,
        write_disposition="merge",
        primary_key="id",
        columns=_COLUMNS,
    )
    return pipeline


def sync(
    *,
    pipeline_name: str = "changwon_jobs",
    dataset_name: str = "raw",
    destination: str = "duckdb",
    **kwargs,
) -> list[dict]:
    """Produce this run's documents, load them, and return them."""
    docs = list(iter_documents(**kwargs))
    load(
        docs,
        pipeline_name=pipeline_name,
        dataset_name=dataset_name,
        destination=destination,
    )
    return docs
