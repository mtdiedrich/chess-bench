"""Tests for the standard-Elo rating math in chess_bench.elo."""

import math

import pytest

from chess_bench import elo


def test_constants() -> None:
    assert elo.DEFAULT_RATING == 1200
    assert elo.DEFAULT_K == 32


def test_expected_score_equal_ratings_is_half() -> None:
    assert elo.expected_score(1200, 1200) == 0.5


def test_expected_score_symmetry_sums_to_one() -> None:
    a, b = 1500, 1320
    assert math.isclose(
        elo.expected_score(a, b) + elo.expected_score(b, a), 1.0
    )


def test_expected_score_higher_rating_favored() -> None:
    assert elo.expected_score(1600, 1400) > 0.5
    assert elo.expected_score(1400, 1600) < 0.5


def test_win_raises_a_and_lowers_b() -> None:
    new_a, new_b = elo.update_ratings(1200, 1200, 1)
    assert new_a > 1200
    assert new_b < 1200


def test_loss_lowers_a_and_raises_b() -> None:
    new_a, new_b = elo.update_ratings(1200, 1200, 0)
    assert new_a < 1200
    assert new_b > 1200


def test_rating_change_is_symmetric() -> None:
    # Whatever A gains, B loses; the sum is conserved.
    ra, rb = 1320, 1480
    new_a, new_b = elo.update_ratings(ra, rb, 1)
    assert math.isclose(new_a - ra, rb - new_b)
    assert math.isclose(new_a + new_b, ra + rb)


def test_draw_between_equal_ratings_is_noop() -> None:
    new_a, new_b = elo.update_ratings(1200, 1200, 0.5)
    assert math.isclose(new_a, 1200)
    assert math.isclose(new_b, 1200)


def test_higher_rated_winner_gains_less_than_upset_winner() -> None:
    # Favorite (higher rating) beats underdog -> small gain.
    fav_new, _ = elo.update_ratings(1800, 1200, 1)
    favorite_gain = fav_new - 1800

    # Underdog (lower rating) pulls off an upset -> large gain.
    upset_new, _ = elo.update_ratings(1200, 1800, 1)
    upset_gain = upset_new - 1200

    assert upset_gain > favorite_gain


def test_invalid_score_raises_value_error() -> None:
    for bad in (0.25, 2, -1, 0.75, 1.5):
        with pytest.raises(ValueError):
            elo.update_ratings(1200, 1200, bad)


def test_k_factor_scales_change() -> None:
    small = elo.update_ratings(1200, 1200, 1, k=16)[0] - 1200
    large = elo.update_ratings(1200, 1200, 1, k=32)[0] - 1200
    assert math.isclose(large, 2 * small)


def test_e2e_two_equal_players_sum_conserved() -> None:
    # Scenario: two fresh 1200 players; winner rises, loser falls,
    # and the total rating is conserved.
    white = elo.DEFAULT_RATING
    black = elo.DEFAULT_RATING
    total_before = white + black

    new_white, new_black = elo.update_ratings(white, black, 1)

    assert new_white > white
    assert new_black < black
    assert math.isclose(new_white + new_black, total_before)
