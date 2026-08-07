import numpy as np

from ad_auction_simulator.mechanisms import first_price, sample_reserve, second_price


def test_second_price_charges_second_bid():
    values = np.array([5.0, 3.0, 1.0])
    result = second_price(values, reserve_price=0.5)
    assert result.winner_index == 0
    assert result.clearing_price == 3.0
    assert np.allclose(result.submitted_bids, values)


def test_second_price_reserve_can_bind():
    values = np.array([5.0, 1.0])
    result = second_price(values, reserve_price=2.5)
    assert result.winner_index == 0
    assert result.clearing_price == 2.5


def test_first_price_shades_without_overbidding():
    values = np.array([5.0, 3.0, 1.0])
    risk = np.array([0.5, 0.5, 0.5])
    result = first_price(values, risk, reserve_price=0.1)
    assert np.all(result.submitted_bids <= values)
    assert result.clearing_price == result.submitted_bids[result.winner_index]


def test_sample_reserve_can_leave_auction_unfilled():
    result = sample_reserve(np.array([1.0, 0.8]), sampled_reserve=2.0)
    assert result.winner_index is None
    assert result.clearing_price == 0.0
