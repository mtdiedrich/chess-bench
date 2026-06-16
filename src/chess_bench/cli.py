"""Command-line interface for chess-bench.

Provides an argparse-based CLI with subcommands to play single matches,
run round-robin tournaments, register players, and display the leaderboard.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from chess_bench.match import play_and_record, play_match
from chess_bench.players.base import RandomPlayer
from chess_bench.registry import Registry
from chess_bench.tournament import round_robin

DEFAULT_REGISTRY = "leaderboard.json"


def _build_player(kind: str, name: str, seed: int | None) -> RandomPlayer:
    """Construct a player instance of the requested kind."""
    if kind == "random":
        return RandomPlayer(name, seed=seed)
    raise ValueError(f"Unknown player kind: {kind!r}")


def _result_board_ascii(result: object) -> str:
    """Best-effort extraction of a final-board ASCII rendering from a result.

    The MatchResult shape is owned by a sibling module; accommodate either a
    ``board_ascii()`` method or a plain ``board_ascii``/``board`` attribute.
    """
    candidate = getattr(result, "board_ascii", None)
    if callable(candidate):
        return str(candidate())
    if isinstance(candidate, str):
        return candidate
    board = getattr(result, "board", None)
    return board if isinstance(board, str) else ""


def _cmd_play(args: argparse.Namespace) -> int:
    """Run a single match between two players and print the outcome."""
    white = _build_player(args.white, "white", args.seed)
    black = _build_player(args.black, "black", args.seed)

    if args.registry:
        registry = Registry(args.registry)
        result = play_and_record(white, black, registry)
    else:
        result = play_match(white, black)

    print(f"Result: {result.result}")
    print(f"Termination: {result.termination}")
    print(f"Moves: {result.moves}")
    print()
    board = _result_board_ascii(result)
    if board:
        print(board)
        print()
    print("PGN:")
    print(result.pgn)
    return 0


def _cmd_tournament(args: argparse.Namespace) -> int:
    """Run a round-robin tournament among baseline players."""
    players = [
        _build_player("random", f"random-{i + 1}", args.seed)
        for i in range(args.players)
    ]
    registry = Registry(args.registry)
    results = round_robin(players, registry, double=args.double)

    games = len(results) if results is not None else 0
    print(f"Tournament complete: {games} games played.")
    print()
    _print_leaderboard(registry)
    return 0


def _cmd_leaderboard(args: argparse.Namespace) -> int:
    """Load a registry and print its ranked leaderboard."""
    registry = Registry(args.registry)
    if hasattr(registry, "load"):
        registry.load()
    _print_leaderboard(registry)
    return 0


def _cmd_register(args: argparse.Namespace) -> int:
    """Create (or fetch) a player record and persist the registry."""
    registry = Registry(args.registry)
    registry.get_or_create(args.name)
    registry.save()
    print(f"Registered player: {args.name}")
    return 0


def _print_leaderboard(registry: Registry) -> None:
    """Print a ranked leaderboard table for the given registry."""
    records = registry.leaderboard()
    header = f"{'Rank':<6}{'Name':<20}{'Rating':>8}  {'W':>4}{'L':>4}{'D':>4}{'Games':>7}"
    print("Leaderboard")
    print(header)
    print("-" * len(header))
    for rank, record in enumerate(records, start=1):
        print(
            f"{rank:<6}{record.name:<20}{record.rating:>8.1f}  "
            f"{record.wins:>4}{record.losses:>4}{record.draws:>4}{record.games:>7}"
        )


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="chess-bench",
        description="Adversarial LLM chess benchmarking tool.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    play = subparsers.add_parser("play", help="Play a single match.")
    play.add_argument("--white", default="random", help="White player kind.")
    play.add_argument("--black", default="random", help="Black player kind.")
    play.add_argument("--seed", type=int, default=None, help="Random seed.")
    play.add_argument(
        "--registry", default=None, help="Optional registry path to record the game."
    )
    play.set_defaults(func=_cmd_play)

    tournament = subparsers.add_parser(
        "tournament", help="Run a round-robin tournament."
    )
    tournament.add_argument(
        "--players", type=int, default=2, help="Number of baseline players."
    )
    tournament.add_argument("--seed", type=int, default=None, help="Random seed.")
    tournament.add_argument("--registry", default=DEFAULT_REGISTRY, help="Registry path.")
    tournament.add_argument(
        "--double",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Play each pairing twice (home/away).",
    )
    tournament.set_defaults(func=_cmd_tournament)

    leaderboard = subparsers.add_parser("leaderboard", help="Show the leaderboard.")
    leaderboard.add_argument(
        "--registry", default=DEFAULT_REGISTRY, help="Registry path."
    )
    leaderboard.set_defaults(func=_cmd_leaderboard)

    register = subparsers.add_parser("register", help="Register a player.")
    register.add_argument("name", help="Player name.")
    register.add_argument("--registry", default=DEFAULT_REGISTRY, help="Registry path.")
    register.set_defaults(func=_cmd_register)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and dispatch to the selected subcommand."""
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
