"""Tests for chess_bench.players.llm.

Sibling modules ``chess_bench.players.base`` and ``chess_bench.prompts`` are not
on this branch. To keep the production import lines in ``llm.py`` exactly as they
must be post-merge, we register lightweight stub modules in ``sys.modules``
BEFORE importing ``llm``. This means ``llm`` resolves the real import paths to
our doubles instead of falling through to its local shim.
"""

from __future__ import annotations

import sys
import types

import pytest


# ---------------------------------------------------------------------------
# Stub sibling modules in sys.modules BEFORE importing the module under test.
# ---------------------------------------------------------------------------

def _install_base_stub() -> None:
    """Install a stub ``chess_bench.players.base`` exposing an abstract Player."""
    import abc

    base_mod = types.ModuleType("chess_bench.players.base")

    class Player(abc.ABC):
        def __init__(self, name: str) -> None:
            self.name = name

        @abc.abstractmethod
        def choose_move(self, game) -> str:  # noqa: ANN001
            ...

    base_mod.Player = Player
    sys.modules["chess_bench.players.base"] = base_mod


def _install_prompts_stub() -> None:
    """Install a stub ``chess_bench.prompts`` with build_move_prompt/parse_move."""
    prompts_mod = types.ModuleType("chess_bench.prompts")

    def build_move_prompt(fen, legal_moves, turn, history=None):
        return (
            f"FEN: {fen}\nTurn: {turn}\nHistory: {history}\n"
            f"Legal moves: {', '.join(legal_moves)}\nReply with one UCI move."
        )

    def parse_move(text, legal_moves):
        text = (text or "").strip()
        # Exact match first.
        if text in legal_moves:
            return text
        # Otherwise find any legal move appearing as a token in the text.
        for mv in legal_moves:
            if mv in text.split():
                return mv
        return None

    prompts_mod.build_move_prompt = build_move_prompt
    prompts_mod.parse_move = parse_move
    sys.modules["chess_bench.prompts"] = prompts_mod


_STUBBED_MODULES = ("chess_bench.players.base", "chess_bench.prompts")
_saved_modules = {name: sys.modules.get(name) for name in _STUBBED_MODULES}

_install_base_stub()
_install_prompts_stub()

from chess_bench.players import llm  # noqa: E402

# Restore the real sibling modules so these stubs don't leak into other test
# modules during the combined run (notably shadowing the real ``chess_bench.prompts``
# that ``test_prompts`` binds at collection time). ``llm`` imports ``prompts``
# lazily and the real ``parse_move`` is a superset of the stub, so the LLMPlayer
# tests below still behave correctly against the real module.
for _name, _mod in _saved_modules.items():
    if _mod is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _mod
from chess_bench.players.llm import (  # noqa: E402
    AnthropicClient,
    GoogleClient,
    LLMPlayer,
    MockLLMClient,
    OpenAIClient,
)


# ---------------------------------------------------------------------------
# Stub game.
# ---------------------------------------------------------------------------

class StubGame:
    """Minimal game double exposing the contract LLMPlayer depends on."""

    def __init__(self, legal_moves, fen="startpos-fen", turn="white", history=None):
        self._legal_moves = list(legal_moves)
        self._fen = fen
        self._turn = turn
        self._history = history if history is not None else []

    def fen(self):
        return self._fen

    def legal_moves_uci(self):
        return list(self._legal_moves)

    def turn(self):
        return self._turn

    def move_history_uci(self):
        return list(self._history)


# ---------------------------------------------------------------------------
# LLMPlayer behaviour.
# ---------------------------------------------------------------------------

def test_returns_legal_move_with_default_mock():
    game = StubGame(["e2e4", "d2d4", "g1f3"])
    client = MockLLMClient()  # default: first legal move detected in prompt
    player = LLMPlayer("mock", client)

    move = player.choose_move(game)

    assert move in game.legal_moves_uci()
    assert move == "e2e4"
    assert client.call_count == 1


def test_returns_configured_legal_move():
    game = StubGame(["e2e4", "d2d4", "g1f3"])
    client = MockLLMClient(move="g1f3")
    player = LLMPlayer("mock", client)

    assert player.choose_move(game) == "g1f3"


def test_illegal_then_legal_triggers_retry():
    game = StubGame(["e2e4", "d2d4"])
    # First response illegal, second is legal.
    client = MockLLMClient(responses=["z9z9", "d2d4"])
    player = LLMPlayer("mock", client, max_retries=3)

    move = player.choose_move(game)

    assert move == "d2d4"
    assert client.call_count == 2  # one retry happened
    # The retry prompt should contain a corrective note.
    assert "not a legal move" in client.prompts[1]


def test_all_illegal_falls_back_to_first_legal_move():
    game = StubGame(["e2e4", "d2d4"])
    client = MockLLMClient(responses=["nope", "still no", "bad", "wrong", "again"])
    player = LLMPlayer("mock", client, max_retries=3)

    move = player.choose_move(game)

    # Falls back to first legal move so the game never stalls.
    assert move == "e2e4"
    # initial attempt + 3 retries = 4 calls
    assert client.call_count == 4


def test_no_legal_moves_raises():
    game = StubGame([])
    client = MockLLMClient(responses=["whatever"])
    player = LLMPlayer("mock", client, max_retries=1)

    with pytest.raises(ValueError):
        player.choose_move(game)


# ---------------------------------------------------------------------------
# Provider stubs raise clear errors when SDK / key is missing.
# ---------------------------------------------------------------------------

def _block_import(monkeypatch, name):
    """Force ``import name`` to fail with ImportError."""
    import builtins

    real_import = builtins.__import__

    def fake_import(n, *args, **kwargs):
        if n == name or n.startswith(name + "."):
            raise ImportError(f"blocked import of {n}")
        return real_import(n, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_openai_client_missing_sdk_raises(monkeypatch):
    _block_import(monkeypatch, "openai")
    with pytest.raises(ImportError, match="openai"):
        OpenAIClient().complete("hi")


def test_google_client_missing_sdk_raises(monkeypatch):
    _block_import(monkeypatch, "google.generativeai")
    with pytest.raises(ImportError, match="google-generativeai"):
        GoogleClient().complete("hi")


def test_anthropic_client_missing_sdk_raises(monkeypatch):
    _block_import(monkeypatch, "anthropic")
    with pytest.raises(ImportError, match="anthropic"):
        AnthropicClient().complete("hi")


def test_client_protocol_is_satisfied_by_mock():
    assert isinstance(MockLLMClient(), llm.LLMClient)
