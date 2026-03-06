# BAC Tracker Pilot Readiness Checklist

Use this before inviting real users for nights-out testing.

## 1) Safety Guardrails
- [x] In-app warning visible on live tracking screen.
- [x] Drive check clearly states educational/non-legal use.
- [x] High-risk BAC alert shown when BAC >= 0.08.
- [x] Critical risk message shown at higher BAC tiers.
- [x] One-tap emergency call action (`911`) available.
- [x] Ride/campus help quick action available.

## 2) Accounts + Persistence
- [ ] Confirm production DB is persistent (not `/tmp`).
- [ ] Register/login/logout works on two separate devices.
- [ ] Account session stays active after browser restart.
- [ ] Password reset flow validated end-to-end in production.

## 3) Privacy + Sharing
- [x] Sharing defaults are opt-in.
- [x] Privacy revoke-all control exists.
- [ ] Publish short privacy policy in repo/site.
- [ ] Confirm friend/group visibility behavior with test users.

## 4) Reliability
- [x] Automated test suite passing locally.
- [ ] Review production logs for any 500 errors over 24h.
- [ ] Validate DB backup/restore path.
- [ ] Confirm error monitoring alerts are configured.

## 5) Mobile Test Protocol
- [ ] Test on iPhone + Android on cellular data.
- [ ] Validate PWA install and relaunch behavior.
- [ ] Verify all key buttons are easy to tap one-handed.
- [ ] Run 1 pilot weekend with 5-10 trusted testers.
- [ ] Collect issue reports and prioritize fixes before broader sharing.

## 6) Bar-Environment Functional Gate (Must Pass Before Sharing)
- [ ] Login/register works without page loops on mobile Safari + Chrome.
- [ ] First drink tap logs immediately (no delayed double-add behavior).
- [ ] Quick-add top 6 drinks can be tapped repeatedly under slow network.
- [ ] Sip mode (`15`/`30` min) correctly shifts BAC curve and sober ETA.
- [ ] Session auto-save persists after refresh and device lock/unlock.
- [ ] History tab shows today session and can reload it into live tracker.
- [ ] Social group create/join/check-in works for at least 2 test accounts.
- [ ] Guardian link opens read-only view and shows current safety status.
- [ ] Emergency actions (`Call 911`, ride, share status) trigger correctly.
- [ ] Logout always routes to login screen; unauthenticated writes are blocked.

## 7) Go/No-Go Rule
- [ ] No Sev-1/Sev-2 bugs open (auth failures, lost session data, broken drink logging, broken emergency actions).
- [ ] Last deploy passes `/readyz` and deploy smoke test.
- [ ] Team has rollback plan to previous known-good Render deploy.
