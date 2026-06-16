# chess-bench Architecture

`chess-bench` is an adversarial LLM chess tool. Pluggable "players" play full
games of chess against each other. Every completed game updates each player's
Elo rating, producing a leaderboard. The design is provider-agnostic: baseline
players (random, scripted) and LLM-backed players (any provider) all implement
the same interface, and chess rules are delegated to the
[`python-chess`](https://pypi.org/project/chess/) library.

## Overview

```
            +-------------+
            |  Player(s)  |   choose_move(game) -> UCI
            +------+------+
                   |
        +----------v-----------+
        |       ChessGame      |   wraps chess.Board (rules, legality)
        +----------+-----------+
                   |
        +----------v-----------+
        |        Match         |   drives two players to a result
        +----------+-----------+
                   |
        +----------v-----------+
        |      Tournament      |   round-robin / random pairings
        +----------+-----------+
                   |
        +----------v-----------+      +-----------+
        |       Registry       +----->|   Elo     |
        |  (ratings on disk)   |      | (scoring) |
        +----------+-----------+      +-----------+
                   |
        +----------v-----------+
        |         CLI          |   play / tournament / leaderboard / register
        +----------------------+
```

All modules live under `src/chess_bench/`. Siblings import each other by full
path (e.g. `from chess_bench import elo`). `__init__.py` files are intentionally
minimal — there is no central re-export surface — so that independently
developed modules merge without conflict.

## Module Contracts

### `elo.py`
Elo rating math.

- `DEFAULT_RATING = 1200`
- `DEFAULT_K = 32`
- `expected_score(rating_a, rating_b) -> float` — expected score for A.
- `update_ratings(rating_a, rating_b, score_a, k=DEFAULT_K) -> tuple[float, float]`
  — `score_a` is `0`, `0.5`, or `1`; returns the new `(rating_a, rating_b)`.

### `game.py`
A thin wrapper over `chess.Board` exposing only what players and the match
loop need.

- `class IllegalMoveError(Exception)`
- `class ChessGame`
  - `__init__(fen=None)` — start position, or a FEN if provided.
  - `legal_moves_uci() -> list[str]`
  - `legal_moves_san() -> list[str]`
  - `push_uci(uci)` / `push_san(san)` — raise `IllegalMoveError` on illegal input.
  - `is_game_over() -> bool`
  - `result() -> str` — `"1-0"`, `"0-1"`, `"1/2-1/2"`, or `"*"` (in progress).
  - `fen() -> str`
  - `turn() -> str` — `"white"` or `"black"`.
  - `move_history_uci() -> list[str]`
  - `to_pgn() -> str`
  - `board_ascii() -> str`

### `prompts.py`
LLM prompt construction and move extraction.

- `build_move_prompt(fen, legal_moves, turn, history=None) -> str`
- `parse_move(text, legal_moves) -> str | None` — extract a legal UCI move from
  free-form model output, or `None` if none can be found.

### `players/base.py`
The player abstraction and non-LLM baselines.

- abstract `class Player` with attribute `name: str` and
  `choose_move(self, game) -> str` (returns UCI).
- `class RandomPlayer(Player)` — seedable, picks a uniformly random legal move.
- `class ScriptedPlayer(Player)` — plays a fixed, predetermined move sequence.

### `players/llm.py`
Provider-agnostic LLM players.

- `class LLMClient(Protocol)` with `complete(prompt) -> str`.
- `class MockLLMClient` — deterministic client for tests.
- `class LLMPlayer(Player)` — builds a prompt from the game, calls a client,
  parses the response into a legal move.
- Provider stubs `OpenAIClient` / `GoogleClient` / `AnthropicClient`, each
  behind lazy imports so the corresponding SDK is only required when that
  provider is actually used.

### `registry.py`
Persistent ratings store (JSON on disk).

- `@dataclass PlayerRecord(name, rating, wins, losses, draws, games)`
- `class Registry(path)`
  - `load()` / `save()`
  - `get_or_create(name) -> PlayerRecord`
  - `record_result(white, black, result, k=elo.DEFAULT_K)` — applies the Elo
    update and bumps win/loss/draw/game counters.
  - `leaderboard() -> list[PlayerRecord]` — sorted by rating, descending.

### `match.py`
Runs a single game between two players.

- `@dataclass MatchResult(white, black, result, moves, termination, pgn)`
- `play_match(white, black, max_moves=200, start_fen=None) -> MatchResult`
- `play_and_record(white, black, registry, **kw) -> MatchResult` — plays a
  match and records the outcome in the registry.

### `tournament.py`
Multi-game orchestration.

- `round_robin(players, registry, double=True) -> list[MatchResult]` — every
  player faces every other; `double=True` plays both color assignments.
- `random_pairings(players, registry, n_games, rng=None) -> list[MatchResult]`

### `cli.py`
`argparse` entrypoint.

- `main(argv=None)` with subcommands:
  - `play` — run a single game between two players.
  - `tournament` — run a tournament among N players.
  - `leaderboard` — print current ratings.
  - `register` — add a player to the registry.

The console script `chess-bench` is wired to `chess_bench.cli:main` in
`pyproject.toml`.

## Design Notes

- **Provider-agnostic LLM interface.** Players depend only on the `LLMClient`
  protocol (`complete(prompt) -> str`). Concrete providers are thin adapters
  loaded lazily, so adding a new provider never touches the game or match code,
  and no provider SDK is a hard dependency.
- **Rules live in `python-chess`.** `ChessGame` is the single seam to the chess
  engine; legality, termination, and PGN/FEN serialization are all delegated
  there. UCI is the canonical move format passed between players and the game.
- **Elo is the scoring substrate.** Matches produce a result string; the
  registry translates it into a score and applies `elo.update_ratings`, keeping
  rating math isolated and testable.
- **Minimal coupling at merge.** Modules import siblings by full path and avoid
  central re-exports, so the units composing this system integrate cleanly.
