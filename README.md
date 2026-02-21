# BAC Tracker Web

A production-style Flask app for estimating blood alcohol concentration (BAC) using a Widmark-based model.

This project is designed to demonstrate:
- clean backend API design
- modular domain logic (`bac_app/`)
- test coverage with `pytest`
- a practical frontend for real-time tracking and planning

Important: this is an educational estimator, not a medical device or legal tool. Never drive after drinking.

## Features

- BAC estimation from weight, sex, drink type, count, and timing
- Drink catalog with calories, carbs, and sugar
- BAC chart over time (Chart.js)
- "Need to be sharp" planner with stop-by guidance
- Night tools: hydration tracker and pace coach
- Local social tracking: friend group drink/water counters
- Installable mobile web app (PWA) with offline shell caching
- Per-user session isolation (safe for multi-user public testing)
- Account system (register/login/logout) with per-user saved sessions
- Persistent feedback API and admin feedback feed
- Social safety tab with group invite codes, friend network, and opt-in live sharing

## Tech Stack

- Python 3.10+
- Flask 3
- Vanilla JavaScript + Chart.js
- Pytest
- Gunicorn (deployment)

## Project Structure

```text
bac_tracker_web/
  app.py                  # Flask routes and API handlers
  bac_app/
    calculations.py       # BAC model and curve generation
    session.py            # session state + drink event operations
    catalog.py            # drink catalog + nutrition metadata
    drinks.py             # base drink definitions and conversion helpers
    hangover.py           # stop-by and risk guidance logic
    graph.py              # graph helper for optional static image export
  templates/
    index.html            # app UI shell
  static/
    app.js                # frontend interactions and API integration
    style.css             # styling
  tests/
    test_bac.py           # core math/session tests
    test_api.py           # API behavior tests
```

## Local Development

```powershell
cd C:\Users\noahw\Documents\Projects\bac_tracker_web
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Running Tests

```powershell
python -m pytest -q
```

If your local machine has a top-level folder named `code/`, run:

```powershell
python -m pytest -q -p no:debugging
```

## API Endpoints

- `GET /healthz`
- `GET /api/catalog`
- `POST /api/setup`
- `POST /api/drink`
- `GET /api/state`
- `GET /api/hangover-plan`
- `POST /api/reset`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/session/save`
- `GET /api/session/list`
- `GET /api/session/list?date=YYYY-MM-DD`
- `GET /api/session/dates`
- `POST /api/session/load`
- `POST /api/feedback`
- `GET /api/feedback/recent?token=...` (admin)

## Deployment (Render)

This repo includes `render.yaml` for one-click deployment.

1. Push to GitHub.
2. In Render, choose `New +` -> `Blueprint`.
3. Select this repo and deploy.
4. After deploy, open the generated URL and share it.
5. View tester feedback via:
   `https://<your-app>.onrender.com/api/feedback/recent?token=<ADMIN_TOKEN>`

User account data and saved BAC sessions are stored in SQLite on a mounted Render disk (`/var/data`).

Manual start command (if not using blueprint):

```bash
gunicorn -w 2 -b 0.0.0.0:$PORT app:app
```

## Mobile/PWA Notes

- On iPhone: open the deployed link in Safari, then `Share` -> `Add to Home Screen`.
- On Android: open in Chrome and tap `Install app` when prompted.

## Safety and Scope

- BAC varies by person, food intake, hydration, medications, and many other factors.
- This tool can under- or over-estimate real BAC.
- Use it for awareness only.

## License

MIT (see `LICENSE`).
