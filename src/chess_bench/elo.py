"""Standard-Elo rating math for the chess-bench leaderboard.

This module contains pure functions implementing the standard Elo rating
system. It has no dependencies beyond the standard library. Ratings are kept
as floats throughout; rounding (if any) is left to callers.
"""

DEFAULT_RATING: float = 1200
DEFAULT_K: int = 32

_VALID_SCORES: frozenset[float] = frozenset({0.0, 0.5, 1.0})


def expected_score(rating_a: float, rating_b: float) -> float:
    """Return the expected score of player A against player B.

    Uses the standard logistic formula ``1 / (1 + 10 ** ((rb - ra) / 400))``.
    The result lies in ``(0, 1)``. By symmetry,
    ``expected_score(a, b) + expected_score(b, a) == 1.0`` and equal ratings
    yield exactly ``0.5``.
    """
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_ratings(
    rating_a: float,
    rating_b: float,
    score_a: float,
    k: int = DEFAULT_K,
) -> tuple[float, float]:
    """Return updated ``(rating_a, rating_b)`` after a game.

    ``score_a`` is player A's actual result: ``1`` for a win, ``0.5`` for a
    draw, ``0`` for a loss. Player B's score is ``1 - score_a``. ``k`` is the
    K-factor controlling rating volatility.

    The total rating change is symmetric: whatever A gains, B loses (and vice
    versa), so the sum of the two ratings is conserved.

    Raises:
        ValueError: if ``score_a`` is not one of ``{0, 0.5, 1}``.
    """
    if score_a not in _VALID_SCORES:
        raise ValueError(
            f"score_a must be one of {{0, 0.5, 1}}, got {score_a!r}"
        )

    expected_a = expected_score(rating_a, rating_b)
    expected_b = 1.0 - expected_a
    score_b = 1.0 - score_a

    new_a = rating_a + k * (score_a - expected_a)
    new_b = rating_b + k * (score_b - expected_b)
    return new_a, new_b
