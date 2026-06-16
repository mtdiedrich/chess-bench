"""Baseline chess players.

This module defines the abstract :class:`Player` base class and two concrete
baseline implementations:

* :class:`RandomPlayer` -- picks a uniformly random legal move using its own
  :class:`random.Random` instance so games are reproducible and independent of
  global RNG state.
* :class:`ScriptedPlayer` -- replays a fixed list of UCI moves in order.

A player only needs the game object to expose ``legal_moves_uci() -> list[str]``.
To avoid importing :mod:`chess_bench.game` (which may require the optional
``chess`` dependency) at import time, we rely on a structural ``Protocol`` and a
``TYPE_CHECKING`` guard.
"""

from __future__ import annotations

import abc
import random
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    # Imported only for type checkers; never required at runtime.
    from chess_bench.game import ChessGame  # noqa: F401


@runtime_checkable
class GameLike(Protocol):
    """Structural type describing the minimal game interface a player needs."""

    def legal_moves_uci(self) -> list[str]:
        """Return the list of legal moves in the current position as UCI strings."""
        ...


class Player(abc.ABC):
    """Abstract base class for all chess players.

    Attributes:
        name: A human-readable identifier for the player.
    """

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def choose_move(self, game: GameLike) -> str:
        """Return the UCI string of the move this player chooses to play.

        Args:
            game: A game object exposing ``legal_moves_uci()``.

        Returns:
            A single UCI move string (e.g. ``"e2e4"``).
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"


class RandomPlayer(Player):
    """A player that selects a uniformly random legal move.

    The player owns a private :class:`random.Random` instance seeded with
    ``seed`` so that, given the same seed and the same sequence of positions,
    two instances produce identical moves -- independent of the global RNG.
    """

    def __init__(self, name: str = "RandomPlayer", seed: int | None = None) -> None:
        super().__init__(name)
        self._rng = random.Random(seed)

    def choose_move(self, game: GameLike) -> str:
        """Return a uniformly random move from ``game.legal_moves_uci()``.

        Raises:
            IndexError: If there are no legal moves available.
        """
        moves = game.legal_moves_uci()
        if not moves:
            raise IndexError(f"{self.name}: no legal moves available")
        return self._rng.choice(moves)


class ScriptedPlayer(Player):
    """A player that replays a predetermined sequence of UCI moves.

    On each call to :meth:`choose_move` the next move in ``moves`` is returned.
    Once the script is exhausted, any further call raises :class:`IndexError`.
    The ``game`` argument is accepted for interface compatibility but ignored;
    the scripted moves are not validated against the game's legal moves.
    """

    def __init__(self, name: str, moves: list[str]) -> None:
        super().__init__(name)
        self._moves: list[str] = list(moves)
        self._index: int = 0

    def choose_move(self, game: GameLike) -> str:
        """Return the next scripted move.

        Args:
            game: Ignored; present only to satisfy the :class:`Player` interface.

        Returns:
            The next UCI move string in the script.

        Raises:
            IndexError: If the script has been exhausted.
        """
        if self._index >= len(self._moves):
            raise IndexError(
                f"{self.name}: scripted moves exhausted after {len(self._moves)} move(s)"
            )
        move = self._moves[self._index]
        self._index += 1
        return move
