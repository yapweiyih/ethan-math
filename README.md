# MathError — Find the Wrong Equation!

A multiplayer math game where players race to find the incorrect equation. Features solo classic/custom modes and multiplayer private rooms with a moderator dashboard.

## Quick Start (Local Testing)

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Run the Server

```bash
uv run python server.py
```

The game will be available at **http://localhost:8080**

### Open in Browser

Open http://localhost:8080 in your browser. You can open multiple tabs or different browsers to test multiplayer features.

## How It Works

| Component | Storage | Description |
|-----------|---------|-------------|
| **User accounts** | SQLite (`mathdata.db`) | Username, password, display name, player ID — persists across server restarts |
| **Game rooms** | Server memory | Room state, questions, player answers — ephemeral, cleared on restart |
| **Game history** | Browser localStorage | High scores, game history — per-browser |
| **Friends** | Browser localStorage | Friend lists, requests — per-browser |

## Project Structure

```
├── server.py          # FastAPI backend (rooms, invites, auth APIs)
├── math-madness.html  # Single-file game (HTML + CSS + JS)
├── mathdata.db        # SQLite database (auto-created on first run)
├── pyproject.toml     # Python project config
└── Dockerfile         # Container deployment
```

## Game Modes

- **Classic** — Solo survival, increasing difficulty
- **Custom** — Choose topics (addition, multiplication, roots, powers, etc.) and time limits
- **Private Room** — Multiplayer with friends, moderator dashboard, live scoring

## Features

- Server-side accounts (login from any device)
- 5-character Player IDs for cross-browser friend/invite lookup
- Real-time multiplayer with polling-based sync
- Moderator dashboard with question review, statistics, leaderboard
- Speed bonuses, lightbulb power-ups, difficulty progression
- Chiptune music and sound effects
