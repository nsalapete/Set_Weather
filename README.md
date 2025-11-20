# Set Weaver – Anthropic x Spotify DJ Assistant

Set Weaver turns a DJ brief into a structured setlist by choreographing three Claude-powered agents plus Spotify search. You can use the CLI for quick experiments or the Flask chat UI to iterate on threads with saved history.

## Why it exists

- **Multi-agent workflow** – Strategist sequences the narrative, Library Agent digs the catalog, Transition Agent writes mix tactics.
- **Rich metadata** – Every track carries BPM, Camelot key, energy level, transition tips, FX, and DJ reminders.
- **Persistent workspace** – Login-protected UI with conversation history, animated thinking bar, and instant thread switching.
- **Spotify-ready** – Uses Search API out of the box, plus optional PKCE helpers for deeper OAuth scopes.

## Architecture snapshot

| Component | Purpose |
| --- | --- |
| `StrategistAgent` | Plans the full setlist, calls other agents/tools, validates JSON. |
| `LibraryAgent` | Queries Spotify (or fallbacks) for track suggestions. |
| `TransitionAgent` | Refines BPM/key flow and proposes FX + mix instructions. |
| CLI (`set_weaver.cli`) | Headless orchestrator for scripts or terminal usage. |
| Flask app (`set_weaver.web`) | Auth, SQLite persistence, chat UI, thread management. |

## Requirements

- Python 3.10+
- Anthropic key in `ANTHROPIC_API_KEY`
- Spotify credentials (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`)
- Optional knobs: `ANTHROPIC_MODEL`, `SET_WEAVER_ADMIN_USER`, `SET_WEAVER_ADMIN_PASSWORD`, or `SET_WEAVER_ENV` to point to a custom `.env`.

Minimal `.env` excerpt:

```env
ANTHROPIC_API_KEY=sk-ant-...
SPOTIFY_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
SPOTIFY_CLIENT_SECRET=yyyyyyyyyyyyyyyy
SET_WEAVER_ADMIN_USER=setweaver
SET_WEAVER_ADMIN_PASSWORD=setweaver123
```

## Install

```powershell
git clone https://github.com/nsalapete/Set_Weather.git
cd Set_Weather
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Run the CLI (quick brief)

```powershell
python -m set_weaver.cli "90 minute sunset slot, start at 118 BPM and peak at 125"
# optional flags
python -m set_weaver.cli "..." --compact
python -m set_weaver.cli "..." --override-title "Rooftop Flow"
```

## Run the web app

1. Ensure your `.env` (or exported variables) includes Anthropic + Spotify + admin credentials.
2. From the repo root:

	```powershell
	set FLASK_APP=set_weaver.web.app
	set FLASK_ENV=development
	python -m flask run
	```

3. Browse to `http://127.0.0.1:5000` and log in (defaults: `setweaver / setweaver123`).
4. Create threads, send prompts, rename/delete history entries; SQLite (`set_weaver.db`) keeps everything per user.

### Persistence quick facts

- `conversations_threads` stores per-user titles + timestamps.
- `messages` keeps ordered chat history (`user` / `assistant`), HTML, and metadata.
- Deleting a thread cascades its messages; creating/renaming happens through AJAX endpoints used by the UI.

## Spotify OAuth helper commands (optional)

```powershell
python -m set_weaver.cli spotify-auth-url --redirect-uri "http://127.0.0.1:8080/callback" --scope playlist-read-private

# After grabbing the `code` from your redirect:
python -m set_weaver.cli spotify-exchange-code --redirect-uri "http://127.0.0.1:8080/callback" --code "..." --code-verifier "..."
```

Use these if you need user-level scopes; store tokens securely and only pass `--client-secret` for confidential clients.

## Project layout

- `src/set_weaver/agents/` – Strategist, Library, Transition agents
- `src/set_weaver/schemas/` – Pydantic models (tracks, transitions, final reports)
- `src/set_weaver/tools/` – Spotify search + helper utilities
- `src/set_weaver/web/` – Flask blueprints, templates, static assets, SQLite models
- `src/set_weaver/cli/` – CLI entry points and helper commands

## Extending ideas

- Add more Anthropic tools (crowd energy detectors, venue constraints, etc.).
- Export setlists to Rekordbox/Engine Prime using the structured JSON.
- Swap SQLite for Postgres/MySQL before deploying multi-user hosting.

🎧 Happy mixing!
