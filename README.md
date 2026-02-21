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
python -m pytest -q -p no:debugging
```

Note: `-p no:debugging` avoids a local environment conflict if a separate top-level folder named `code/` exists on your machine.

## API Endpoints

- `GET /healthz`
- `GET /api/catalog`
- `POST /api/setup`
- `POST /api/drink`
- `GET /api/state`
- `GET /api/hangover-plan`
- `POST /api/reset`

## Deployment

The app is ready for platforms like Render/Railway/Fly/Heroku.

Start command:

```bash
gunicorn -w 1 -b 0.0.0.0:$PORT app:app
```

## Safety and Scope

- BAC varies by person, food intake, hydration, medications, and many other factors.
- This tool can under- or over-estimate real BAC.
- Use it for awareness only.

## License

MIT (see `LICENSE`).