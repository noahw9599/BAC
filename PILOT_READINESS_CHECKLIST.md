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
