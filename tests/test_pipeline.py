from pathlib import Path

import duckdb

from ad_auction_simulator.analysis import analyze
from ad_auction_simulator.config import ProjectPaths
from ad_auction_simulator.pipeline.extract import extract_synthetic
from ad_auction_simulator.pipeline.load import load
from ad_auction_simulator.pipeline.transform import transform


def test_end_to_end_pipeline(tmp_path: Path):
    root = tmp_path
    (root / "sql").mkdir()
    source_sql = Path(__file__).resolve().parents[1] / "sql" / "views.sql"
    (root / "sql" / "views.sql").write_text(source_sql.read_text())
    paths = ProjectPaths.from_root(root)

    extract_synthetic(paths, auction_count=300, bidder_count=12, advertiser_count=5, days=5, seed=7)
    transformed = transform(paths)
    loaded = load(paths)
    result = analyze(loaded.database_path, paths.artifacts)

    assert transformed.auction_outcomes == 900
    assert len(result["mechanism_kpis"]) == 3
    with duckdb.connect(str(loaded.database_path), read_only=True) as connection:
        count = connection.execute("SELECT COUNT(*) FROM fact_bid_events").fetchone()[0]
    assert count == transformed.bid_events
