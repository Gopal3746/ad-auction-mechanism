from __future__ import annotations

import argparse
from pathlib import Path

from ad_auction_simulator.analysis import analyze
from ad_auction_simulator.config import ProjectPaths
from ad_auction_simulator.pipeline.extract import extract_synthetic
from ad_auction_simulator.pipeline.load import load
from ad_auction_simulator.pipeline.transform import transform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ad auction analytics pipeline.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--auctions", type=int, default=25_000, help="Number of base auctions")
    parser.add_argument("--bidders", type=int, default=40, help="Bidder population")
    parser.add_argument("--advertisers", type=int, default=12, help="Advertiser population")
    parser.add_argument("--days", type=int, default=30, help="Synthetic observation period")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--skip-extract", action="store_true", help="Reuse existing raw parquet")
    parser.add_argument("--llm-summary", action="store_true", help="Use optional OpenAI summary")
    return parser


def run(args: argparse.Namespace) -> None:
    paths = ProjectPaths.from_root(args.root)
    paths.ensure()

    if not args.skip_extract:
        extracted = extract_synthetic(
            paths,
            auction_count=args.auctions,
            bidder_count=args.bidders,
            advertiser_count=args.advertisers,
            days=args.days,
            seed=args.seed,
        )
        print(
            f"Extracted {extracted.auctions:,} auctions and {extracted.bids:,} bids "
            f"({extracted.calibration_auctions:,} calibration auctions)."
        )

    transformed = transform(paths)
    print(
        f"Transformed {transformed.bid_events:,} bid events and "
        f"{transformed.auction_outcomes:,} auction outcomes."
    )
    print("Calibration value medians used by the sample-reserve mechanism:")
    for placement_id, value in sorted(transformed.reserve_reference_medians.items()):
        print(f"  {placement_id}: {value:.3f} CPM")

    loaded = load(paths)
    print(f"Loaded DuckDB warehouse: {loaded.database_path}")

    analysis = analyze(loaded.database_path, paths.artifacts, use_llm=args.llm_summary)
    print("\nExecutive summary")
    print("-----------------")
    print(analysis["executive_summary"])


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
