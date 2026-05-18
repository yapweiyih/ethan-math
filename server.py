"""MathError multiplayer backend server.

Serves the game HTML and provides API endpoints for real-time
room management across different browsers/devices.
Room data is stored in server memory (not localStorage).
User accounts are persisted in SQLite.
"""

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

import uvicorn

app = FastAPI(title="MathError Server")

# ─── SQLite database for persistent user accounts ───────────────────────────
DB_PATH = Path(__file__).parent / "mathdata.db"


@contextmanager
def get_db():
    """Context manager for SQLite connections with WAL mode."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the users table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username     TEXT PRIMARY KEY,
                password     TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                player_id    TEXT NOT NULL
            )
        """)


def generate_player_id() -> str:
    """Generate a 5-character alphanumeric player ID."""
    import random
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(chars) for _ in range(5))


# Initialize database on startup
init_db()

# ─── In-memory storage (shared across all clients) ──────────────────────────
rooms: dict[str, dict] = {}
invites: dict[str, list[dict]] = {}  # username -> list of invite dicts


# ─── Pydantic models ────────────────────────────────────────────────────────
class RoomCreate(BaseModel):
    """Payload for creating a new room."""

    room: dict


class JoinData(BaseModel):
    """Payload for a player joining a room."""

    username: str
    displayName: str
    playerId: str


class AnswerData(BaseModel):
    """Payload for submitting an answer to a question."""

    username: str
    qIndex: int
    correct: bool
    score: int
    timeout: bool = False
    selectedIdx: int = -1
    timeTaken: float = 0


class InviteData(BaseModel):
    """Payload for sending a room invite."""

    targetUser: str
    roomCode: str
    fromUser: str
    fromName: str


class UsernamePayload(BaseModel):
    """Generic payload containing just a username."""

    username: str


class AdvancePayload(BaseModel):
    """Payload for advancing to the next question (live mode)."""

    nextQuestion: int


class FinishPayload(BaseModel):
    """Payload for marking a player as finished."""

    username: str
    score: int = 0


class StartPayload(BaseModel):
    """Payload for starting a game."""

    host: str


# ─── Room Endpoints ─────────────────────────────────────────────────────────
@app.post("/api/rooms")
def create_room(data: RoomCreate) -> dict:
    """Create a new room with pre-generated questions."""
    room = data.room
    code = room.get("code", "")
    if not code:
        return {"error": "missing_code"}
    rooms[code] = room
    return {"ok": True, "code": code}


@app.get("/api/rooms/{code}")
def get_room(code: str) -> dict:
    """Get the current state of a room (used for polling)."""
    if code not in rooms:
        return {"error": "not_found"}
    return rooms[code]


@app.post("/api/rooms/{code}/join")
def join_room(code: str, data: JoinData) -> dict:
    """Join an existing room."""
    if code not in rooms:
        return {"error": "not_found"}
    room = rooms[code]
    if room["status"] != "waiting":
        return {"error": "already_started"}
    if not any(p["username"] == data.username for p in room["players"]):
        room["players"].append(
            {
                "username": data.username,
                "displayName": data.displayName,
                "playerId": data.playerId,
                "status": "joined",
            }
        )
    return {"ok": True}


@app.post("/api/rooms/{code}/leave")
def leave_room(code: str, data: UsernamePayload) -> dict:
    """Leave a room. Deletes room if empty."""
    if code not in rooms:
        return {"ok": True}
    room = rooms[code]
    room["players"] = [
        p for p in room["players"] if p["username"] != data.username
    ]
    if len(room["players"]) == 0:
        del rooms[code]
    return {"ok": True}


@app.delete("/api/rooms/{code}")
def delete_room(code: str) -> dict:
    """Delete a room entirely (host cleanup)."""
    rooms.pop(code, None)
    return {"ok": True}


@app.post("/api/rooms/{code}/delete")
def delete_room_post(code: str) -> dict:
    """Delete a room entirely (POST fallback for beacons)."""
    rooms.pop(code, None)
    return {"ok": True}


