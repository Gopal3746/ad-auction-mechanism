from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from ad_auction_simulator.config import ProjectPaths


@dataclass(frozen=True)
class LoadResult:
    database_path: Path
    tables: tuple[str, ...]


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def load(paths: ProjectPaths) -> LoadResult:
    paths.ensure()
    database_path = paths.warehouse / "auction_analytics.duckdb"
    tables = (
        "dim_time",
        "dim_bidder",
        "dim_advertiser",
        "dim_placement",
        "fact_bid_events",
        "fact_auction_outcomes",
        "stg_sample_reserve_reference",
    )

    with duckdb.connect(str(database_path)) as connection:
        for table in tables:
            parquet_path = _sql_path(paths.staging / f"{table}.parquet")
            connection.execute(
                f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{parquet_path}')"
            )
        connection.execute((paths.sql / "views.sql").read_text(encoding="utf-8"))
        connection.execute("CHECKPOINT")

    return LoadResult(database_path=database_path, tables=tables)
