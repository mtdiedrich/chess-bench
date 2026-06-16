"""Move prompting and parsing for LLM chess players.

Pure stdlib (regex only) — no chess dependency. This module builds the
text prompt an LLM sees when asked to choose a move, and extracts the
chosen move from the LLM's free-text reply.

All moves are exchanged as UCI strings (e.g. ``"e2e4"``, ``"e7e8q"``).
"""

from __future__ import annotations

import re

__all__ = ["build_move_prompt", "parse_move"]

# A UCI move: from-square, to-square, optional promotion piece.
# e.g. e2e4, g1f3, e7e8q
_UCI_RE = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", re.IGNORECASE)

# A destination square, e.g. "f3", "d5". The square may be preceded by a
# SAN piece letter, file, or capture mark (e.g. the "f3" in "Nf3", the
# "d5" in "exd5"), so no leading word boundary is required; only a
# trailing boundary so we match the end of the square token.
_SQUARE_RE = re.compile(r"([a-h][1-8])\b", re.IGNORECASE)

# Castling notation, using either letter O/o or digit 0.
_CASTLE_RE = re.compile(r"\b([0Oo](?:-[0Oo]){1,2})\b")


def build_move_prompt(
    fen: str,
    legal_moves: list[str],
    turn: str,
    history: list[str] | None = None,
) -> str:
    """Build an instruction prompt asking an LLM to choose its next move.

    Args:
        fen: The board position in Forsyth-Edwards Notation.
        legal_moves: The legal moves available, as UCI strings.
        turn: The side to move, e.g. ``"white"`` or ``"black"``.
        history: Optional list of prior moves (UCI strings) in play order.

    Returns:
        A prompt string that includes the side to move, the FEN, the full
        list of legal moves, the optional move history, and an explicit
        instruction to reply with a single UCI move.
    """
    legal_str = " ".join(legal_moves)

    lines = [
        "You are a chess engine. It is your turn to move.",
        "",
        f"Side to move: {turn}",
        f"Position (FEN): {fen}",
    ]

    if history:
        lines.append(f"Moves so far: {' '.join(history)}")

    lines.extend(
        [
            "",
            "Legal moves (UCI):",
            legal_str,
            "",
            "Choose the best legal move from the list above.",
            "Reply with a single move in UCI notation (for example: e2e4).",
            "Output only that move and nothing else.",
        ]
    )

    return "\n".join(lines)


def parse_move(text: str, legal_moves: list[str]) -> str | None:
    """Extract a legal UCI move from free-text LLM output.

    The match is robust to surrounding prose and code fences. Supported
    forms, tried in order:

    1. An exact UCI token (e.g. ``e2e4``, ``e7e8q``) that is in
       ``legal_moves``. The first such token wins.
    2. Castling (``O-O`` / ``0-0`` / ``o-o`` king-side, ``O-O-O`` /
       ``0-0-0`` queen-side) mapped to the matching king move in ``legal_moves``
       (``e1g1`` / ``e8g8`` king-side, ``e1c1`` / ``e8c8`` queen-side).
    3. A bare destination square (e.g. ``f3``) — resolved only when
       exactly one legal move lands on that square; ambiguous mentions
       return ``None``.

    SAN piece letters (Nf3, exd5, ...) are not parsed as such; they are
    handled best-effort via the destination-square rule (the trailing
    square is matched against legal moves).

    Args:
        text: The raw LLM output.
        legal_moves: The legal moves available, as UCI strings.

    Returns:
        The canonical legal UCI move the text indicates, or ``None`` if
        no unambiguous legal move can be identified.
    """
    if not text or not legal_moves:
        return None

    # Normalise legal moves to lowercase for matching, but return the
    # caller's canonical form.
    canonical = {m.lower(): m for m in legal_moves}
    legal_lower = set(canonical)

    # 1) Exact UCI token.
    for match in _UCI_RE.finditer(text):
        token = match.group(1).lower()
        if token in legal_lower:
            return canonical[token]

    # 2) Castling.
    castle = _CASTLE_RE.search(text)
    if castle:
        marks = castle.group(1).count("-") + 1  # 2 -> O-O, 3 -> O-O-O
        if marks == 3:  # queen-side
            for cand in ("e1c1", "e8c8"):
                if cand in legal_lower:
                    return canonical[cand]
        else:  # king-side
            for cand in ("e1g1", "e8g8"):
                if cand in legal_lower:
                    return canonical[cand]

    # 3) Bare destination square — unique landing square only.
    # Collect destination squares mentioned in the text, in order, and
    # resolve the first one that maps to exactly one legal move.
    by_dest: dict[str, list[str]] = {}
    for m in legal_lower:
        dest = m[2:4]
        by_dest.setdefault(dest, []).append(m)

    for match in _SQUARE_RE.finditer(text):
        sq = match.group(1).lower()
        landing = by_dest.get(sq)
        if landing and len(landing) == 1:
            return canonical[landing[0]]

    return None