@app.post("/api/rooms/{code}/toggle-public")
def toggle_public(code: str) -> dict:
    """Toggle room between public and private."""
    if code not in rooms:
        return {"error": "not_found"}
    rooms[code]["isPublic"] = not rooms[code].get("isPublic", False)
    return {"ok": True, "isPublic": rooms[code]["isPublic"]}


@app.post("/api/rooms/{code}/add-invite")
def add_invite_to_room(code: str, data: UsernamePayload) -> dict:
    """Add a username to the room's invite list."""
    if code not in rooms:
        return {"error": "not_found"}
    username = data.username
    if username not in rooms[code].get("invites", []):
        rooms[code].setdefault("invites", []).append(username)
    return {"ok": True}


@app.post("/api/rooms/{code}/start")
def start_game(code: str, data: StartPayload) -> dict:
    """Start the game. Host only. Assigns teams if team mode."""
    if code not in rooms:
        return {"error": "not_found"}
    room = rooms[code]
    if room["host"] != data.host:
        return {"error": "not_host"}
    if len(room["players"]) < 2:
        return {"error": "not_enough_players"}

    # Assign teams if team mode
    if room["mode"] == "team":
        for i, p in enumerate(room["players"]):
            p["team"] = "Team A" if i % 2 == 0 else "Team B"

    room["status"] = "playing"
    room["currentQuestion"] = 0
    room["results"] = {}
    for p in room["players"]:
        room["results"][p["username"]] = {
            "score": 0,
            "correct": 0,
            "wrong": 0,
            "answers": [],
            "finished": False,
        }
    return {"ok": True}


@app.post("/api/rooms/{code}/answer")
def submit_answer(code: str, data: AnswerData) -> dict:
    """Submit an answer for a question."""
    if code not in rooms:
        return {"error": "not_found"}
    room = rooms[code]
    res = room.get("results", {}).get(data.username)
    if not res:
        return {"error": "player_not_found"}

    res["score"] = data.score
    if data.correct:
        res["correct"] += 1
    else:
        res["wrong"] += 1
    res["answers"].append(
        {
            "q": data.qIndex,
            "correct": data.correct,
            "timeout": data.timeout,
            "selectedIdx": data.selectedIdx,
            "timeTaken": data.timeTaken,
        }
    )
    return {"ok": True}


@app.post("/api/rooms/{code}/advance")
def advance_question(code: str, data: AdvancePayload) -> dict:
    """Advance to the next question (live mode, host only)."""
    if code not in rooms:
        return {"error": "not_found"}
    rooms[code]["currentQuestion"] = data.nextQuestion
    rooms[code]["phase"] = "answering"
    return {"ok": True, "currentQuestion": data.nextQuestion}


@app.post("/api/rooms/{code}/set-phase")
def set_phase(code: str, data: dict) -> dict:
    """Set the current phase of the room (answering/review)."""
    if code not in rooms:
        return {"error": "not_found"}
    rooms[code]["phase"] = data.get("phase", "answering")
    return {"ok": True}


@app.post("/api/rooms/{code}/finish")
def finish_player(code: str, data: FinishPayload) -> dict:
    """Mark a player as finished and check if all players are done."""
    if code not in rooms:
        return {"error": "not_found"}
    room = rooms[code]
    if data.username in room.get("results", {}):
        room["results"][data.username]["score"] = data.score
        room["results"][data.username]["finished"] = True

    # Check if all done
    all_done = all(
        room.get("results", {}).get(p["username"], {}).get("finished", False)
        for p in room["players"]
    )
    if all_done:
        room["status"] = "finished"
    return {"ok": True, "allDone": all_done}


@app.post("/api/rooms/{code}/end")
def end_game(code: str) -> dict:
    """Force-end the game (host only)."""
    if code not in rooms:
        return {"error": "not_found"}
    rooms[code]["status"] = "finished"
    return {"ok": True}


# ─── Invite Endpoints ───────────────────────────────────────────────────────
@app.post("/api/invites")
def send_invite(data: InviteData) -> dict:
    """Send a room invite to a target user."""
    target = data.targetUser
    if target not in invites:
        invites[target] = []
    if not any(i["roomCode"] == data.roomCode for i in invites[target]):
        invites[target].append(
            {
                "roomCode": data.roomCode,
                "fromUser": data.fromUser,
                "fromName": data.fromName,
                "timestamp": int(time.time() * 1000),
            }
        )
    return {"ok": True}


