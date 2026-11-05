import json, os, sqlite3
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash

admin_bp = Blueprint("admin", __name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "cricfun_admin.db")

def connect_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS overlay_settings (match_id TEXT PRIMARY KEY, config TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    return conn

def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("cricfun_admin"):
            return redirect(url_for("admin.admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

@admin_bp.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        expected_password = os.getenv("ADMIN_PASSWORD", "")
        expected_user = os.getenv("ADMIN_USERNAME", "admin")
        if not expected_password:
            flash("Set ADMIN_PASSWORD in Render Environment before login.")
        elif request.form.get("username") == expected_user and request.form.get("password") == expected_password:
            session["cricfun_admin"] = True
            return redirect(url_for("admin.admin_panel"))
        else:
            flash("Invalid username or password.")
    return render_template("admin_login.html")

@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin.admin_login"))

@admin_bp.route("/admin/panel")
@require_admin
def admin_panel():
    return render_template("admin.html")

@admin_bp.route("/api/admin-config/<match_id>")
def get_config(match_id):
    with connect_db() as conn:
        row = conn.execute("SELECT config FROM overlay_settings WHERE match_id=?", (match_id,)).fetchone()
    return jsonify(json.loads(row["config"]) if row else {})

@admin_bp.route("/api/admin-config/<match_id>", methods=["POST"])
@require_admin
def save_config(match_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or len(match_id) > 80:
        return jsonify({"error": "Invalid settings or match ID"}), 400
    allowed = {"team1_name","team2_name","team1_logo","team2_logo","score1","wickets1","overs1","score2","wickets2","overs2","target","crr","rrr","partnership","striker","striker_photo","striker_runs","striker_balls","non_striker","non_striker_photo","non_striker_runs","non_striker_balls","bowler","bowler_photo","bowler_figures","last_wicket","this_over","center_video_url","center_image_url","animation_enabled","manual_mode"}
    clean = {k: str(v).strip()[:1000] for k,v in data.items() if k in allowed and v is not None}
    with connect_db() as conn:
        conn.execute("INSERT INTO overlay_settings(match_id,config,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(match_id) DO UPDATE SET config=excluded.config,updated_at=CURRENT_TIMESTAMP", (match_id, json.dumps(clean)))
    return jsonify({"ok": True, "saved": len(clean)})
