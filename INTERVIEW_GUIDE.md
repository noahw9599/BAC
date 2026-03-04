# Interview Guide: BAC Tracker Web

Use this to answer lead-engineer style questions clearly and quickly.

## 30-Second Pitch

I built a mobile-first BAC safety app focused on real-world nights out: fast drink logging, conservative drive guidance, session persistence, and social safety tools (friends, groups, alerts, guardian view links).  
It is a full-stack Flask + JavaScript project with production deployment, Postgres support, and automated API tests.

## What I Built (Ownership)

- Product scope and iteration from MVP to deployed web app
- Backend API design and persistence model
- Frontend UX optimized for mobile/touch
- Deployment and production debugging
- Regression testing with `pytest`

## Architecture

- `app.py`: Flask routes, auth/session orchestration, API responses
- `bac_app/session.py`: active drinking session model and event handling
- `bac_app/calculations.py`: BAC calculations and curve helpers
- `bac_app/auth_store.py`: users, auth, saved sessions, social tables
- `static/app.js`: client state orchestration and UI behavior
- `templates/*.html`: app and login views
- `tests/test_api.py`: integration-style API and flow tests

## Data + Flow

1. User authenticates via `/api/auth/*`.
2. Drink events are posted to `/api/drink`.
3. Current state comes from `/api/state` (BAC, curve, guidance, tools).
4. Sessions auto-save and can be reviewed/loaded from history.
5. Social data (groups/friends/alerts) is persisted and loaded via `/api/social/*`.

## Key Technical Decisions

- One-tap logging as primary UX for noisy, time-constrained environments
- Conservative “awareness guidance” vs overpromising precision
- Modular domain files in `bac_app/` for maintainability
- SQLite locally, Postgres in production
- Test-first validation before pushing fixes

## Strong Debug Story (Use in Interview)

### Symptom
- Users reported first drink looked ignored, then second click showed two drinks.

### Root Cause Pattern
- Read-after-write UI lag: first write likely succeeded, but state view lagged.

### Fix
- Immediate optimistic count update after successful drink add.
- Followed by server state refresh and one guarded retry refresh if needed.
- Kept server as source of truth while improving perceived responsiveness.

### Result
- First action gives immediate feedback.
- Reconciliation still happens from backend state.

## Security + Privacy Talking Points

- Password-based auth with protected API routes
- Opt-in sharing model for social visibility
- Revoke-all privacy control
- Environment-based secret/config management

## What I Would Improve Next

1. Move active session state to stronger DB-backed event flow for consistency.
2. Add structured observability (request IDs, error monitoring, dashboards).
3. Add broader contract/load testing for social endpoints.
4. Tighten client state transitions to reduce race-condition surface area.

## 8 Common Questions and Answer Angles

1. Why this stack?
- Fast iteration, low overhead, clear full-stack ownership.

2. How did you structure the code?
- Routes in `app.py`, domain logic in `bac_app/*`, UI orchestration in `static/app.js`.

3. How do you prevent regressions?
- Pytest integration tests, incremental commits, verify-before-push.

4. How do you handle production issues?
- Reproduce, isolate path (client/server/config), patch minimally, retest, redeploy.

5. How do you think about tradeoffs?
- Prioritize safe guidance + usability; disclose estimation limits clearly.

6. What are the hardest parts technically?
- Session consistency across mobile browser behavior and state refresh timing.

7. What did you learn?
- Reliable UX requires both correct backend writes and immediate user feedback.

8. What would you do with more time?
- Observability, stronger state consistency model, and broader reliability tests.

## Demo Script (2 Minutes)

1. Register/login
2. Add a drink and show immediate BAC/state update
3. Open planning (“Need to be sharp”) and explain recommendation logic
4. Open social group tools and safety actions
5. Show saved session history

## Important Disclaimer

This app is educational and safety-oriented, not a medical/legal decision tool.
