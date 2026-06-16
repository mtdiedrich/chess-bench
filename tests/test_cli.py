"""Tests for the chess_bench.cli module.

Sibling modules (match, players.base, registry, tournament) are not present
on this branch, so we register lightweight stub modules in sys.modules BEFORE
importing cli. This lets the CLI be exercised in isolation.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import pytest

# --------------------------------------------------------------------------- #
# Stub sibling modules before importing the CLI under test.
# --------------------------------------------------------------------------- #


@dataclass
class _FakeMatchResult:
    white: str = "white"
    black: str = "black"
    result: str = "1-0"
    moves: int = 10
    termination: str = "checkmate"
    pgn: str = "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0"

    def board_ascii(self) -> str:
        return "r n b q k b n r\n. . . . . . . ."


@dataclass
class _FakeRecord:
    name: str
    rating: float = 1000.0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    games: int = 0


class _FakeRegistry:
    _stores: dict[str, dict[str, _FakeRecord]] = {}

    def __init__(self, path: str) -> None:
        self.path = str(path)
        self._players = self._stores.setdefault(self.path, {})

    def get_or_create(self, name: str) -> _FakeRecord:
        if name not in self._players:
            self._players[name] = _FakeRecord(name=name)
        return self._players[name]

    def save(self) -> None:  # pragma: no cover - trivial
        pass

    def load(self) -> None:  # pragma: no cover - trivial
        pass

    def leaderboard(self) -> list[_FakeRecord]:
        return sorted(
            self._players.values(), key=lambda r: r.rating, reverse=True
        )


class _FakeRandomPlayer:
    def __init__(self, name: str, seed: int | None = None) -> None:
        self.name = name
        self.seed = seed


def _play_match(white, black, *args, **kwargs) -> _FakeMatchResult:
    return _FakeMatchResult(white=white.name, black=black.name)


def _play_and_record(white, black, registry) -> _FakeMatchResult:
    registry.get_or_create(white.name)
    registry.get_or_create(black.name)
    return _FakeMatchResult(white=white.name, black=black.name)


def _round_robin(players, registry, double=True) -> list:
    for p in players:
        registry.get_or_create(p.name)
    n = len(players) * (len(players) - 1)
    if not double:
        n //= 2
    return list(range(n))


def _install_stubs() -> None:
    match_mod = types.ModuleType("chess_bench.match")
    match_mod.play_match = _play_match
    match_mod.play_and_record = _play_and_record
    match_mod.MatchResult = _FakeMatchResult
    sys.modules["chess_bench.match"] = match_mod

    players_pkg = types.ModuleType("chess_bench.players")
    players_pkg.__path__ = []  # mark as package
    sys.modules["chess_bench.players"] = players_pkg

    base_mod = types.ModuleType("chess_bench.players.base")
    base_mod.RandomPlayer = _FakeRandomPlayer
    sys.modules["chess_bench.players.base"] = base_mod

    registry_mod = types.ModuleType("chess_bench.registry")
    registry_mod.Registry = _FakeRegistry
    registry_mod.PlayerRecord = _FakeRecord
    sys.modules["chess_bench.registry"] = registry_mod

    tournament_mod = types.ModuleType("chess_bench.tournament")
    tournament_mod.round_robin = _round_robin
    sys.modules["chess_bench.tournament"] = tournament_mod


_STUBBED_MODULES = (
    "chess_bench.match",
    "chess_bench.players",
    "chess_bench.players.base",
    "chess_bench.registry",
    "chess_bench.tournament",
)
_saved_modules = {name: sys.modules.get(name) for name in _STUBBED_MODULES}

_install_stubs()

from chess_bench import cli  # noqa: E402

# ``cli`` bound the stub references at its top-level import above, so its own
# tests keep using the stubs regardless of sys.modules afterwards. Restore the
# real modules now so these stubs don't leak into other test modules during the
# combined test run (e.g. shadowing the real ``chess_bench.players`` package).
for _name, _mod in _saved_modules.items():
    if _mod is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _mod


@pytest.fixture(autouse=True)
def _reset_registry_store():
    _FakeRegistry._stores = {}
    yield
    _FakeRegistry._stores = {}


def test_play_returns_zero_and_prints_result(capsys):
    rc = cli.main(["play", "--white", "random", "--black", "random", "--seed", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Result:" in out
    assert "1-0" in out
    assert "PGN:" in out


def test_leaderboard_prints_table(capsys, tmp_path):
    rc = cli.main(["leaderboard", "--registry", str(tmp_path / "lb.json")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Leaderboard" in out
    assert "Rank" in out
    assert "Rating" in out


def test_tournament_returns_zero(capsys, tmp_path):
    rc = cli.main(
        ["tournament", "--players", "3", "--seed", "1", "--registry", str(tmp_path / "lb.json")]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "games played" in out
    assert "Leaderboard" in out


def test_register_returns_zero(capsys, tmp_path):
    rc = cli.main(["register", "alice", "--registry", str(tmp_path / "lb.json")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alice" in out
