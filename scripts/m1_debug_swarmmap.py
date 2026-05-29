"""Debug: verify __SWARM_MAP__ exposure with __M1_CAPTURE__ init flag."""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request

from playwright.async_api import async_playwright


async def main() -> None:
    r = urllib.request.urlopen(
        urllib.request.Request(
            "http://localhost:8765/auth/login",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"operator_id": "op-operator01", "password": "swarm-dev"}).encode(),
        ), timeout=5)
    payload = json.loads(r.read())
    session = {
        "accessToken": payload["access_token"], "refreshToken": payload["refresh_token"],
        "expiresAt": int((time.time() + payload["expires_in"]) * 1000),
        "role": payload["role"], "operatorId": payload["operator_id"],
        "siteId": payload["site_id"], "mfa": payload["mfa"],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        await ctx.add_init_script("window.__M1_CAPTURE__ = true; console.log('[init] __M1_CAPTURE__ set');")
        page = await ctx.new_page()
        page.on("console", lambda msg: print(f"[browser-{msg.type}] {msg.text[:200]}"))
        page.on("pageerror", lambda err: print(f"[browser-error] {err}"))

        await page.goto("http://localhost:3000/login")
        await page.evaluate(
            "(s) => localStorage.setItem('swarm.session.v1', JSON.stringify(s))", session
        )
        await page.goto("http://localhost:3000/")
        await page.wait_for_timeout(8000)

        state = await page.evaluate("""() => ({
          url: location.href,
          flagSet: window.__M1_CAPTURE__,
          swarmMap: !!window.__SWARM_MAP__,
          swarmMapKeys: window.__SWARM_MAP__ ? Object.keys(window.__SWARM_MAP__).slice(0, 5) : [],
          canvasH: document.querySelector('.maplibregl-canvas')?.clientHeight,
          mapClass: document.querySelector('.maplibregl-map')?.className,
        })""")
        print(f"state: {state}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
