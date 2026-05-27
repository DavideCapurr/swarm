"""Phase 7.G (M1) — capture the 5 desktop + 2 mobile demo beats.

Drives a headless Chromium against localhost:3000 (frontend already
running). Authenticates by writing the JWT into localStorage, then
boots the wildfire sim as a subprocess so beat timing is deterministic.

Polls /anomalies + /operator-commands?operator_id=op-autonomy0001 for
state transitions and takes a screenshot at each beat.

Output: docs/yc/screenshots/{wildfire-0[1-5].png, mobile-0[1-2].png}
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

BACKEND = "http://localhost:8765"
FRONTEND = "http://localhost:3000"
ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = ROOT / "docs" / "yc" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def login_token() -> str:
    req = urllib.request.Request(
        f"{BACKEND}/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"operator_id": "op-operator01", "password": "swarm-dev"}).encode(),
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())["access_token"]


def api_get(path: str, token: str) -> dict:
    req = urllib.request.Request(f"{BACKEND}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


async def wait_until(predicate, deadline_s: float, label: str) -> bool:
    end = time.monotonic() + deadline_s
    while time.monotonic() < end:
        try:
            if predicate():
                print(f"[capture] {label} reached")
                return True
        except Exception as e:  # noqa: BLE001
            print(f"[capture] {label} probe error: {e}")
        await asyncio.sleep(0.5)
    print(f"[capture] WARN {label} deadline {deadline_s}s exhausted")
    return False


async def attach_login(page) -> None:
    token = login_token()
    payload = json.loads(urllib.request.urlopen(  # noqa: S310
        urllib.request.Request(
            f"{BACKEND}/auth/login",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"operator_id": "op-operator01", "password": "swarm-dev"}).encode(),
        ), timeout=5).read())
    await page.goto(f"{FRONTEND}/login")
    session = {
        "accessToken": payload["access_token"],
        "refreshToken": payload["refresh_token"],
        "expiresAt": int((time.time() + payload["expires_in"]) * 1000),
        "role": payload["role"],
        "operatorId": payload["operator_id"],
        "siteId": payload["site_id"],
        "mfa": payload["mfa"],
    }
    await page.evaluate(
        "(s) => { localStorage.setItem('swarm.session.v1', JSON.stringify(s)); }",
        session,
    )
    await page.goto(f"{FRONTEND}/")
    await page.wait_for_load_state("networkidle", timeout=10_000)
    return token


async def run() -> int:
    # Pre-flight: backend must be reachable.
    try:
        token = login_token()
    except Exception as e:  # noqa: BLE001
        print(f"[capture] FATAL backend login failed: {e}", file=sys.stderr)
        return 2

    sim_proc: subprocess.Popen | None = None
    rc = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        await attach_login(page)

        # ── Screenshot 01 — standby (no sim yet) ──
        print("[capture] desktop 01 standby (pre-sim) — waiting for Console render…")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "wildfire-01-standby.png"), full_page=False)

        # Boot sim now — T0 begins.
        env = {**os.environ, "SIM_SCENARIO": "sim/scenarios/wildfire_owner_land.yaml", "SWARM_AUTONOMY_BASELINE": "true"}
        # Source .env vars (POSTGRES, REDIS, JWT, etc.).
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env.setdefault(k, v)
        print("[capture] booting sim…")
        sim_proc = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-m", "sim.swarm_sim.runner"],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        t0 = time.monotonic()

        # Wait for 3 units to appear so the first standby with units is reliable.
        await wait_until(
            lambda: len(api_get("/units", token).get("units", [])) >= 3,
            deadline_s=10,
            label="3 units online",
        )
        # Re-screenshot 01 now that drones are visible (overwrite the empty one).
        await page.screenshot(path=str(SCREENSHOT_DIR / "wildfire-01-standby.png"), full_page=False)
        print(f"[capture] 01 saved at t+{time.monotonic()-t0:.1f}s")

        # ── Screenshot 02 — SMOKE callout (t+10s) ──
        await wait_until(
            lambda: any(a["kind"] == "SMOKE" for a in api_get("/anomalies", token).get("anomalies", [])),
            deadline_s=15,
            label="SMOKE anomaly present",
        )
        # Wait a beat for the WS frame to render the callout.
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "wildfire-02-smoke.png"), full_page=False)
        print(f"[capture] 02 saved at t+{time.monotonic()-t0:.1f}s")

        # ── Screenshot 03 — R1 AUTO chip (t+12s) ──
        await wait_until(
            lambda: any(c.get("source") == "autonomy" and c.get("rule") == "R1"
                        for c in api_get("/commands", token).get("commands", [])),
            deadline_s=12,
            label="R1 autonomy command present",
        )
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "wildfire-03-r1-verify.png"), full_page=False)
        print(f"[capture] 03 saved at t+{time.monotonic()-t0:.1f}s")

        # ── Screenshot 04 — FIRE callout (t+35s) ──
        await wait_until(
            lambda: any(a["kind"] == "FIRE" for a in api_get("/anomalies", token).get("anomalies", [])),
            deadline_s=40,
            label="FIRE anomaly present",
        )
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "wildfire-04-fire.png"), full_page=False)
        print(f"[capture] 04 saved at t+{time.monotonic()-t0:.1f}s")

        # ── Screenshot 05 — R2 escalate (t+45s) ──
        await wait_until(
            lambda: any(c.get("source") == "autonomy" and c.get("rule") == "R2"
                        for c in api_get("/commands", token).get("commands", [])),
            deadline_s=20,
            label="R2 autonomy command present",
        )
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "wildfire-05-r2-escalate.png"), full_page=False)
        print(f"[capture] 05 saved at t+{time.monotonic()-t0:.1f}s")

        # ── Mobile 390x844 ──
        await ctx.set_viewport_size({"width": 390, "height": 844})
        await page.goto(f"{FRONTEND}/m")
        await page.wait_for_load_state("networkidle", timeout=5_000)
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-01-list.png"), full_page=False)
        print(f"[capture] mobile 01 saved")

        # Mobile detail — click first anomaly link.
        first_anom = api_get("/anomalies", token).get("anomalies", [])
        if first_anom:
            aid = first_anom[0]["id"]
            await page.goto(f"{FRONTEND}/m/{aid}")
            await page.wait_for_load_state("networkidle", timeout=5_000)
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-02-detail.png"), full_page=False)
            print(f"[capture] mobile 02 saved")
        else:
            print("[capture] WARN no anomaly to navigate for mobile-02")
            rc = 1

        await browser.close()

    if sim_proc is not None:
        sim_proc.send_signal(signal.SIGTERM)
        try:
            sim_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            sim_proc.kill()

    print("[capture] done")
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
