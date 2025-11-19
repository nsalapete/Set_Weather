"""Flask web interface for Set Weaver DJ assistant with persistence."""
from __future__ import annotations

import os
from datetime import timedelta
from functools import wraps

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from set_weaver.agents.library_agent import LibraryAgent
from set_weaver.agents.strategist_agent import StrategistAgent
from set_weaver.agents.transition_agent import TransitionAgent
from set_weaver.schemas.track_data import SetlistReport
from set_weaver.web import db

app = Flask(__name__)
app.secret_key = os.getenv("SET_WEAVER_SESSION_KEY", "set-weaver-secret")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Initialize agents (requires ANTHROPIC_API_KEY and SPOTIFY_CLIENT_* env vars)
try:
    library_agent = LibraryAgent()
    transition_agent = TransitionAgent()
    strategist = StrategistAgent(library_agent, transition_agent)
    agents_initialized = True
except Exception as init_error:
    print(f"⚠️  Warning: Could not initialize agents: {init_error}")
    print("⚠️  Please set ANTHROPIC_API_KEY, SPOTIFY_CLIENT_ID, and SPOTIFY_CLIENT_SECRET environment variables")
    library_agent = None
    transition_agent = None
    strategist = None
    agents_initialized = False

SUGGESTED_PROMPTS = [
    "Plan a 60 minute Afrohouse set starting at 112 BPM, building to 122 BPM with a dramatic vocal anthem.",
    "Create a deep house sunset mix with a steady 118 BPM groove and warm chords.",
    "Map out a 90 minute techno journey beginning near 124 BPM and concluding in an industrial 132 BPM peak.",
]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def initialize():
    db.init_db()


@app.before_request
def load_user():
    user_id = session.get("user_id")
    g.user = db.get_user_by_id(user_id) if user_id else None


def format_setlist(report: SetlistReport) -> str:
    """Format setlist as rich HTML for display in the chat."""
    tracks_html = ""
    for idx, entry in enumerate(report.setlist):
        transition_html = ""
        if entry.mix_out_instructions:
            mix = entry.mix_out_instructions
            transition_html = f"""
            <div class="transition-card">
                <div class="transition-header">🎚️ Mix Instructions</div>
                <div class="transition-grid">
                    <div class="transition-item">
                        <span class="label">Technique:</span>
                        <span class="value">{mix.mixing_technique}</span>
                    </div>
                    <div class="transition-item">
                        <span class="label">Key:</span>
                        <span class="value">{mix.key_compatibility}</span>
                    </div>
                    <div class="transition-item">
                        <span class="label">BPM:</span>
                        <span class="value">{mix.bpm_change:+.1f}</span>
                    </div>
                    <div class="transition-item">
                        <span class="label">Duration:</span>
                        <span class="value">{mix.mix_duration_bars} bars</span>
                    </div>
                    <div class="transition-item full-width">
                        <span class="label">FX:</span>
                        <span class="value">{mix.suggested_fx}</span>
                    </div>
                    <div class="transition-item full-width">
                        <span class="label">DJ Notes:</span>
                        <span class="value">{mix.notes_to_dj}</span>
                    </div>
                </div>
            </div>
            """
        
        tracks_html += f"""
        <div class="track-card">
            <div class="track-header">
                <div class="track-number">{idx + 1}</div>
                <div class="track-info">
                    <div class="track-title">{entry.track_artist} – {entry.track_title}</div>
                    <div class="track-meta">
                        <span class="badge">{entry.genre}</span>
                        <span class="badge">{entry.bpm} BPM</span>
                        <span class="badge">{entry.key_camelot}</span>
                        <span class="badge">Energy {entry.energy_level}/10</span>
                    </div>
                </div>
                <div class="track-time">{entry.start_time}</div>
            </div>
            {transition_html}
        </div>
        """
    
    return f"""
    <div class="setlist-report">
        <div class="setlist-header-card">
            <h3>{report.set_title}</h3>
            <div class="setlist-stats">
                <span>⏱️ {report.duration_minutes} minutes</span>
                <span>🎵 {len(report.setlist)} tracks</span>
            </div>
        </div>
        <div class="tracks-container">
            {tracks_html}
        </div>
    </div>
    """


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.verify_user(username, password)
        if user:
            session["user_id"] = user["user_id"]
            session.permanent = True
            return redirect(url_for("index"))
        error = "Invalid credentials"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    threads = db.get_threads_for_user(g.user["user_id"])
    active_thread = threads[0] if threads else None
    return render_template(
        "index.html",
        username=g.user["username"],
        threads=threads,
        active_thread=active_thread,
        suggestions=SUGGESTED_PROMPTS,
    )


@app.route("/threads", methods=["GET", "POST"])
@login_required
def threads_route():
    if request.method == "GET":
        return jsonify({"threads": db.get_threads_for_user(g.user["user_id"])}), 200

    data = request.get_json() or {}
    title = data.get("title", "New Thread")
    thread_id = db.create_thread(g.user["user_id"], title)
    thread = db.get_thread(thread_id)
    return jsonify({"thread": dict(thread)}) if thread else ("", 204)


@app.route("/threads/<int:thread_id>", methods=["PATCH", "DELETE"])
@login_required
def update_thread(thread_id: int):
    if request.method == "DELETE":
        db.delete_thread(thread_id)
        return ("", 204)

    data = request.get_json() or {}
    title = data.get("title", "New Thread")
    success = db.update_thread_title(thread_id, title)
    return jsonify({"success": success}), 200 if success else 404


@app.route("/thread/<int:thread_id>/messages", methods=["GET", "POST"])
@login_required
def thread_messages(thread_id: int):
    thread = db.get_thread(thread_id)
    if not thread:
        return jsonify({"error": "Thread not found"}), 404

    if request.method == "GET":
        return jsonify({"thread": dict(thread), "messages": db.get_messages_for_thread(thread_id)})

    data = request.get_json() or {}
    prompt = data.get("content", "").strip()
    if not prompt:
        return jsonify({"error": "Message content required"}), 400

    db.add_message(thread_id, "user", prompt)
    
    if not agents_initialized or not strategist:
        error_msg = "⚠️ AI agents are not initialized. Please configure ANTHROPIC_API_KEY, SPOTIFY_CLIENT_ID, and SPOTIFY_CLIENT_SECRET environment variables and restart the server."
        db.add_message(thread_id, "assistant", error_msg)
        return jsonify({
            "success": False,
            "error": "Agents not initialized",
            "messages": db.get_messages_for_thread(thread_id)
        })
    
    try:
        report = strategist.plan_set(prompt)
        ai_text = format_setlist(report)
        db.add_message(thread_id, "assistant", ai_text)
        return jsonify(
            {
                "success": True,
                "thread": dict(thread),
                "messages": db.get_messages_for_thread(thread_id),
            }
        )
    except Exception as exc:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Error in thread_messages: {error_details}")
        error_msg = f'<div class="error-message">Sorry, I encountered an error: {str(exc)}</div>'
        db.add_message(thread_id, "assistant", error_msg)
        return jsonify({
            "success": False,
            "error": str(exc),
            "messages": db.get_messages_for_thread(thread_id)
        })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
