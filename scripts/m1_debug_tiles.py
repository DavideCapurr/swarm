"""Phase 7.G debug — capture maplibre tile requests + canvas state."""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request

from playwright.async_api import async_playwright

BACKEND = "http://localhost:8765"
FRONTEND = "http://localhost:3000"


async def main() -> None:
    r = urllib.request.urlopen(
        urllib.request.Request(
            f"{BACKEND}/auth/login",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"operator_id": "op-operator01", "password": "swarm-dev"}).encode(),
        ), timeout=5)
    payload = json.loads(r.read())

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        tile_reqs: list[tuple[str, str]] = []
        tile_resps: list[tuple[str, int]] = []
        page.on("request", lambda req: (
            tile_reqs.append((req.method, req.url)) if "cartocdn" in req.url else None
        ))
        page.on("response", lambda resp: (
            tile_resps.append((resp.url, resp.status)) if "cartocdn" in resp.url else None
        ))
        page.on("requestfailed", lambda req: print(
            f"FAIL {req.method} {req.url} -> {req.failure}"
        ) if "cartocdn" in req.url else None)

        await page.goto(f"{FRONTEND}/login")
        session = {
            "accessToken": payload["access_token"], "refreshToken": payload["refresh_token"],
            "expiresAt": int((time.time() + payload["expires_in"]) * 1000),
            "role": payload["role"], "operatorId": payload["operator_id"],
            "siteId": payload["site_id"], "mfa": payload["mfa"],
        }
        await page.evaluate("(s) => localStorage.setItem('swarm.session.v1', JSON.stringify(s))", session)
        await page.goto(f"{FRONTEND}/")
        # Wait a long time
        await page.wait_for_timeout(15_000)
        # Sample canvas pixels via JS
        sample = await page.evaluate("""() => {
          const cvs = document.querySelector('.maplibregl-canvas');
          if (!cvs) return {error: 'no canvas'};
          const ctx = document.createElement('canvas').getContext('2d');
          // Read via 2d context - need to use WebGL readPixels for actual canvas
          return {w: cvs.width, h: cvs.height, cssW: cvs.clientWidth, cssH: cvs.clientHeight,
                  containerW: cvs.parentElement?.clientWidth, containerH: cvs.parentElement?.clientHeight};
        }""")
        print(f"canvas: {sample}")
        print(f"tile requests: {len(tile_reqs)}")
        for t in tile_reqs[:5]:
            print(f"  REQ {t[0]} {t[1]}")
        print(f"tile responses: {len(tile_resps)}")
        for t in tile_resps[:5]:
            print(f"  RESP {t[1]} {t[0]}")

        await page.screenshot(path="/tmp/m1_debug_tiles.png", full_page=False)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
