import os, re, time, threading
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from admin import admin_bp

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'change-this-secret-in-render')
app.register_blueprint(admin_bp)
API_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
CRICBUZZ_HOST = os.getenv("CRICBUZZ_HOST", "cricbuzz-cricket.p.rapidapi.com").strip()
MATCH_INFO_HOST = os.getenv("MATCH_INFO_HOST", "free-cricbuzz-cricket-api.p.rapidapi.com").strip()

# Cache each upstream endpoint to avoid repeatedly consuming RapidAPI quota.
_CACHE = {}
_CACHE_LOCK = threading.Lock()
CACHE_SECONDS = int(os.getenv("MATCH_CACHE_SECONDS", "60"))

class UpstreamAPIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

def api_get(host, path, params=None):
    cache_key = (host, path, tuple(sorted((params or {}).items())))
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and now - cached["time"] < CACHE_SECONDS:
            return cached["data"]

    if not API_KEY:
        raise UpstreamAPIError("RapidAPI key is not configured.", 401)

    try:
        response = requests.get(
            "https://" + host + "/" + path.lstrip("/"),
            headers={"X-RapidAPI-Key": API_KEY, "X-RapidAPI-Host": host},
            params=params or {}, timeout=15
        )
    except requests.RequestException:
        raise UpstreamAPIError("Could not connect to the cricket data provider.")

    if response.status_code == 429:
        # Keep serving the last successful response, if one exists, during a rate limit.
        with _CACHE_LOCK:
            cached = _CACHE.get(cache_key)
        if cached:
            return cached["data"]
        raise UpstreamAPIError("The cricket data provider rate limit was reached. Please wait and retry.", 429)
    if response.status_code in (401, 403):
        raise UpstreamAPIError("RapidAPI rejected the request. Check the subscription and API key.", response.status_code)
    if not response.ok:
        raise UpstreamAPIError("The cricket data provider returned an error.", response.status_code)

    try:
        data = response.json()
    except ValueError:
        raise UpstreamAPIError("The cricket data provider returned an invalid response.")

    with _CACHE_LOCK:
        _CACHE[cache_key] = {"time": now, "data": data}
    return data

def extract_matches(payload):
    found = []
    for group in payload.get("typeMatches", []) if isinstance(payload, dict) else []:
        for series in group.get("seriesMatches", []):
            wrapper = series.get("seriesAdWrapper") or {}
            for item in wrapper.get("matches", []):
                info = item.get("matchInfo") or {}
                if info:
                    found.append(info)
    return found

def normalize(info):
    a, b = info.get("team1") or {}, info.get("team2") or {}
    return {
        "id": str(info.get("matchId") or ""),
        "series": info.get("seriesName") or info.get("matchDesc") or "Cricket",
        "title": (a.get("teamName") or a.get("teamSName") or "Team 1") + " vs " + (b.get("teamName") or b.get("teamSName") or "Team 2"),
        "status": info.get("status") or info.get("state") or "Scheduled",
        "state": str(info.get("state") or "").lower(),
        "venue": (info.get("venueInfo") or {}).get("ground") or ""
    }

def get_matches(kind):
    endpoint = "matches/v1/live" if kind == "live" else "matches/v1/upcoming"
    return [normalize(x) for x in extract_matches(api_get(CRICBUZZ_HOST, endpoint))]

def load_match_lists():
    matches, errors = [], []
    for kind in ("live", "upcoming"):
        try:
            matches.extend(get_matches(kind))
        except UpstreamAPIError as exc:
            errors.append({"feed": kind, "message": str(exc), "status_code": exc.status_code})
        except Exception:
            errors.append({"feed": kind, "message": "Unable to load this match feed.", "status_code": None})
    unique = {m["id"]: m for m in matches if m.get("id")}
    return list(unique.values()), errors

def get_match_info(match_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(match_id)):
        raise ValueError("Invalid match ID")
    payload = api_get(MATCH_INFO_HOST, "cricket-match-info", {"matchid": match_id})
    data = payload.get("matchInfo") or payload.get("data") or payload
    return data if isinstance(data, dict) else {}

@app.route("/")
def index():
    matches, errors = load_match_lists()
    return render_template("index.html", matches=matches, errors=errors)

@app.route("/match/<match_id>")
def match_page(match_id):
    try:
        info = get_match_info(match_id)
        a, b = info.get("team1") or {}, info.get("team2") or {}
        match = {
            "id": match_id,
            "title": (a.get("teamName") or "Team 1") + " vs " + (b.get("teamName") or "Team 2"),
            "status": info.get("status") or info.get("state") or "Match",
            "series": info.get("seriesName") or "Cricket"
        }
    except Exception:
        match = {"id": match_id, "title": "Match details unavailable", "status": "Please try again shortly", "series": "Cricket"}
    return render_template("generate.html", match=match)

@app.route("/overlay/<match_id>")
def overlay(match_id):
    return render_template("overlay.html", match_id=match_id)

@app.route("/api/matches")
def matches_api():
    matches, errors = load_match_lists()
    response = jsonify({
        "matches": matches,
        "feeds": {
            "live": "available" if not any(e["feed"] == "live" for e in errors) else "temporarily_unavailable",
            "upcoming": "available" if not any(e["feed"] == "upcoming" for e in errors) else "temporarily_unavailable"
        },
        "message": "Some feeds are temporarily unavailable due to provider rate limits." if errors else None
    })
    response.headers["Cache-Control"] = "public, max-age=30"
    return response

@app.route("/api/overlay-data/<match_id>")
def overlay_data(match_id):
    try:
        info = get_match_info(match_id)
        try:
            score = api_get(MATCH_INFO_HOST, "cricket-match-scorecard", {"matchid": match_id})
        except UpstreamAPIError as exc:
            score = {"temporarilyUnavailable": True, "message": str(exc)}
        return jsonify({"matchInfo": info, "scorecard": score})
    except UpstreamAPIError as exc:
        return jsonify({"error": str(exc)}), exc.status_code or 502
    except Exception:
        return jsonify({"error": "Unable to load this match right now."}), 502

@app.route("/health")
def health():
    return jsonify({"status": "ok", "api_key_configured": bool(API_KEY), "cache_seconds": CACHE_SECONDS})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
