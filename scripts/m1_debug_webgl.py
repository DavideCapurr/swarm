"""Debug: read pixels from the maplibre WebGL canvas to confirm GPU rendering."""

from __future__ import annotations

import asyncio
import base64
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
        browser = await p.chromium.launch(
            headless=True,
            args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"],
        )
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        await ctx.add_init_script("window.__M1_CAPTURE__ = true;")
        page = await ctx.new_page()
        page.on("pageerror", lambda e: print(f"[err] {e}"))

        await page.goto("http://localhost:3000/login")
        await page.evaluate("(s) => localStorage.setItem('swarm.session.v1', JSON.stringify(s))", session)
        await page.goto("http://localhost:3000/")
        await page.wait_for_timeout(5000)
        await page.reload()
        await page.wait_for_timeout(5000)

        info = await page.evaluate("""() => {
          const cvs = document.querySelector('.maplibregl-canvas');
          if (!cvs) return {error: 'no canvas'};
          const gl = cvs.getContext('webgl2') || cvs.getContext('webgl');
          if (!gl) return {error: 'no GL context', tag: cvs.outerHTML.substring(0, 200)};
          const params = {
            renderer: gl.getParameter(gl.RENDERER),
            vendor: gl.getParameter(gl.VENDOR),
            version: gl.getParameter(gl.VERSION),
            w: cvs.width, h: cvs.height,
            cssW: cvs.clientWidth, cssH: cvs.clientHeight,
          };
          // Try to read pixels (gl.readPixels needs preserveDrawingBuffer)
          try {
            const buf = new Uint8Array(4);
            const x = Math.floor(cvs.width / 2), y = Math.floor(cvs.height / 2);
            gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, buf);
            params.midPixel = Array.from(buf);
          } catch (e) { params.readError = String(e); }
          // toDataURL fallback
          try {
            const url = cvs.toDataURL('image/png');
            params.dataUrlPrefix = url.substring(0, 50);
            params.dataUrlLen = url.length;
          } catch (e) { params.dataUrlError = String(e); }
          // Force a repaint via maplibre
          if (window.__SWARM_MAP__) {
            window.__SWARM_MAP__.triggerRepaint();
            params.triggered = true;
          }
          return params;
        }""")
        print(json.dumps(info, indent=2))

        # After triggerRepaint, wait a beat and re-read
        await page.wait_for_timeout(2000)
        post = await page.evaluate("""() => {
          const cvs = document.querySelector('.maplibregl-canvas');
          if (!cvs) return null;
          const gl = cvs.getContext('webgl2') || cvs.getContext('webgl');
          const buf = new Uint8Array(4);
          const x = Math.floor(cvs.width / 2), y = Math.floor(cvs.height / 2);
          gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, buf);
          // Save data URL
          const url = cvs.toDataURL('image/png');
          return {midPixel: Array.from(buf), dataUrlLen: url.length, dataUrl: url};
        }""")
        if post and post.get("dataUrl"):
            data = post["dataUrl"].split(",")[1]
            with open("/tmp/m1_canvas_dump.png", "wb") as f:
                f.write(base64.b64decode(data))
            print(f"canvas dumped: midPixel={post['midPixel']} dataUrlLen={post['dataUrlLen']}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
