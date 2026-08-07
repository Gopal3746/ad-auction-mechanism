from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
import pandas as pd

from ad_auction_simulator.config import ProjectPaths
from ad_auction_simulator.mechanisms import first_price, sample_reserve, second_price


@dataclass(frozen=True)
class TransformResult:
    bid_events: int
    auction_outcomes: int
    reserve_reference_medians: dict[str, float]


def _build_sample_reserve_pools(
    auctions: pd.DataFrame,
    bids: pd.DataFrame,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """Build placement-specific value samples from the calibration split.

    Evaluation auctions draw one calibration value as an anonymous reserve. The true
    valuation distribution is never supplied to the mechanism.
    """
    calibration = (
        bids.merge(
            auctions[["auction_id", "placement_id", "split"]],
            on="auction_id",
            how="left",
            validate="many_to_one",
        )
        .loc[lambda frame: frame["split"] == "calibration"]
    )
    pools: dict[str, np.ndarray] = {}
    medians: dict[str, float] = {}
    for placement_id, group in calibration.groupby("placement_id"):
        values = group["private_value"].to_numpy(float)
        pools[placement_id] = values
        medians[placement_id] = float(np.median(values)) if values.size else 0.0
    return pools, medians


def _sample_reserve_for_auction(
    auction_id: str,
    placement_id: str,
    floor: float,
    pools: dict[str, np.ndarray],
) -> float:
    pool = pools.get(placement_id)
    if pool is None or pool.size == 0:
        return floor
    digest = hashlib.blake2b(
        f"{auction_id}:{placement_id}".encode("utf-8"), digest_size=8
    ).digest()
    index = int.from_bytes(digest, "big") % pool.size
    return max(floor, float(pool[index]))


def _assert_quality(fact_bids: pd.DataFrame, fact_auctions: pd.DataFrame) -> None:
    if fact_bids["bid_event_id"].duplicated().any():
        raise ValueError("Duplicate bid_event_id detected")
    if fact_auctions["auction_mechanism_id"].duplicated().any():
        raise ValueError("Duplicate auction_mechanism_id detected")
    required_bid = ["auction_id", "bidder_id", "mechanism", "private_value", "submitted_bid"]
    if fact_bids[required_bid].isna().any().any():
        raise ValueError("Nulls detected in required fact_bid_events columns")
    winner_counts = fact_bids.groupby(["auction_id", "mechanism"])["is_winner"].sum()
    if (winner_counts > 1).any():
        raise ValueError("More than one winner detected for an auction mechanism")
    if (fact_auctions["seller_revenue"] < 0).any():
        raise ValueError("Negative seller revenue detected")
    if (fact_bids["submitted_bid"] - fact_bids["private_value"] > 1e-9).any():
        raise ValueError("Simulator produced a bid above private value")


def transform(paths: ProjectPaths) -> TransformResult:
    auctions = pd.read_parquet(paths.raw / "raw_auctions.parquet")
    bids = pd.read_parquet(paths.raw / "raw_bids.parquet")
    bidders = pd.read_parquet(paths.raw / "raw_bidders.parquet")
    advertisers = pd.read_parquet(paths.raw / "raw_advertisers.parquet")
    placements = pd.read_parquet(paths.raw / "raw_placements.parquet")

    auctions["event_timestamp"] = pd.to_datetime(auctions["event_timestamp"], utc=True)
    auctions["time_id"] = auctions["event_timestamp"].dt.strftime("%Y%m%d%H").astype("int64")
    dim_time = (
        auctions[["time_id", "event_timestamp"]]
        .assign(
            date=lambda x: x["event_timestamp"].dt.date,
            hour=lambda x: x["event_timestamp"].dt.hour,
            day_of_week=lambda x: x["event_timestamp"].dt.day_name(),
            week=lambda x: x["event_timestamp"].dt.isocalendar().week.astype(int),
        )[["time_id", "date", "hour", "day_of_week", "week"]]
        .drop_duplicates("time_id")
        .sort_values("time_id")
    )

    dim_bidder = bidders[["bidder_id", "advertiser_id", "value_scale", "risk_aversion"]].copy()
    dim_advertiser = advertisers.copy()
    dim_placement = placements.copy()
    reserve_pools, reserve_reference_medians = _build_sample_reserve_pools(auctions, bids)
    placement_floors = placements.set_index("placement_id")["floor_price"].to_dict()
    auction_lookup = auctions.set_index("auction_id")

    bid_event_rows: list[dict[str, object]] = []
    outcome_rows: list[dict[str, object]] = []

    for auction_id, group in bids.groupby("auction_id", sort=False):
        auction = auction_lookup.loc[auction_id]
        values = group["private_value"].to_numpy(float)
        risks = group["risk_aversion"].to_numpy(float)
        floor = float(placement_floors[auction.placement_id])
        mechanisms = {
            "first_price": first_price(values, risks, floor),
            "second_price": second_price(values, floor),
            "sample_reserve": sample_reserve(
                values,
                _sample_reserve_for_auction(
                    auction_id, auction.placement_id, floor, reserve_pools
                ),
            ),
        }

        for mechanism, result in mechanisms.items():
            sorted_bids = np.sort(result.submitted_bids)
            highest_bid = float(sorted_bids[-1])
            second_highest_bid = float(sorted_bids[-2]) if len(sorted_bids) > 1 else 0.0
            filled = result.winner_index is not None
            winning_value = float(values[result.winner_index]) if filled else 0.0
            winner_surplus = winning_value - result.clearing_price if filled else 0.0
            shading_ratios = np.divide(
                result.submitted_bids,
                values,
                out=np.ones_like(values),
                where=values > 0,
            )
            auction_mechanism_id = f"{auction_id}_{mechanism}"
            outcome_rows.append(
                {
                    "auction_mechanism_id": auction_mechanism_id,
                    "auction_id": auction_id,
                    "event_timestamp": auction.event_timestamp,
                    "time_id": int(auction.time_id),
                    "placement_id": auction.placement_id,
                    "split": auction.split,
                    "mechanism": mechanism,
                    "auction_depth": int(len(group)),
                    "is_filled": bool(filled),
                    "winning_bid": highest_bid if filled else 0.0,
                    "second_highest_bid": second_highest_bid,
                    "clearing_price": float(result.clearing_price),
                    "reserve_price": float(result.reserve_price),
                    "seller_revenue": float(result.clearing_price),
                    "bid_spread": float(result.clearing_price - second_highest_bid) if filled else 0.0,
                    "top_bid_gap": float(highest_bid - second_highest_bid),
                    "winning_value": winning_value,
                    "winner_surplus": float(winner_surplus),
                    "mean_shading_ratio": float(np.mean(shading_ratios)),
                }
            )

            for position, row in enumerate(group.itertuples(index=False)):
                is_winner = filled and position == result.winner_index
                submitted_bid = float(result.submitted_bids[position])
                bid_event_rows.append(
                    {
                        "bid_event_id": f"{auction_id}_{mechanism}_{row.bidder_id}",
                        "auction_mechanism_id": auction_mechanism_id,
                        "auction_id": auction_id,
                        "event_timestamp": auction.event_timestamp,
                        "time_id": int(auction.time_id),
                        "placement_id": auction.placement_id,
                        "bidder_id": row.bidder_id,
                        "advertiser_id": row.advertiser_id,
                        "split": auction.split,
                        "mechanism": mechanism,
                        "private_value": float(row.private_value),
                        "submitted_bid": submitted_bid,
                        "bid_shading_amount": float(row.private_value - submitted_bid),
                        "bid_shading_ratio": float(submitted_bid / row.private_value),
                        "is_winner": bool(is_winner),
                        "win_price": float(result.clearing_price) if is_winner else np.nan,
                        "seller_revenue": float(result.clearing_price) if is_winner else 0.0,
                        "bidder_surplus": float(row.private_value - result.clearing_price) if is_winner else 0.0,
                    }
                )

    fact_bids = pd.DataFrame(bid_event_rows)
    fact_auctions = pd.DataFrame(outcome_rows)
    _assert_quality(fact_bids, fact_auctions)

    outputs = {
        "dim_time": dim_time,
        "dim_bidder": dim_bidder,
        "dim_advertiser": dim_advertiser,
        "dim_placement": dim_placement,
        "fact_bid_events": fact_bids,
        "fact_auction_outcomes": fact_auctions,
        "stg_sample_reserve_reference": pd.DataFrame(
            [
                {
                    "placement_id": key,
                    "calibration_value_median": value,
                    "calibration_sample_count": int(reserve_pools[key].size),
                }
                for key, value in reserve_reference_medians.items()
            ]
        ),
    }
    for name, frame in outputs.items():
        frame.to_parquet(paths.staging / f"{name}.parquet", index=False)

    return TransformResult(
        bid_events=len(fact_bids),
        auction_outcomes=len(fact_auctions),
        reserve_reference_medians=reserve_reference_medians,
    )
