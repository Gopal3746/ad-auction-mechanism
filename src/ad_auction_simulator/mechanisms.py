from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AuctionResult:
    submitted_bids: np.ndarray
    winner_index: int | None
    clearing_price: float
    reserve_price: float

    @property
    def filled(self) -> bool:
        return self.winner_index is not None


def _winner(submitted_bids: np.ndarray, reserve_price: float) -> int | None:
    if submitted_bids.size == 0:
        return None
    winner_index = int(np.argmax(submitted_bids))
    return winner_index if submitted_bids[winner_index] >= reserve_price else None


def first_price(
    private_values: np.ndarray,
    risk_aversion: np.ndarray,
    reserve_price: float,
) -> AuctionResult:
    """Heuristic first-price bidding based on the symmetric IPV uniform benchmark.

    The textbook equilibrium bid under i.i.d. uniform values is ((n-1)/n) * value.
    We use that factor as a transparent baseline and add a small bidder-specific
    risk-aversion adjustment. Because the simulator uses log-normal values, this is
    explicitly a behavioral approximation rather than a claimed closed-form equilibrium.
    """
    depth = max(int(private_values.size), 1)
    equilibrium_factor = (depth - 1) / depth if depth > 1 else 1.0
    adjustment = 0.06 * (risk_aversion - 0.5)
    shading_factor = np.clip(equilibrium_factor + adjustment, 0.55, 0.99)
    submitted_bids = private_values * shading_factor
    winner_index = _winner(submitted_bids, reserve_price)
    clearing_price = float(submitted_bids[winner_index]) if winner_index is not None else 0.0
    return AuctionResult(submitted_bids, winner_index, clearing_price, reserve_price)


def second_price(private_values: np.ndarray, reserve_price: float) -> AuctionResult:
    submitted_bids = private_values.copy()
    winner_index = _winner(submitted_bids, reserve_price)
    if winner_index is None:
        return AuctionResult(submitted_bids, None, 0.0, reserve_price)

    sorted_bids = np.sort(submitted_bids)
    second_highest = float(sorted_bids[-2]) if submitted_bids.size > 1 else 0.0
    clearing_price = max(float(reserve_price), second_highest)
    return AuctionResult(submitted_bids, winner_index, clearing_price, reserve_price)


def sample_reserve(private_values: np.ndarray, sampled_reserve: float) -> AuctionResult:
    """Prior-independent second-price auction with a reserve learned from samples."""
    return second_price(private_values, sampled_reserve)
