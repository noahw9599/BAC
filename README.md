# BAC Tracker Web

Mobile-first BAC tracking web app focused on real-time safety decisions, session analytics, and group coordination.

Live Demo: https://bac-tracker-web.onrender.com

Quick Navigation:
- Live Demo: https://bac-tracker-web.onrender.com
- Quick Demo Flow: `#quick-demo-60-seconds`
- Architecture: `#architecture-high-level`
- Local Setup: `#local-development`
- Tests: `#test-commands`
- Deployment: `#deployment-render`

Built as an internship portfolio project to demonstrate:
- end-to-end product ownership (backend + frontend + deployment)
- practical system design for stateful user workflows
- disciplined testing and iterative feature delivery

Important: this is an educational estimator, not a legal or medical device. Never drive after drinking.

## What Makes This Project Strong

- Production-style Flask API with clear route boundaries
- Persistent account system (email/password auth)
- Session lifecycle model with auto-save + expiration rules
- Pace-aware planner logic (not just static rules)
- Social safety features (groups, alerts, guardian links, friend network)
- Mobile-focused UX with tabbed navigation and collapsible sections
- Meaningful automated coverage with `pytest`

## Core Features

### Real-Time BAC Tracking
- BAC curve using Widmark-style modeling
- Drink catalog (calories, carbs, sugar)
- Live BAC chart + legal-limit overlay
- Drive-risk guidance messaging

### Smart Planner
- "Need to be sharp" planning based on target date/time
- Pace-aware stop-by recommendation that updates as drinks are logged
- Debrief endpoint for post-session suggestions

### Session Lifecycle
- Auto-start on first drink
- Auto-save after drink events and periodic refresh
- Auto-expire active session after:
  - 3 hours inactivity, or
  - 12 hours max active duration
- History view for closed sessions
- Optional manual named saves and reload

### Social Safety
- Friend requests by email or username
- Invite links for one-tap friend add (`?invite=<code>`)
- Group creation/join via invite codes
- Group member check actions (`check`, `water`, `ride`)
- Group alerts including threshold alerts for high BAC
- Guardian read-only links with optional browser notifications
- Privacy kill-switch to revoke all sharing

### Mobile Web App
- PWA install support (iOS/Android)
- Sticky bottom tab nav
- Touch-friendly controls and condensed mobile layout

## Tech Stack

- Python 3.10+
- Flask 3
- SQLite
- Vanilla JavaScript + Chart.js
- Pytest
- Gunicorn (deployment)

## Architecture (High Level)

```text
Browser (PWA UI)
  -> static/app.js (state + UI orchestration)
  -> Flask routes in app.py
       -> bac_app/session.py       (current-session modeling)
       -> bac_app/calculations.py  (BAC math)
       -> bac_app/hangover.py      (planner logic)
       -> bac_app/auth_store.py    (auth, sessions, social persistence)
       -> bac_app/catalog.py       (drink metadata)
  -> SQLite (users, sessions, social graph, alerts, guardian links)
```

## Project Structure

```text
bac_tracker_web/
  app.py
  bac_app/
    auth_store.py
    calculations.py
    session.py
    hangover.py
    catalog.py
    drinks.py
  templates/
    index.html
    guardian.html
  static/
    app.js
    style.css
    manifest.webmanifest
    sw.js
  tests/
    test_api.py
    test_bac.py
```

## Quick Demo (60 Seconds)

1. Register account (name/email/password/gender/weight)
2. Add a few drinks on `Now`
3. Set a target time in "Need to be sharp"
4. Open `Social` and create a group
5. Create a guardian link and open it in a new tab
6. Check `History` and verify session behavior

## Local Development

```powershell
cd C:\Users\noahw\Documents\Projects\bac_tracker_web
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Test Commands

```powershell
python -m pytest -q
```

If your machine has a top-level `code/` folder:

```powershell
python -m pytest -q -p no:debugging
```

## API Highlights

- Auth: `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`
- Tracking: `/api/setup`, `/api/drink`, `/api/state`, `/api/reset`
- Sessions: `/api/session/save`, `/api/session/list`, `/api/session/dates`, `/api/session/load`, `/api/session/debrief`
- Social:
  - `/api/social/status`, `/api/social/feed`
  - `/api/social/request`, `/api/social/request/respond`
  - `/api/social/user-lookup`, `/api/social/invite/accept`
  - `/api/social/groups/*`, `/api/guardian/<token>`
- Safety utilities: `/api/campus/presets`, `/api/social/privacy/revoke-all`

## Deployment (Render)

`render.yaml` is included for blueprint deployment.

1. Push `main` to GitHub
2. In Render: `New +` -> `Blueprint`
3. Select this repo
4. Deploy

### Render Free Tier Persistence (Recommended)

If you are on Render free tier and cannot attach a disk, use managed Postgres:

1. Create a Render Postgres database.
2. In your web service `Environment`, set:
   - `APP_DB_PATH=<your Postgres connection string>`
   - or `DATABASE_URL=<your Postgres connection string>` (app supports this fallback)
3. Keep `SESSION_COOKIE_SECURE=1` for HTTPS deployments.
4. Do not use `/tmp/*.db` for auth/session data if you need persistence.

For feedback feed:

`https://<your-app>.onrender.com/api/feedback/recent?token=<ADMIN_TOKEN>`

## Safety + Scope Notes

- Real BAC varies by many factors not fully modeled here.
- Results should be treated as conservative awareness guidance only.
- Never use this app as legal proof that driving is safe.

## License

MIT (see `LICENSE`)
