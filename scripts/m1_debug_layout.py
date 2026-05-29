"""Debug: trace parent height chain to find why .maplibregl-canvas is 78px."""

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
        page = await ctx.new_page()

        await page.goto("http://localhost:3000/login")
        await page.evaluate("(s) => localStorage.setItem('swarm.session.v1', JSON.stringify(s))", session)
        await page.goto("http://localhost:3000/")
        await page.wait_for_timeout(5000)

        chain = await page.evaluate("""() => {
          const canvas = document.querySelector('.maplibregl-canvas');
          if (!canvas) return {error: 'no canvas'};
          const trace = [];
          let el = canvas;
          while (el) {
            const r = el.getBoundingClientRect();
            const cs = window.getComputedStyle(el);
            trace.push({
              tag: el.tagName, cls: el.className?.toString().substring(0, 60),
              w: Math.round(r.width), h: Math.round(r.height),
              cssH: cs.height, minH: cs.minHeight, display: cs.display,
              gridArea: cs.gridArea, flex: cs.flex,
            });
            el = el.parentElement;
            if (trace.length > 10) break;
          }
          return {
            viewportH: window.innerHeight,
            documentH: document.documentElement.clientHeight,
            chain: trace
          };
        }""")
        print(json.dumps(chain, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
