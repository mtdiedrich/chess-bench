"""Tests for the match runner.

These tests exercise the real game mechanics via ``python-chess`` (install with
``uv pip install chess``). Because the sibling ``chess_bench.game`` module is not
present on this branch, a local ``ChessGame`` adapter implementing the shared
contract is injected into ``sys.modules`` before importing the match module.
The players and registry used here are local test doubles so the tests do not
depend on ``players/base.py`` or ``registry.py`` being present.
"""

from __future__ import annotations

import sys
import types

import chess
import chess.pgn


# --- Local real ChessGame adapter (shared-contract surface) -----------------


class IllegalMoveError(Exception):
    """Raised when an illegal UCI move is pushed."""


class ChessGame:
    """Adapter over python-chess implementing the shared ChessGame contract."""

    def __init__(self, fen: str | None = None) -> None:
        self._board = chess.Board(fen) if fen else chess.Board()
        self._moves: list[str] = []

    def is_game_over(self) -> bool:
        return self._board.is_game_over()

    def turn(self) -> str:
        return "white" if self._board.turn == chess.WHITE else "black"

    def push_uci(self, uci: str) -> None:
        try:
            move = chess.Move.from_uci(uci)
        except (ValueError, chess.InvalidMoveError) as exc:
            raise IllegalMoveError(uci) from exc
        if move not in self._board.legal_moves:
            raise IllegalMoveError(uci)
        self._board.push(move)
        self._moves.append(uci)

    def result(self) -> str:
        return self._board.result()

    def move_history_uci(self) -> list[str]:
        return list(self._moves)

    def to_pgn(self) -> str:
        return str(chess.pgn.Game.from_board(self._board))

    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    def is_stalemate(self) -> bool:
        return self._board.is_stalemate()

    def is_insufficient_material(self) -> bool:
        return self._board.is_insufficient_material()


# Inject a fake chess_bench.game module so match.py can import it.
_saved_game_mod = sys.modules.get("chess_bench.game")
_game_mod = types.ModuleType("chess_bench.game")
_game_mod.ChessGame = ChessGame
_game_mod.IllegalMoveError = IllegalMoveError
sys.modules["chess_bench.game"] = _game_mod

from chess_bench.match import MatchResult, play_and_record, play_match  # noqa: E402

# match.py bound the stub above at its top-level import; restore the real module
# so the stub doesn't leak into other test modules during the combined run.
if _saved_game_mod is None:
    sys.modules.pop("chess_bench.game", None)
else:
    sys.modules["chess_bench.game"] = _saved_game_mod


# --- Test doubles -----------------------------------------------------------


class ScriptedPlayer:
    """A player that returns a pre-scripted sequence of UCI moves."""

    def __init__(self, name: str, moves: list[str]) -> None:
        self.name = name
        self._moves = list(moves)
        self._idx = 0

    def choose_move(self, game: ChessGame) -> str:
        move = self._moves[self._idx]
        self._idx += 1
        return move


class RaisingPlayer:
    """A player whose choose_move raises."""

    def __init__(self, name: str) -> None:
        self.name = name

    def choose_move(self, game: ChessGame) -> str:
        raise RuntimeError("boom")


class FakeRegistry:
    """Records calls to record_result."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def record_result(self, white: str, black: str, result: str) -> None:
        self.calls.append((white, black, result))


# --- Tests ------------------------------------------------------------------


def test_scholars_mate_line_black_wins() -> None:
    white = ScriptedPlayer("White", ["f2f3", "g2g4"])
    black = ScriptedPlayer("Black", ["e7e5", "d8h4"])

    res = play_match(white, black)

    assert isinstance(res, MatchResult)
    assert res.result == "0-1"
    assert res.termination == "checkmate"
    assert res.moves == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert len(res.moves) == 4
    assert res.pgn.strip() != ""
    assert res.white == "White"
    assert res.black == "Black"


def test_illegal_move_white_forfeits() -> None:
    white = ScriptedPlayer("White", ["e2e5"])  # illegal opening move
    black = ScriptedPlayer("Black", ["e7e5"])

    res = play_match(white, black)

    assert res.result == "0-1"
    assert "forfeit" in res.termination.lower()
    assert res.moves == []


def test_illegal_move_black_forfeits() -> None:
    white = ScriptedPlayer("White", ["e2e4", "d2d4"])
    black = ScriptedPlayer("Black", ["e8e6"])  # illegal: king to empty square

    res = play_match(white, black)

    assert res.result == "1-0"
    assert "forfeit" in res.termination.lower()
    assert res.moves == ["e2e4"]


def test_empty_move_forfeits() -> None:
    white = ScriptedPlayer("White", [""])
    black = ScriptedPlayer("Black", ["e7e5"])

    res = play_match(white, black)

    assert res.result == "0-1"
    assert "forfeit" in res.termination.lower()


def test_raising_player_forfeits() -> None:
    white = RaisingPlayer("White")
    black = ScriptedPlayer("Black", ["e7e5"])

    res = play_match(white, black)

    assert res.result == "0-1"
    assert "forfeit" in res.termination.lower()


def test_max_moves_cap_is_draw() -> None:
    # Two players shuffle knights back and forth forever.
    white = ScriptedPlayer("White", ["g1f3", "f3g1"] * 10)
    black = ScriptedPlayer("Black", ["g8f6", "f6g8"] * 10)

    res = play_match(white, black, max_moves=4)

    assert res.result == "1/2-1/2"
    assert res.termination == "max_moves"
    assert len(res.moves) == 4


def test_play_and_record_calls_registry() -> None:
    white = ScriptedPlayer("White", ["f2f3", "g2g4"])
    black = ScriptedPlayer("Black", ["e7e5", "d8h4"])
    registry = FakeRegistry()

    res = play_and_record(white, black, registry)

    assert res.result == "0-1"
    assert registry.calls == [("White", "Black", "0-1")]
