# BAC Tracker

A web app that estimates **blood alcohol content (BAC)** using the Widmark formula. Enter your weight and sex, log drinks (with time), and see your estimated BAC and a graph over time. Built for education and personal tracking — **never use in place of a breathalyzer; never drive after drinking.**

![BAC Tracker](https://img.shields.io/badge/python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-3.0+-green)

## Features

- **Widmark-style BAC math**: weight, sex (distribution ratio), standard drinks (14 g ethanol), 0.015%/hr elimination
- **Web UI**: set profile → add drinks (type, count, “hours ago”) → see current BAC, “sober in X hours,” and a live BAC-over-time chart
- **Modular core** (`bac_app/`): same logic can power CLI, API, or a future iOS app

## Quick start (local)

**If the project is already on your machine** (e.g. in `Documents\Projects\bac_tracker_web`), open PowerShell and run:

```powershell
cd C:\Users\noahw\Documents\Projects\bac_tracker_web
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

If you see an error about running scripts, run once: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, then try activating again.

**If you need to clone from GitHub** (install [Git for Windows](https://git-scm.com/download/win) first), then:

```powershell
cd C:\Users\noahw\Documents\Projects
git clone https://github.com/YOUR_USERNAME/bac_tracker_web.git
cd bac_tracker_web
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

**macOS / Linux (bash):**

```bash
cd /path/to/bac_tracker_web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser. Set weight and sex, then add drinks and watch the BAC curve update.

## Run online (deploy)

The app listens on `0.0.0.0` and respects the `PORT` environment variable, so it runs on:

- **Render**: New Web Service → connect repo → Build: `pip install -r requirements.txt`, Start: `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
- **Railway / Fly.io / Heroku**: Set `PORT`; start command: `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`

No database required; session is in-memory (single user per process).

## Project layout

| Path | Purpose |
|------|--------|
| `app.py` | Flask web app (routes, API) |
| `templates/`, `static/` | Web UI (HTML, CSS, JS, Chart.js) |
| `bac_app/` | Core logic: drinks, Widmark calculations, session, graph data |
| `bac_app/drinks.py` | Drink types, standard drink (14 g), grams from volume/ABV |
| `bac_app/calculations.py` | BAC at time, BAC curve, elimination rate |
| `bac_app/session.py` | Session (weight, sex, drink log), add drink, BAC now, curve |
| `bac_app/graph.py` | Curve data for chart; optional PNG export (matplotlib) |
| `bac_app/main.py` | CLI: `python -m bac_app.main --demo [--graph out.png]` |
| `code/` | Separate task-workflow scripts (scout/prioritize/execute) |

## API (for testing or integration)

- `GET /api/drink-types` — list drink types
- `POST /api/setup` — body: `{ "weight_lb": 160, "is_male": true }`
- `POST /api/drink` — body: `{ "drink_key": "beer", "count": 1, "hours_ago": 0 }`
- `GET /api/state` — current BAC, curve `[{t, bac}]`, hours until sober, drink count
- `POST /api/reset` — clear drinks (keep profile)

## Tests

With the venv activated:

```powershell
pip install -r requirements.txt
pytest tests/ -v
```

## License

MIT (or your choice). Include a `LICENSE` file in the repo if you specify one.
