# SUquid – Multiplayer Real-Time Quiz Game

**CS 408 Computer Networks** course project, Sabancı University, Fall 2025.

A client-server quiz game where multiple players connect to a server over TCP and answer questions in real time. The server distributes questions, collects answers, calculates scores and broadcasts a live scoreboard.

## Features

- **Multi-client TCP server:** each client is handled in its own thread; shared state is protected with locks.
- **JSON-based message protocol:** `JOIN`, `ACK`, `QUESTION`, `ANSWER`, `RESULT`, `SCOREBOARD`, `FINAL_RESULT`, `INFO`, `ERROR`, `END`.
- **Scoring:** 1 point per correct answer, plus a bonus for the first correct answer (number of connected players − 1).
- **Tie-aware ranking:** players with equal scores share the same rank.
- **Robust connection handling:** duplicate usernames are rejected, players cannot join a running game, and players who disconnect mid-game stay on the scoreboard as `(DISCONNECTED)`.
- **GUI (Tkinter):** server settings, game control, live scoreboard and server log on the server side.

## How to Run

Requirements: Python 3.

1. Start the server: `python server.py`
2. Enter IP and port, then click **Start Server**.
3. Start at least two clients: `python client.py`, then connect with a unique username.
4. On the server, set the question file and question count, then click **Start Game**.

## Question File Format

Each question takes 5 lines (see `quiz_qa demo.txt`):

    What is the capital of Türkiye?
    A - Istanbul
    B - Ankara
    C - Izmir
    Answer: B

## Revisions

After the first evaluation, I fixed the following issues:

- Game controls are now correctly re-enabled after a game ends.
- Invalid or empty question counts are rejected before the game starts.
- Tie-aware ranking was added (`sortRank`).
- Player removal was centralized in a single function, so disconnected players are handled consistently in every game state.
