"""Tests for chess_bench.tournament.

The real ``chess_bench.match`` sibling module is not present on this branch, so
a stub module is registered in ``sys.modules`` before importing the tournament
module. The stub's ``play_and_record`` records each ``(white.name, black.name)``
pairing and returns a fake result, letting us assert on scheduling behaviour
without depending on un-merged siblings.
"""

from __future__ import annotations

import random
import sys
import types
from dataclasses import dataclass

import pytest


@dataclass
class _FakeResult:
    white: str
    black: str


class _Player:
    def __init__(self, name: str) -> None:
        self.name = name


class _Registry:
    """Minimal stand-in for chess_bench.registry.Registry."""


@pytest.fixture
def recorded():
    """Install a stub chess_bench.match and return its recording list.

    Reloads chess_bench.tournament against the stub so the module-level
    ``from chess_bench.match import play_and_record`` binds to the stub.
    """
    calls: list[tuple[str, str]] = []

    stub = types.ModuleType("chess_bench.match")

    def play_and_record(white, black, registry, **kw):
        calls.append((white.name, black.name))
        return _FakeResult(white.name, black.name)

    stub.play_and_record = play_and_record
    sys.modules["chess_bench.match"] = stub

    # Ensure tournament rebinds against the stub.
    sys.modules.pop("chess_bench.tournament", None)
    import chess_bench.tournament as tournament  # noqa: PLC0415

    try:
        yield tournament, calls
    finally:
        sys.modules.pop("chess_bench.match", None)
        sys.modules.pop("chess_bench.tournament", None)


def _players(*names: str) -> list[_Player]:
    return [_Player(n) for n in names]


def test_round_robin_double_plays_every_ordered_pair_once(recorded):
    tournament, calls = recorded
    players = _players("a", "b", "c")
    registry = _Registry()

    results = tournament.round_robin(players, registry, double=True)

    assert len(results) == 6
    assert len(calls) == 6
    # Every ordered pair of distinct players appears exactly once.
    expected = {(w, b) for w in "abc" for b in "abc" if w != b}
    assert set(calls) == expected
    assert len(set(calls)) == 6


def test_round_robin_single_plays_each_unordered_pair_once(recorded):
    tournament, calls = recorded
    players = _players("a", "b", "c")
    registry = _Registry()

    results = tournament.round_robin(players, registry, double=False)

    assert len(results) == 3
    assert len(calls) == 3
    # White is always the lower-indexed player.
    assert calls == [("a", "b"), ("a", "c"), ("b", "c")]


def test_round_robin_never_plays_self(recorded):
    tournament, calls = recorded
    players = _players("a", "b", "c", "d")
    registry = _Registry()

    tournament.round_robin(players, registry, double=True)

    assert all(w != b for w, b in calls)
    assert len(calls) == 4 * 3  # N*(N-1)


def test_random_pairings_plays_exactly_n_games_and_no_self_play(recorded):
    tournament, calls = recorded
    players = _players("a", "b", "c", "d")
    registry = _Registry()

    results = tournament.random_pairings(
        players, registry, n_games=5, rng=random.Random(123)
    )

    assert len(results) == 5
    assert len(calls) == 5
    assert all(w != b for w, b in calls)


def test_random_pairings_reproducible_with_same_seed(recorded):
    tournament, calls = recorded
    players = _players("a", "b", "c", "d")
    registry = _Registry()

    first = tournament.random_pairings(
        players, registry, n_games=5, rng=random.Random(42)
    )
    second = tournament.random_pairings(
        players, registry, n_games=5, rng=random.Random(42)
    )

    first_pairs = [(r.white, r.black) for r in first]
    second_pairs = [(r.white, r.black) for r in second]
    assert first_pairs == second_pairs
    # Recorded calls reflect both runs back to back.
    assert calls[:5] == calls[5:]


def test_random_pairings_requires_two_players(recorded):
    tournament, _calls = recorded
    with pytest.raises(ValueError):
        tournament.random_pairings(_players("solo"), _Registry(), n_games=3)
