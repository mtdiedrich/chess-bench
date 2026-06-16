import chess_bench

def test_version_exists():
    assert hasattr(chess_bench, '__version__')