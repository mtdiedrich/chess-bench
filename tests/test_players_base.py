"""Tests for chess_bench.players.base baseline players."""

from __future__ import annotations

import pytest

from chess_bench.players.base import Player, RandomPlayer, ScriptedPlayer


class StubGame:
    """Minimal game stub exposing legal_moves_uci()."""

    def __init__(self, moves: list[str]) -> None:
        self._moves = moves

    def legal_moves_uci(self) -> list[str]:
        return list(self._moves)


LEGAL = ["e2e4", "d2d4", "g1f3", "c2c4", "b1c3"]


def test_player_is_abstract() -> None:
    """Player cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Player("p")  # type: ignore[abstract]


def test_random_player_returns_legal_move() -> None:
    """RandomPlayer always returns a move within legal_moves_uci()."""
    game = StubGame(LEGAL)
    player = RandomPlayer(seed=42)
    for _ in range(50):
        assert player.choose_move(game) in LEGAL


def test_random_player_reproducible_across_instances() -> None:
    """Two RandomPlayers with the same seed produce identical move sequences."""
    game = StubGame(LEGAL)
    p1 = RandomPlayer(name="a", seed=123)
    p2 = RandomPlayer(name="b", seed=123)
    seq1 = [p1.choose_move(game) for _ in range(20)]
    seq2 = [p2.choose_move(game) for _ in range(20)]
    assert seq1 == seq2


def test_random_player_independent_of_global_rng() -> None:
    """Different seeds generally yield different sequences."""
    game = StubGame(LEGAL)
    p1 = RandomPlayer(seed=1)
    p2 = RandomPlayer(seed=2)
    seq1 = [p1.choose_move(game) for _ in range(20)]
    seq2 = [p2.choose_move(game) for _ in range(20)]
    assert seq1 != seq2


def test_random_player_raises_when_no_moves() -> None:
    """RandomPlayer raises when there are no legal moves."""
    player = RandomPlayer(seed=0)
    with pytest.raises(IndexError):
        player.choose_move(StubGame([]))


def test_scripted_player_returns_moves_in_order() -> None:
    """ScriptedPlayer returns its moves in order."""
    script = ["e2e4", "g1f3", "f1c4"]
    player = ScriptedPlayer("scripted", script)
    game = StubGame(LEGAL)
    assert [player.choose_move(game) for _ in range(3)] == script


def test_scripted_player_raises_when_exhausted() -> None:
    """ScriptedPlayer raises IndexError once the script is exhausted."""
    player = ScriptedPlayer("scripted", ["e2e4"])
    game = StubGame(LEGAL)
    assert player.choose_move(game) == "e2e4"
    with pytest.raises(IndexError):
        player.choose_move(game)


def test_scripted_player_copies_input_list() -> None:
    """Mutating the caller's list does not affect the player's script."""
    moves = ["e2e4"]
    player = ScriptedPlayer("scripted", moves)
    moves.append("d2d4")
    game = StubGame(LEGAL)
    assert player.choose_move(game) == "e2e4"
    with pytest.raises(IndexError):
        player.choose_move(game)
