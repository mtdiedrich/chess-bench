"""LLM-backed chess players and provider client adapters.

This module defines:
  - ``LLMClient``: a structural protocol for "give me a completion for this prompt".
  - ``MockLLMClient``: a deterministic in-process client for tests.
  - ``LLMPlayer``: a ``Player`` that asks an ``LLMClient`` for a move, parses it,
    retries on illegal/unparseable responses, and falls back to a deterministic
    legal move so a game never stalls.
  - ``OpenAIClient`` / ``GoogleClient`` / ``AnthropicClient``: thin provider stubs
    that lazily import their SDK inside ``complete`` and raise a clear, actionable
    error when the SDK or API key is missing.

Import notes
------------
Post-merge, the canonical imports are::

    from chess_bench.players.base import Player
    from chess_bench import prompts

``prompts`` is imported lazily inside ``LLMPlayer.choose_move`` so that this
module stays importable even before the sibling ``prompts`` module lands on a
branch. ``Player`` is imported at module top with a guarded fallback to a local
abstract shim used ONLY when ``chess_bench.players.base`` is not yet present.
The fallback is behaviourally equivalent (name + abstract ``choose_move``) and
disappears as soon as the real ``base`` module exists at merge time.
"""

from __future__ import annotations

import abc
import os
from typing import Protocol, runtime_checkable

try:  # pragma: no cover - exercised implicitly depending on merge state
    from chess_bench.players.base import Player
except ImportError:  # pragma: no cover - fallback only used pre-merge
    class Player(abc.ABC):
        """Local abstract shim for ``chess_bench.players.base.Player``.

        Used ONLY when the real ``base`` module is not yet on the branch. The
        merged codebase imports the real ``Player`` above and never reaches this.
        """

        def __init__(self, name: str) -> None:
            self.name = name

        @abc.abstractmethod
        def choose_move(self, game) -> str:  # noqa: ANN001 - game type lives in sibling module
            ...


@runtime_checkable
class LLMClient(Protocol):
    """Structural protocol for anything that can complete a text prompt."""

    def complete(self, prompt: str) -> str:
        """Return a text completion for ``prompt``."""
        ...


class MockLLMClient:
    """Deterministic LLM client for tests.

    Two modes (mutually compatible — ``responses`` takes priority while it has
    entries left):

      * ``responses``: a preset list of strings returned in sequence on
        successive ``complete`` calls. Lets a test simulate, e.g., an
        illegal-then-legal exchange. Once exhausted, falls back to ``move`` /
        first-legal-move behaviour.
      * ``move``: a fixed move string to always return.

    Default behaviour (no ``responses`` / ``move``): detect the first legal move
    from the prompt and return it. ``LLMPlayer`` includes the legal moves in the
    prompt, so this yields a valid move without any configuration.
    """

    def __init__(
        self,
        move: str | None = None,
        responses: list[str] | None = None,
    ) -> None:
        self.move = move
        self.responses = list(responses) if responses is not None else None
        self.prompts: list[str] = []
        self.call_count = 0

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        self.call_count += 1

        if self.responses:
            return self.responses.pop(0)

        if self.move is not None:
            return self.move

        return self._first_legal_move_from_prompt(prompt)

    @staticmethod
    def _first_legal_move_from_prompt(prompt: str) -> str:
        """Best-effort: return the first UCI-looking token found in the prompt.

        Recognises tokens like ``e2e4``, ``g1f3``, ``e7e8q`` (promotion). This
        keeps the mock self-sufficient when the prompt lists the legal moves.
        """
        import re

        match = re.search(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", prompt)
        if match:
            return match.group(0)
        # Nothing recognisable; return empty so the player retries/falls back.
        return ""


class LLMPlayer(Player):
    """A ``Player`` that delegates move choice to an ``LLMClient``."""

    def __init__(self, name: str, client: LLMClient, max_retries: int = 3) -> None:
        super().__init__(name)
        self.client = client
        self.max_retries = max_retries

    def choose_move(self, game) -> str:  # noqa: ANN001 - game type lives in sibling module
        # Lazy import keeps this module importable before ``prompts`` lands.
        from chess_bench import prompts

        legal_moves = list(game.legal_moves_uci())
        fen = game.fen()
        turn = game.turn()
        history = game.move_history_uci()

        prompt = prompts.build_move_prompt(fen, legal_moves, turn, history=history)

        # One initial attempt plus ``max_retries`` retries.
        for attempt in range(self.max_retries + 1):
            text = self.client.complete(prompt)
            move = prompts.parse_move(text, legal_moves)
            if move is not None and move in legal_moves:
                return move
            # Append a corrective note for the next attempt.
            prompt = (
                f"{prompt}\n\n"
                f"Your previous response {text!r} was not a legal move. "
                f"You must reply with exactly one move in UCI notation chosen "
                f"from this list: {', '.join(legal_moves)}."
            )

        # Exhausted retries: fall back to a deterministic legal move so the
        # game never stalls. ``legal_moves`` is non-empty whenever it is the
        # player's turn to move.
        if legal_moves:
            return legal_moves[0]
        raise ValueError("No legal moves available; the game should already be over.")


class OpenAIClient:
    """Thin ``LLMClient`` adapter for the OpenAI API.

    The ``openai`` SDK is imported lazily inside ``complete`` so importing this
    module never requires the SDK to be installed.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key

    def complete(self, prompt: str) -> str:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "The 'openai' package is required to use OpenAIClient. "
                "Install it with: pip install openai"
            ) from exc

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No OpenAI API key found. Pass api_key=... to OpenAIClient or "
                "set the OPENAI_API_KEY environment variable."
            )

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


class GoogleClient:
    """Thin ``LLMClient`` adapter for Google's Generative AI API."""

    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key

    def complete(self, prompt: str) -> str:
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "The 'google-generativeai' package is required to use GoogleClient. "
                "Install it with: pip install google-generativeai"
            ) from exc

        api_key = self.api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No Google API key found. Pass api_key=... to GoogleClient or "
                "set the GOOGLE_API_KEY environment variable."
            )

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(prompt)
        return response.text or ""


class AnthropicClient:
    """Thin ``LLMClient`` adapter for the Anthropic API."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-latest",
        api_key: str | None = None,
        max_tokens: int = 1024,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "The 'anthropic' package is required to use AnthropicClient. "
                "Install it with: pip install anthropic"
            ) from exc

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No Anthropic API key found. Pass api_key=... to AnthropicClient "
                "or set the ANTHROPIC_API_KEY environment variable."
            )

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate any text blocks in the response.
        parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
        return "".join(parts)
