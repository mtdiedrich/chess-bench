"""Tournament and pairing scheduling for chess-bench.

Provides deterministic pairing strategies that play full games between
:class:`~chess_bench.players.base.Player` instances and record each result via
:func:`chess_bench.match.play_and_record`.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from chess_bench.match import play_and_record

if TYPE_CHECKING:
    from chess_bench.match import MatchResult
    from chess_bench.players.base import Player
    from chess_bench.registry import Registry


def round_robin(
    players: list[Player],
    registry: Registry,
    double: bool = True,
) -> list[MatchResult]:
    """Play a round-robin tournament among ``players``.

    For every unordered pair ``(i, j)`` with ``i < j``, play one game with
    ``players[i]`` as white and ``players[j]`` as black. If ``double`` is true,
    also play the reverse-color return game (``players[j]`` white vs
    ``players[i]`` black).

    For ``N`` players this yields ``N*(N-1)`` games when ``double`` is true and
    ``N*(N-1)/2`` games otherwise. Results are returned in scheduling order.
    """
    results: list[MatchResult] = []
    n = len(players)
    for i in range(n):
        for j in range(i + 1, n):
            results.append(play_and_record(players[i], players[j], registry))
            if double:
                results.append(play_and_record(players[j], players[i], registry))
    return results


def random_pairings(
    players: list[Player],
    registry: Registry,
    n_games: int,
    rng: random.Random | None = None,
) -> list[MatchResult]:
    """Play ``n_games`` between randomly chosen distinct pairs of ``players``.

    For each game two distinct players are sampled and randomly assigned colors.
    Pass a seeded ``rng`` (``random.Random(...)``) for reproducible scheduling.
    """
    if len(players) < 2:
        raise ValueError("random_pairings requires at least two players")
    rng = rng if rng is not None else random.Random()
    results: list[MatchResult] = []
    for _ in range(n_games):
        white, black = rng.sample(players, 2)
        results.append(play_and_record(white, black, registry))
    return results
