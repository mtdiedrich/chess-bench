"""Match runner: play full chess games between two pluggable players.

A :class:`MatchResult` captures the outcome of a single game, including the
result string, the moves played (UCI), a termination label, and the PGN.
:func:`play_match` drives the game loop, handling forfeits when a player
returns an illegal/empty move or raises. :func:`play_and_record` additionally
records the result against a registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from chess_bench.game import ChessGame, IllegalMoveError


class Player(Protocol):
    """Minimal structural protocol for a player (see players/base.py)."""

    name: str

    def choose_move(self, game: ChessGame) -> str:  # pragma: no cover - protocol
        ...


class Registry(Protocol):
    """Minimal structural protocol for the Elo registry (see registry.py)."""

    def record_result(
        self, white: str, black: str, result: str
    ) -> Any:  # pragma: no cover - protocol
        ...


@dataclass
class MatchResult:
    """Outcome of a single game between two players."""

    white: str
    black: str
    result: str
    moves: list[str]
    termination: str
    pgn: str


def _termination_label(game: ChessGame) -> str:
    """Derive a simple termination label from a finished game.

    Only :meth:`is_game_over` and :meth:`result` are part of the shared
    contract, so any finer-grained predicates are probed defensively and a
    generic label is used when they are unavailable.
    """
    for predicate, label in (
        ("is_checkmate", "checkmate"),
        ("is_stalemate", "stalemate"),
        ("is_insufficient_material", "insufficient_material"),
    ):
        method = getattr(game, predicate, None)
        if callable(method):
            try:
                if method():
                    return label
            except Exception:
                pass
    return "game_over"


def play_match(
    white: Player,
    black: Player,
    max_moves: int = 200,
    start_fen: str | None = None,
) -> MatchResult:
    """Play a full game between ``white`` and ``black``.

    The side to move is asked for a UCI move via ``choose_move``. If that side
    returns an illegal or empty move, or raises, it forfeits and the opponent
    wins. If ``max_moves`` is reached without a result, the game is a draw.
    """
    game = ChessGame(start_fen)

    result: str | None = None
    termination: str | None = None

    move_count = 0
    while not game.is_game_over() and move_count < max_moves:
        to_move = white if game.turn() == "white" else black

        try:
            uci = to_move.choose_move(game)
        except Exception:
            uci = None

        if not uci:
            # Empty/None move: forfeit by the side to move.
            result = "0-1" if to_move is white else "1-0"
            termination = f"forfeit ({to_move.name} returned no move)"
            break

        try:
            game.push_uci(uci)
        except IllegalMoveError:
            result = "0-1" if to_move is white else "1-0"
            termination = f"forfeit ({to_move.name} played illegal move {uci})"
            break

        move_count += 1

    if result is None:
        if game.is_game_over():
            result = game.result()
            termination = _termination_label(game)
        else:
            # Hit the max_moves cap without a natural result.
            result = "1/2-1/2"
            termination = "max_moves"

    return MatchResult(
        white=white.name,
        black=black.name,
        result=result,
        moves=game.move_history_uci(),
        termination=termination,
        pgn=game.to_pgn(),
    )


def play_and_record(
    white: Player,
    black: Player,
    registry: Registry,
    **kwargs: Any,
) -> MatchResult:
    """Play a match and record its result against ``registry``."""
    match = play_match(white, black, **kwargs)
    registry.record_result(white.name, black.name, match.result)
    return match
