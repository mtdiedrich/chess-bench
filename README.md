# chess-bench

An adversarial LLM chess tool. Pluggable "players" (random, scripted, or
LLM-backed via any provider) play full games of chess against each other. Every
game updates each player's Elo rating, producing a leaderboard. Chess rules are
handled by the [`python-chess`](https://pypi.org/project/chess/) library.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the module design.

## Quick Start

```powershell
# Create virtual environment
uv venv .venv

# Activate environment
.\.venv\Scripts\Activate.ps1

# Install dependencies (editable, with dev extras)
uv pip install -e .[dev]
```

## Usage

```powershell
# Play a single game between two players
uv run chess-bench play --white random --black random

# Run a tournament among N players
uv run chess-bench tournament --players 4

# Show the current leaderboard
uv run chess-bench leaderboard

# Register a new player
uv run chess-bench register --name my-player
```

## Development

```powershell
uv run pytest -v                                    # Run tests
uv run pytest --cov=chess_bench --cov-report=html   # Tests with coverage
uv run ruff check .                                 # Check code quality
uv run ruff format .                                # Format code
```
