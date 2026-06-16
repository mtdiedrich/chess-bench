"""Tests for chess_bench.prompts (move prompting/parsing)."""

from chess_bench.prompts import build_move_prompt, parse_move


def test_build_move_prompt_contains_fen_moves_and_turn():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    legal = ["e2e4", "d2d4", "g1f3", "b1c3"]
    prompt = build_move_prompt(fen, legal, "white")

    assert fen in prompt
    assert "white" in prompt
    for move in legal:
        assert move in prompt
    # Explicit UCI instruction present.
    assert "UCI" in prompt


def test_build_move_prompt_includes_history():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    legal = ["e7e5", "c7c5"]
    history = ["e2e4"]
    prompt = build_move_prompt(fen, legal, "black", history=history)
    assert "e2e4" in prompt


def test_parse_move_finds_uci_in_prose():
    legal = ["e2e4", "d2d4", "g1f3"]
    assert parse_move("I think the best move here is e2e4, opening up.", legal) == "e2e4"


def test_parse_move_uci_among_prose_g1f3():
    legal = ["g1f3", "e2e4", "d2d4"]
    assert parse_move("I'll play g1f3 then develop", legal) == "g1f3"


def test_parse_move_promotion_token():
    legal = ["e7e8q", "e7e8r", "a2a3"]
    assert parse_move("Promote with e7e8q for the win.", legal) == "e7e8q"


def test_parse_move_castling_kingside():
    legal = ["e1g1", "e1f1", "d1d2"]
    assert parse_move("I'll castle O-O now.", legal) == "e1g1"


def test_parse_move_castling_queenside():
    legal = ["e1c1", "e1d1", "d1d2"]
    assert parse_move("Time to castle O-O-O.", legal) == "e1c1"


def test_parse_move_castling_digit_notation():
    legal = ["e8g8", "e8f8"]
    assert parse_move("Black castles 0-0.", legal) == "e8g8"


def test_parse_move_castling_lowercase():
    legal = ["e1g1", "e1f1"]
    assert parse_move("I'll castle o-o.", legal) == "e1g1"


def test_parse_move_first_uci_token_wins():
    # Documented behavior: the first legal UCI token in the text wins.
    legal = ["e2e4", "d2d4"]
    assert parse_move("options: e2e4 or d2d4.", legal) == "e2e4"


def test_parse_move_none_when_no_move_mentioned():
    legal = ["e2e4", "d2d4", "g1f3"]
    assert parse_move("I am not sure what to do here.", legal) is None


def test_parse_move_unique_destination_square():
    # Only one legal move lands on f3.
    legal = ["g1f3", "e2e4", "d2d4"]
    assert parse_move("I'll play Nf3 to develop.", legal) == "g1f3"


def test_parse_move_ambiguous_destination_returns_none():
    # Two legal moves land on d2; bare "d2" is ambiguous.
    legal = ["c1d2", "b1d2", "e2e4"]
    assert parse_move("Maybe something to d2?", legal) is None


def test_parse_move_empty_inputs():
    assert parse_move("", ["e2e4"]) is None
    assert parse_move("e2e4", []) is None


def test_parse_move_uci_preferred_over_square():
    # Exact UCI token should win even if other squares are mentioned.
    legal = ["e2e4", "g1f3"]
    assert parse_move("Not f3, I'll go e2e4.", legal) == "e2e4"


def test_parse_move_robust_to_code_fence():
    legal = ["e2e4", "d2d4"]
    text = "```\ne2e4\n```"
    assert parse_move(text, legal) == "e2e4"
