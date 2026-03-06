"""Deployment smoke test for BAC Tracker Web.

Usage:
    python scripts/smoke_deploy.py --base-url https://bac-tracker-web-k0qa.onrender.com
"""

from __future__ import annotations

import argparse
import json
import random
import string
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


def _json_request(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    data = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with opener.open(req, timeout=20) as resp:
            status = int(resp.status)
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read().decode("utf-8")
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {"raw": body}
    return status, parsed


def _random_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"smoke-{suffix}@example.com"


def run_smoke(base_url: str) -> int:
    base = base_url.rstrip("/")
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def check(condition: bool, message: str) -> None:
        if not condition:
            raise RuntimeError(message)

    print("1) Checking readiness...")
    status, body = _json_request(opener, "GET", f"{base}/readyz")
    check(status == 200 and body.get("ok") is True, f"/readyz failed: status={status}, body={body}")

    print("2) Fetching auth bootstrap token...")
    status, body = _json_request(opener, "GET", f"{base}/api/auth/me")
    check(status == 200, f"/api/auth/me failed: status={status}, body={body}")
    csrf = str(body.get("csrf_token", "")).strip()
    check(bool(csrf), "Missing csrf_token from /api/auth/me")

    print("3) Registering smoke user...")
    email = _random_email()
    password = "smoketest123"
    payload = {
        "display_name": "Smoke Test",
        "username": "",
        "email": email,
        "password": password,
        "confirm_password": password,
        "gender": "male",
        "default_weight_lb": 170,
    }
    status, body = _json_request(opener, "POST", f"{base}/api/auth/register", payload=payload, headers={"X-CSRF-Token": csrf})
    check(status == 200 and body.get("ok") is True, f"/api/auth/register failed: status={status}, body={body}")
    csrf = str(body.get("csrf_token", "")).strip() or csrf

    print("4) Setting profile defaults for active session...")
    status, body = _json_request(
        opener,
        "POST",
        f"{base}/api/setup",
        payload={"weight_lb": 170, "is_male": True},
        headers={"X-CSRF-Token": csrf},
    )
    check(status == 200 and body.get("ok") is True, f"/api/setup failed: status={status}, body={body}")

    print("5) Adding one drink...")
    status, body = _json_request(
        opener,
        "POST",
        f"{base}/api/drink",
        payload={"catalog_id": "vodka-cran", "count": 1, "hours_ago": 0, "sip_minutes": 0},
        headers={"X-CSRF-Token": csrf},
    )
    check(status == 200 and body.get("ok") is True, f"/api/drink failed: status={status}, body={body}")

    print("6) Validating resulting state...")
    status, body = _json_request(opener, "GET", f"{base}/api/state")
    check(status == 200, f"/api/state failed: status={status}, body={body}")
    check(body.get("authenticated") is True, f"Expected authenticated=true, got {body}")
    check(body.get("configured") is True, f"Expected configured=true, got {body}")
    check(int(body.get("drink_count", 0)) >= 1, f"Expected drink_count >= 1, got {body}")

    print("Smoke test passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deployment smoke checks against BAC Tracker Web.")
    parser.add_argument("--base-url", required=True, help="Base URL for deployed app, e.g. https://bac-tracker-web-k0qa.onrender.com")
    args = parser.parse_args()
    try:
        return run_smoke(args.base_url)
    except Exception as exc:
        print(f"Smoke test failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

