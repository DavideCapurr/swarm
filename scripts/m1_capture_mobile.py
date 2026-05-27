"""Phase 7.G (M1) — capture the 2 mobile beats.

Standalone script (the desktop capture is in m1_capture_screenshots.py).
Assumes backend + sim are still running from the desktop run, so at
least one anomaly is present in /anomalies.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

BACKEND = "http://localhost:8765"
FRONTEND = "http://localhost:3000"
ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = ROOT / "docs" / "yc" / "screenshots"


def login_payload() -> dict:
    req = urllib.request.Request(
        f"{BACKEND}/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"operator_id": "op-operator01", "password": "swarm-dev"}).encode(),
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def api_get(path: str, token: str) -> dict:
    req = urllib.request.Request(f"{BACKEND}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


async def run() -> int:
    payload = login_payload()
    session = {
        "accessToken": payload["access_token"],
        "refreshToken": payload["refresh_token"],
        "expiresAt": int((time.time() + payload["expires_in"]) * 1000),
        "role": payload["role"],
        "operatorId": payload["operator_id"],
        "siteId": payload["site_id"],
        "mfa": payload["mfa"],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 390, "height": 844})
        page = await ctx.new_page()
        # Authenticate first by visiting /login then writing localStorage.
        await page.goto(f"{FRONTEND}/login")
        await page.evaluate(
            "(s) => { localStorage.setItem('swarm.session.v1', JSON.stringify(s)); }",
            session,
        )

        # Mobile list at /m.
        await page.goto(f"{FRONTEND}/m")
        await page.wait_for_load_state("networkidle", timeout=10_000)
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-01-list.png"), full_page=False)
        print("[capture] mobile-01-list saved")

        # Mobile detail — pick first anomaly id from backend.
        anoms = api_get("/anomalies", payload["access_token"]).get("anomalies", [])
        if not anoms:
            print("[capture] WARN no anomaly available for mobile-02; aborting", file=sys.stderr)
            await browser.close()
            return 1
        aid = anoms[0]["id"]
        await page.goto(f"{FRONTEND}/m/{aid}")
        await page.wait_for_load_state("networkidle", timeout=10_000)
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "mobile-02-detail.png"), full_page=False)
        print(f"[capture] mobile-02-detail saved (anomaly {aid[:12]})")

        await browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
