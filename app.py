import requests
from flask import Flask, render_template

app = Flask(__name__)

# 🔹 ENTER YOUR API KEY HERE
API_KEY = "8ea2d63329msh588632da98602c7p1c8755jsn9c9cd4d911a2"

# 1. MATCH LIST (Fetching IDs)
def get_live_matches():
    url = "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/live"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
    }
    match_ids = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if 'typeMatches' in data:
            for group in data['typeMatches']:
                for series in group.get('seriesMatches', []):
                    series_info = series.get('seriesAdWrapper')
                    if series_info:
                        for m in series_info.get('matches', []):
                            info = m.get('matchInfo', {})
                            if info.get('state') != 'Result':
                                match_ids.append(info.get('matchId'))
        return match_ids
    except Exception as e:
        print("Error fetching match list:", e)
        return []

# 2. MATCH DETAIL (Using your provided API for specific details)
def get_match_info(match_id):
    url = f"https://free-cricbuzz-cricket-api.p.rapidapi.com/cricket-match-info?matchid={match_id}"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "free-cricbuzz-cricket-api.p.rapidapi.com"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        info = data.get("matchInfo", {})
        return {
            "id": match_id,
            "series": info.get("seriesName", "Cricket Series"),
            "title": f"{info.get('team1', {}).get('teamName')} vs {info.get('team2', {}).get('teamName')}",
            "status": info.get("status", "Live")
        }
    except Exception as e:
        print(f"Error fetching match {match_id}:", e)
        return None

# --- ROUTES ---

@app.route('/')
def index():
    match_ids = get_live_matches()
    matches = []
    # Fetching details for each ID
    for mid in match_ids:
        data = get_match_info(mid)
        if data:
            matches.append(data)
    return render_template('index.html', matches=matches)

@app.route('/generate/<match_id>')
def generate(match_id):
    match = get_match_info(match_id)
    return render_template('generate.html', match=match)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    