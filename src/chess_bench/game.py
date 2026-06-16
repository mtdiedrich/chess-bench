"""Chess game wrapper around python-chess.

Provides :class:`ChessGame`, a thin convenience wrapper over
:class:`chess.Board` exposing UCI/SAN move pushing, legal-move enumeration,
game-state queries, and PGN/ASCII rendering. Illegal or unparseable moves are
surfaced uniformly via :class:`IllegalMoveError`.
"""

from __future__ import annotations

import chess
import chess.pgn


class IllegalMoveError(Exception):
    """Raised when a move is illegal in the current position or unparseable."""


class ChessGame:
    """A single chess game wrapping :class:`chess.Board`."""

    def __init__(self, fen: str | None = None) -> None:
        """Create a game from ``fen`` (defaults to the standard start)."""
        self._initial_fen: str | None = fen
        self.board: chess.Board = chess.Board(fen) if fen is not None else chess.Board()

    def legal_moves_uci(self) -> list[str]:
        """Return all legal moves in the current position as UCI strings."""
        return [move.uci() for move in self.board.legal_moves]

    def legal_moves_san(self) -> list[str]:
        """Return all legal moves in the current position as SAN strings."""
        return [self.board.san(move) for move in self.board.legal_moves]

    def push_uci(self, uci: str) -> None:
        """Apply the move given in UCI notation.

        Raises:
            IllegalMoveError: if ``uci`` is unparseable or not legal here.
        """
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise IllegalMoveError(f"Unparseable UCI move: {uci!r}") from exc
        if move not in self.board.legal_moves:
            raise IllegalMoveError(
                f"Illegal move {uci!r} in position {self.board.fen()!r}"
            )
        self.board.push(move)

    def push_san(self, san: str) -> None:
        """Apply the move given in SAN notation.

        Raises:
            IllegalMoveError: if ``san`` is unparseable, ambiguous, or illegal.
        """
        try:
            self.board.push_san(san)
        except (
            chess.IllegalMoveError,
            chess.InvalidMoveError,
            chess.AmbiguousMoveError,
            ValueError,
        ) as exc:
            raise IllegalMoveError(f"Illegal or invalid SAN move: {san!r}") from exc

    def is_game_over(self) -> bool:
        """Return whether the game has ended (checkmate, draw, etc.)."""
        return self.board.is_game_over()

    def result(self) -> str:
        """Return the game result ("1-0"/"0-1"/"1/2-1/2", or "*" if ongoing)."""
        return self.board.result()

    def fen(self) -> str:
        """Return the current position in FEN notation."""
        return self.board.fen()

    def turn(self) -> str:
        """Return the side to move ("white" or "black")."""
        return "white" if self.board.turn == chess.WHITE else "black"

    def move_history_uci(self) -> list[str]:
        """Return the moves played so far as UCI strings."""
        return [move.uci() for move in self.board.move_stack]

    def to_pgn(self) -> str:
        """Build and return a PGN string from the move stack."""
        game = chess.pgn.Game()
        if self._initial_fen is not None:
            game.setup(chess.Board(self._initial_fen))
        node: chess.pgn.GameNode = game
        for move in self.board.move_stack:
            node = node.add_variation(move)
        game.headers["Result"] = self.board.result()
        return str(game)

    def board_ascii(self) -> str:
        """Return a multi-line ASCII rendering of the board."""
        return str(self.board)
