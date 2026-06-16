"""Tests for the ChessGame wrapper."""

import pytest

from chess_bench.game import ChessGame, IllegalMoveError


def test_fresh_game_has_twenty_legal_moves_and_white_to_move() -> None:
    game = ChessGame()
    assert len(game.legal_moves_uci()) == 20
    assert game.turn() == "white"
    assert game.is_game_over() is False
    assert game.result() == "*"


def test_push_uci_flips_turn_and_records_history() -> None:
    game = ChessGame()
    game.push_uci("e2e4")
    assert game.turn() == "black"
    assert "e2e4" in game.move_history_uci()
    assert game.move_history_uci() == ["e2e4"]


def test_illegal_push_uci_raises() -> None:
    game = ChessGame()
    with pytest.raises(IllegalMoveError):
        game.push_uci("e2e5")


def test_unparseable_push_uci_raises() -> None:
    game = ChessGame()
    with pytest.raises(IllegalMoveError):
        game.push_uci("not-a-move")


def test_push_san_works() -> None:
    game = ChessGame()
    game.push_san("Nf3")
    assert game.move_history_uci() == ["g1f3"]
    assert game.turn() == "black"


def test_illegal_push_san_raises() -> None:
    game = ChessGame()
    with pytest.raises(IllegalMoveError):
        game.push_san("Nf6")


def test_legal_moves_san_fresh_game() -> None:
    game = ChessGame()
    san_moves = game.legal_moves_san()
    assert len(san_moves) == 20
    assert "Nf3" in san_moves
    assert "e4" in san_moves


def test_scholars_mate_line_ends_game_black_wins() -> None:
    game = ChessGame()
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        game.push_uci(uci)
    assert game.is_game_over() is True
    assert game.result() == "0-1"


def test_to_pgn_returns_nonempty_string_with_moves() -> None:
    game = ChessGame()
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        game.push_uci(uci)
    pgn = game.to_pgn()
    assert isinstance(pgn, str)
    assert pgn.strip() != ""
    assert "f3" in pgn
    assert "Qh4" in pgn
    assert "0-1" in pgn


def test_board_ascii_is_multiline_string() -> None:
    game = ChessGame()
    ascii_board = game.board_ascii()
    assert isinstance(ascii_board, str)
    assert "\n" in ascii_board
    assert len(ascii_board.splitlines()) == 8


def test_fen_roundtrip() -> None:
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    game = ChessGame(fen)
    assert game.fen() == fen
    assert game.turn() == "black"
