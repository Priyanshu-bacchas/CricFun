import os, re
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

load_dotenv()
app = Flask(__name__)
API_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
CRICBUZZ_HOST = os.getenv("CRICBUZZ_HOST", "cricbuzz-cricket.p.rapidapi.com").strip()
MATCH_INFO_HOST = os.getenv("MATCH_INFO_HOST", "free-cricbuzz-cricket-api.p.rapidapi.com").strip()

def api_get(host, path, params=None):
    if not API_KEY:
        raise RuntimeError("RAPIDAPI_KEY is not configured. Add it to .env or hosting environment.")
    response = requests.get("https://" + host + "/" + path.lstrip("/"),
        headers={"X-RapidAPI-Key": API_KEY, "X-RapidAPI-Host": host},
        params=params or {}, timeout=12)
    response.raise_for_status()
    return response.json()

def extract_matches(payload):
    found = []
    for group in payload.get("typeMatches", []) if isinstance(payload, dict) else []:
        for series in group.get("seriesMatches", []):
            wrapper = series.get("seriesAdWrapper") or {}
            for item in wrapper.get("matches", []):
                info = item.get("matchInfo") or {}
                if info: found.append(info)
    return found

def normalize(info):
    a, b = info.get("team1") or {}, info.get("team2") or {}
    return {"id": str(info.get("matchId") or ""), "series": info.get("seriesName") or info.get("matchDesc") or "Cricket",
        "title": (a.get("teamName") or a.get("teamSName") or "Team 1") + " vs " + (b.get("teamName") or b.get("teamSName") or "Team 2"),
        "status": info.get("status") or info.get("state") or "Scheduled", "state": str(info.get("state") or "").lower(),
        "venue": (info.get("venueInfo") or {}).get("ground") or ""}

def get_matches(kind):
    endpoint = "matches/v1/live" if kind == "live" else "matches/v1/upcoming"
    return [normalize(x) for x in extract_matches(api_get(CRICBUZZ_HOST, endpoint))]

def get_match_info(match_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(match_id)): raise ValueError("Invalid match ID")
    payload = api_get(MATCH_INFO_HOST, "cricket-match-info", {"matchid": match_id})
    data = payload.get("matchInfo") or payload.get("data") or payload
    return data if isinstance(data, dict) else {}

@app.route("/")
def index():
    matches, errors = [], []
    for kind in ("live", "upcoming"):
        try: matches.extend(get_matches(kind))
        except Exception as exc: errors.append(kind.title() + ": " + str(exc))
    unique = {m["id"]: m for m in matches if m.get("id")}
    return render_template("index.html", matches=list(unique.values()), errors=errors)

@app.route("/match/<match_id>")
def match_page(match_id):
    try:
        info = get_match_info(match_id)
        a, b = info.get("team1") or {}, info.get("team2") or {}
        match = {"id": match_id, "title": (a.get("teamName") or "Team 1") + " vs " + (b.get("teamName") or "Team 2"),
                 "status": info.get("status") or info.get("state") or "Match", "series": info.get("seriesName") or "Cricket"}
    except Exception as exc:
        match = {"id": match_id, "title": "Match details unavailable", "status": "API error", "series": str(exc)}
    return render_template("generate.html", match=match)

@app.route("/overlay/<match_id>")
def overlay(match_id):
    return render_template("overlay.html", match_id=match_id)

@app.route("/api/matches")
def matches_api():
    result, errors = [], []
    for kind in ("live", "upcoming"):
        try: result.extend(get_matches(kind))
        except Exception as exc: errors.append(str(exc))
    unique = {m["id"]: m for m in result if m.get("id")}
    return jsonify({"matches": list(unique.values()), "errors": errors})

@app.route("/api/overlay-data/<match_id>")
def overlay_data(match_id):
    try:
        info = get_match_info(match_id)
        try: score = api_get(MATCH_INFO_HOST, "cricket-match-scorecard", {"matchid": match_id})
        except Exception as exc: score = {"scorecardError": str(exc)}
        return jsonify({"matchInfo": info, "scorecard": score})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

@app.route("/health")
def health():
    return jsonify({"status": "ok", "api_key_configured": bool(API_KEY)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
