"""Tests for chess_bench.registry.

A stub ``elo`` module is registered in ``sys.modules`` before importing the
registry so these tests run without the real sibling module present.
"""

import sys
import types

import pytest

# --- Install a stub elo module BEFORE importing registry. ---
_stub_elo = types.ModuleType("chess_bench.elo")
_stub_elo.DEFAULT_RATING = 1200
_stub_elo.DEFAULT_K = 32


def _update_ratings(rating_a, rating_b, score_a, k=_stub_elo.DEFAULT_K):
    expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))
    expected_b = 1.0 - expected_a
    score_b = 1.0 - score_a
    new_a = rating_a + k * (score_a - expected_a)
    new_b = rating_b + k * (score_b - expected_b)
    return new_a, new_b


_stub_elo.update_ratings = _update_ratings
_saved_elo = sys.modules.get("chess_bench.elo")
sys.modules["chess_bench.elo"] = _stub_elo

from chess_bench import registry  # noqa: E402
from chess_bench.registry import PlayerRecord, Registry  # noqa: E402

# registry.py bound the stub above at its top-level import; restore the real
# module so the stub doesn't leak into other test modules during the combined run.
if _saved_elo is None:
    sys.modules.pop("chess_bench.elo", None)
else:
    sys.modules["chess_bench.elo"] = _saved_elo


@pytest.fixture
def reg(tmp_path):
    return Registry(tmp_path / "registry.json")


def test_get_or_create_defaults(reg):
    rec = reg.get_or_create("alice")
    assert rec.rating == registry.elo.DEFAULT_RATING
    assert rec.wins == rec.losses == rec.draws == rec.games == 0
    # Returns the same instance on repeat.
    assert reg.get_or_create("alice") is rec


def test_record_result_win(reg):
    reg.record_result("white", "black", "1-0")
    white = reg.get_or_create("white")
    black = reg.get_or_create("black")

    assert white.rating > registry.elo.DEFAULT_RATING
    assert black.rating < registry.elo.DEFAULT_RATING
    assert white.wins == 1 and white.losses == 0 and white.games == 1
    assert black.losses == 1 and black.wins == 0 and black.games == 1


def test_record_result_loss(reg):
    reg.record_result("white", "black", "0-1")
    white = reg.get_or_create("white")
    black = reg.get_or_create("black")

    assert white.rating < registry.elo.DEFAULT_RATING
    assert black.rating > registry.elo.DEFAULT_RATING
    assert white.losses == 1 and black.wins == 1


def test_record_result_draw_conserves_sum(reg):
    reg.record_result("white", "black", "1/2-1/2")
    white = reg.get_or_create("white")
    black = reg.get_or_create("black")

    assert white.draws == 1 and black.draws == 1
    assert white.games == 1 and black.games == 1
    # Equal starting ratings + draw => ratings unchanged and sum conserved.
    assert white.rating + black.rating == pytest.approx(
        2 * registry.elo.DEFAULT_RATING
    )


def test_record_result_invalid_raises(reg):
    with pytest.raises(ValueError):
        reg.record_result("a", "b", "win")


def test_leaderboard_sorted_desc(reg):
    reg.record_result("strong", "weak", "1-0")
    board = reg.leaderboard()
    assert [r.name for r in board] == ["strong", "weak"]
    ratings = [r.rating for r in board]
    assert ratings == sorted(ratings, reverse=True)


def test_leaderboard_tie_break_by_name(reg):
    reg.get_or_create("charlie")
    reg.get_or_create("alice")
    reg.get_or_create("bob")
    # All equal rating -> stable tie-break by name ascending.
    assert [r.name for r in reg.leaderboard()] == ["alice", "bob", "charlie"]


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "registry.json"
    reg = Registry(path)
    reg.record_result("white", "black", "1-0")
    reg.record_result("white", "black", "1/2-1/2")
    reg.save()

    fresh = Registry(path)
    fresh.load()
    original = {r.name: r for r in reg.leaderboard()}
    loaded = {r.name: r for r in fresh.leaderboard()}

    assert original.keys() == loaded.keys()
    for name, rec in original.items():
        assert isinstance(loaded[name], PlayerRecord)
        assert loaded[name] == rec
