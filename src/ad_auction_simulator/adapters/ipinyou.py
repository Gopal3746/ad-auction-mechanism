from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"bidid", "timestamp", "payprice", "bidprice", "advertiser"}


def read_ipinyou_log(path: Path | str) -> pd.DataFrame:
    """Read an extracted iPinYou tab-separated log and normalize common columns.

    iPinYou is useful for validating market-level price and response patterns, but its
    advertiser-side logs do not expose every competing bidder in each auction. Therefore,
    this adapter deliberately does not pretend it can reconstruct true auction depth or
    replay first-price versus second-price outcomes.
    """
    frame = pd.read_csv(path, sep="\t", low_memory=False)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing expected iPinYou columns: {sorted(missing)}")
    return frame.rename(
        columns={
            "bidid": "impression_id",
            "bidprice": "submitted_bid",
            "payprice": "win_price",
            "advertiser": "advertiser_id",
        }
    )
