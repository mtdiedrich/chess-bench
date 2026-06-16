"""Player registry and leaderboard.

Persists :class:`PlayerRecord` entries to a JSON file. Each recorded game
result updates both players' Elo ratings (via :mod:`chess_bench.elo`) and their
win/loss/draw/game counters, then writes the state back to disk.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from chess_bench import elo

# Valid result strings and the score they assign to the white (player A) side.
_RESULT_SCORES: dict[str, float] = {
    "1-0": 1.0,
    "0-1": 0.0,
    "1/2-1/2": 0.5,
}


@dataclass
class PlayerRecord:
    """A single player's rating and game tally."""

    name: str
    rating: float
    wins: int
    losses: int
    draws: int
    games: int


class Registry:
    """A collection of :class:`PlayerRecord` entries backed by a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: dict[str, PlayerRecord] = {}
        if self.path.exists():
            self.load()

    def load(self) -> None:
        """Load all records from the JSON file, replacing in-memory state."""
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._records = {
            entry["name"]: PlayerRecord(**entry) for entry in raw
        }

    def save(self) -> None:
        """Persist all records to the JSON file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(record) for record in self._records.values()]
        self.path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def get_or_create(self, name: str) -> PlayerRecord:
        """Return the record for ``name``, creating a default one if absent."""
        record = self._records.get(name)
        if record is None:
            record = PlayerRecord(
                name=name,
                rating=elo.DEFAULT_RATING,
                wins=0,
                losses=0,
                draws=0,
                games=0,
            )
            self._records[name] = record
        return record

    def record_result(
        self,
        white: str,
        black: str,
        result: str,
        k: float = elo.DEFAULT_K,
    ) -> None:
        """Record a game between ``white`` (player A) and ``black``.

        ``result`` must be one of ``"1-0"``, ``"0-1"`` or ``"1/2-1/2"``.
        Both players' ratings are updated via :func:`elo.update_ratings`, and
        their win/loss/draw/game counters are incremented, then the registry is
        persisted. Players that do not yet exist are created automatically.
        """
        if result not in _RESULT_SCORES:
            raise ValueError(f"unknown result string: {result!r}")

        white_record = self.get_or_create(white)
        black_record = self.get_or_create(black)
        score_a = _RESULT_SCORES[result]

        new_white, new_black = elo.update_ratings(
            white_record.rating, black_record.rating, score_a, k=k
        )
        white_record.rating = new_white
        black_record.rating = new_black

        if result == "1-0":
            white_record.wins += 1
            black_record.losses += 1
        elif result == "0-1":
            white_record.losses += 1
            black_record.wins += 1
        else:
            white_record.draws += 1
            black_record.draws += 1

        white_record.games += 1
        black_record.games += 1

        self.save()

    def leaderboard(self) -> list[PlayerRecord]:
        """Return records sorted by rating descending, tie-broken by name."""
        return sorted(
            self._records.values(),
            key=lambda record: (-record.rating, record.name),
        )