@app.get("/api/invites/{username}")
def get_invites(username: str) -> list[dict]:
    """Get pending invites for a user (filters expired >10min)."""
    user_invites = invites.get(username, [])
    now = int(time.time() * 1000)
    fresh = [i for i in user_invites if now - i["timestamp"] < 600000]
    invites[username] = fresh
    return fresh


@app.delete("/api/invites/{username}/{code}")
def clear_invite(username: str, code: str) -> dict:
    """Clear a specific invite for a user."""
    if username in invites:
        invites[username] = [
            i for i in invites[username] if i["roomCode"] != code
        ]
    return {"ok": True}


# ─── Auth Endpoints (persistent accounts in SQLite) ─────────────────────────
class AuthPayload(BaseModel):
    """Payload for login/register."""

    username: str
    password: str


class PasswordChangePayload(BaseModel):
    """Payload for changing password."""

    username: str
    oldPassword: str
    newPassword: str


class DisplayNamePayload(BaseModel):
    """Payload for updating display name."""

    username: str
    displayName: str


@app.post("/api/auth/register")
def auth_register(data: AuthPayload) -> dict:
    """Register a new account. Returns profile on success."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT username FROM users WHERE username = ?", (data.username,)
        ).fetchone()
        if existing:
            return {"error": "exists"}
        pid = generate_player_id()
        conn.execute(
            "INSERT INTO users (username, password, display_name, player_id) VALUES (?, ?, ?, ?)",
            (data.username, data.password, data.username, pid),
        )
        return {
            "ok": True,
            "username": data.username,
            "displayName": data.username,
            "playerId": pid,
        }


@app.post("/api/auth/login")
def auth_login(data: AuthPayload) -> dict:
    """Login with username/password. Returns profile on success."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT username, password, display_name, player_id FROM users WHERE username = ?",
            (data.username,),
        ).fetchone()
        if not row:
            return {"error": "not_found"}
        if row["password"] != data.password:
            return {"error": "wrong_password"}
        return {
            "ok": True,
            "username": row["username"],
            "displayName": row["display_name"],
            "playerId": row["player_id"],
        }


@app.post("/api/auth/verify")
def auth_verify(data: UsernamePayload) -> dict:
    """Verify a username exists (for auto-login). Returns profile."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT username, display_name, player_id FROM users WHERE username = ?",
            (data.username,),
        ).fetchone()
        if not row:
            return {"error": "not_found"}
        return {
            "ok": True,
            "username": row["username"],
            "displayName": row["display_name"],
            "playerId": row["player_id"],
        }


@app.post("/api/auth/password")
def auth_change_password(data: PasswordChangePayload) -> dict:
    """Change password for a user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT password FROM users WHERE username = ?", (data.username,)
        ).fetchone()
        if not row:
            return {"error": "not_found"}
        if row["password"] != data.oldPassword:
            return {"error": "wrong_password"}
        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (data.newPassword, data.username),
        )
        return {"ok": True}


@app.post("/api/auth/display-name")
def auth_update_display_name(data: DisplayNamePayload) -> dict:
    """Update display name for a user."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET display_name = ? WHERE username = ?",
            (data.displayName, data.username),
        )
        return {"ok": True}


@app.delete("/api/auth/user/{username}")
def auth_delete_user(username: str) -> dict:
    """Delete a user account permanently."""
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        return {"ok": True}


@app.get("/api/auth/lookup/{player_id}")
def auth_lookup_player(player_id: str) -> dict:
    """Look up a username by player ID (cross-browser)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT username, display_name FROM users WHERE player_id = ?",
            (player_id.upper(),),
        ).fetchone()
        if not row:
            return {"error": "not_found"}
        return {
            "ok": True,
            "username": row["username"],
            "displayName": row["display_name"],
        }


# ─── Serve static HTML ──────────────────────────────────────────────────────
@app.get("/")
def serve_index() -> FileResponse:
    """Serve the main game HTML file."""
    return FileResponse("math-madness.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
