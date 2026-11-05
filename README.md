# CricFun

Flask live cricket match dashboard with unique OBS browser-source overlays.

## Run locally
1. Python 3.11+
2. `python -m venv .venv` and activate it
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`; set a NEW `RAPIDAPI_KEY`
5. `python app.py`, then open http://127.0.0.1:5000

## Features
- Live and upcoming match discovery
- Match detail page with copyable OBS URL
- Responsive 1920x1080 OBS overlay polling every 3 seconds
- API key read from environment; never stored in source

## API setup
Subscribe to the RapidAPI products for `cricbuzz-cricket.p.rapidapi.com` and `free-cricbuzz-cricket-api.p.rapidapi.com`. Endpoint availability depends on your plan. If an endpoint is unavailable, the app reports an API error instead of displaying fake scores. The scorecard endpoint used is `cricket-match-scorecard?matchid=...`.

## Render
Deploy as a Python Web Service using `render.yaml`, then add `RAPIDAPI_KEY` in Render Environment. Never commit `.env`.

## Security
The uploaded source contained a hardcoded RapidAPI key. Treat it as compromised: revoke/rotate it immediately in RapidAPI and use the replacement only in environment variables.
