from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from ad_auction_simulator.config import ProjectPaths


@dataclass(frozen=True)
class ExtractResult:
    auctions: int
    bids: int
    calibration_auctions: int


PLACEMENTS = (
    ("placement_news", "News display", "display", 1.20),
    ("placement_video", "Streaming pre-roll", "video", 4.50),
    ("placement_mobile", "Mobile app interstitial", "mobile", 2.10),
    ("placement_commerce", "Commerce product page", "display", 3.10),
    ("placement_finance", "Finance premium", "display", 5.20),
)


def extract_synthetic(
    paths: ProjectPaths,
    auction_count: int = 25_000,
    bidder_count: int = 40,
    advertiser_count: int = 12,
    days: int = 30,
    seed: int = 42,
    calibration_fraction: float = 0.20,
) -> ExtractResult:
    if auction_count < 100:
        raise ValueError("auction_count must be at least 100")
    if bidder_count < 2:
        raise ValueError("bidder_count must be at least 2")
    if not 0.05 <= calibration_fraction <= 0.50:
        raise ValueError("calibration_fraction must be between 0.05 and 0.50")

    paths.ensure()
    rng = np.random.default_rng(seed)

    advertisers = pd.DataFrame(
        {
            "advertiser_id": [f"adv_{i:02d}" for i in range(advertiser_count)],
            "advertiser_name": [f"Advertiser {i:02d}" for i in range(advertiser_count)],
            "industry": rng.choice(
                ["retail", "travel", "finance", "gaming", "software", "consumer_goods"],
                size=advertiser_count,
            ),
        }
    )

    bidder_profiles = pd.DataFrame(
        {
            "bidder_id": [f"bidder_{i:03d}" for i in range(bidder_count)],
            "advertiser_id": rng.choice(advertisers["advertiser_id"], size=bidder_count),
            "value_scale": rng.lognormal(mean=0.0, sigma=0.28, size=bidder_count),
            "risk_aversion": rng.beta(2.2, 2.2, size=bidder_count),
        }
    )

    placements = pd.DataFrame(
        PLACEMENTS,
        columns=["placement_id", "placement_name", "format", "base_cpm"],
    )
    placements["floor_price"] = placements["base_cpm"] * 0.35

    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    total_seconds = max(days, 1) * 24 * 60 * 60
    offsets = rng.integers(0, total_seconds, size=auction_count)
    timestamps = [start + timedelta(seconds=int(offset)) for offset in offsets]
    placement_ids = rng.choice(placements["placement_id"], size=auction_count, p=[0.32, 0.12, 0.25, 0.20, 0.11])
    split = np.where(rng.random(auction_count) < calibration_fraction, "calibration", "evaluation")

    auctions = pd.DataFrame(
        {
            "auction_id": [f"auc_{i:08d}" for i in range(auction_count)],
            "event_timestamp": pd.to_datetime(timestamps, utc=True),
            "placement_id": placement_ids,
            "split": split,
            "quality_multiplier": rng.lognormal(mean=0.0, sigma=0.34, size=auction_count),
        }
    ).sort_values("event_timestamp", ignore_index=True)

    placement_lookup = placements.set_index("placement_id")
    bidder_lookup = bidder_profiles.set_index("bidder_id")
    bidder_ids = bidder_profiles["bidder_id"].to_numpy()

    bid_rows: list[dict[str, object]] = []
    for row in auctions.itertuples(index=False):
        depth = int(np.clip(2 + rng.poisson(4.5), 2, min(18, bidder_count)))
        selected = rng.choice(bidder_ids, size=depth, replace=False)
        placement = placement_lookup.loc[row.placement_id]
        for bidder_id in selected:
            profile = bidder_lookup.loc[bidder_id]
            expected_value = float(placement.base_cpm * row.quality_multiplier * profile.value_scale)
            private_value = float(np.clip(rng.lognormal(np.log(expected_value), 0.46), 0.05, 60.0))
            bid_rows.append(
                {
                    "auction_id": row.auction_id,
                    "bidder_id": bidder_id,
                    "advertiser_id": profile.advertiser_id,
                    "private_value": private_value,
                    "risk_aversion": float(profile.risk_aversion),
                }
            )

    bids = pd.DataFrame(bid_rows)

    auctions.to_parquet(paths.raw / "raw_auctions.parquet", index=False)
    bids.to_parquet(paths.raw / "raw_bids.parquet", index=False)
    bidder_profiles.to_parquet(paths.raw / "raw_bidders.parquet", index=False)
    advertisers.to_parquet(paths.raw / "raw_advertisers.parquet", index=False)
    placements.to_parquet(paths.raw / "raw_placements.parquet", index=False)

    return ExtractResult(
        auctions=len(auctions),
        bids=len(bids),
        calibration_auctions=int((auctions["split"] == "calibration").sum()),
    )
