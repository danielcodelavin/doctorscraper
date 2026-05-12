"""Quick test with 2 cities to validate scraper approach."""
import asyncio
import json
import random
from pathlib import Path
from playwright.async_api import async_playwright

RAW_HTML_DIR = Path("./data/raw_html")

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="de-DE", viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # ---- Test gesund.bund.de ----
        print("=== Testing gesund.bund.de with München ===")
        await page.goto("https://gesund.bund.de/suchen/aerztinnen-und-aerzte",
                       wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # Dismiss cookie
        try:
            btn = page.locator("#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
            if await btn.count() > 0:
                await btn.first.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Fill Fachrichtung
        fach = page.locator("#arztsuche-fachrichtung")
        await fach.click()
        await asyncio.sleep(0.3)
        await fach.fill("Kinder")
        await asyncio.sleep(2)

        opt = page.locator("[role='option']:has-text('Kinderarzt / Kinderärztin')")
        if await opt.count() > 0:
            await opt.first.click()
            print("  Selected Fachrichtung OK")
        else:
            # Check what options exist
            all_opts = await page.locator("[role='option']").all()
            print(f"  Available options: {len(all_opts)}")
            for o in all_opts[:5]:
                print(f"    {await o.inner_text()}")
        await asyncio.sleep(0.5)

        # Fill Ort
        ort = page.locator("#arztsuche__field_where")
        await ort.click()
        await ort.fill("München")
        await asyncio.sleep(2)

        # Try Google Places autocomplete
        pac = page.locator(".pac-item")
        if await pac.count() > 0:
            await pac.first.click()
            print("  Selected location via Places OK")
        else:
            print("  No Places suggestions, pressing Enter")
            await ort.press("ArrowDown")
            await asyncio.sleep(0.3)
            await ort.press("Enter")
        await asyncio.sleep(1)

        # Submit
        submit = page.locator("button:has-text('Jetzt suchen')")
        if await submit.count() > 0:
            await submit.first.click()
            print("  Clicked submit")
        await asyncio.sleep(6)

        await page.screenshot(path="data/raw_html/test_gesund_result.png", full_page=True)
        html = await page.content()
        RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_HTML_DIR / "test_gesund_muenchen.html").write_text(html, encoding="utf-8")

        body = await page.inner_text("body")
        # Check for result indicators
        if "Ergebnis" in body or "Treffer" in body:
            print(f"  RESULTS FOUND!")
            # Print first 500 chars of results area
            idx = body.find("Ergebnis")
            if idx > 0:
                print(f"  Context: ...{body[max(0,idx-100):idx+400]}...")
        elif "keine Ergebnisse" in body:
            print("  No results found")
        else:
            print(f"  Unknown state. First 500 chars: {body[:500]}")

        # ---- Test 116117 ----
        print("\n=== Testing 116117 with München ===")
        await page.goto("https://arztsuche.116117.de/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        try:
            btn = page.locator("button:has-text('Alle akzeptieren')")
            if await btn.count() > 0:
                await btn.first.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Fill Wen oder Was
        wen = page.locator("#WenoderWasSearchInput")
        await wen.click()
        await wen.fill("Kinder")
        await asyncio.sleep(2)

        opt = page.locator("[role='option']:has-text('Kinderarzt / Kinderärztin')")
        if await opt.count() > 0:
            await opt.first.click()
            print("  Selected specialty OK")
        else:
            all_opts = await page.locator("[role='option']").all()
            print(f"  Available options: {len(all_opts)}")
            for o in all_opts[:5]:
                print(f"    {await o.inner_text()}")
        await asyncio.sleep(0.5)

        # Fill Ort
        ort = page.locator("#Ort-PflichtfeldSearchInput")
        await ort.click()
        await ort.fill("München")
        await asyncio.sleep(2)

        # Select location suggestion
        loc_opt = page.locator("[role='option']")
        if await loc_opt.count() > 0:
            # Find the München option specifically
            muc_opt = page.locator("[role='option']:has-text('München')")
            if await muc_opt.count() > 0:
                await muc_opt.first.click()
                print("  Selected location OK")
            else:
                await loc_opt.first.click()
                print("  Selected first location option")
        else:
            await ort.press("Enter")
            print("  Pressed Enter for location")
        await asyncio.sleep(1)

        # Search
        search = page.locator("button:has-text('Suchen')")
        if await search.count() > 0:
            await search.first.click()
            print("  Clicked search")
        await asyncio.sleep(6)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        await page.screenshot(path="data/raw_html/test_116117_result.png", full_page=True)
        html = await page.content()
        (RAW_HTML_DIR / "test_116117_muenchen.html").write_text(html, encoding="utf-8")

        body = await page.inner_text("body")
        print(f"  Result page URL: {page.url}")
        # Check for results
        import re
        count_match = re.search(r'(\d+)\s*(?:Ergebnis|Treffer|Prax)', body)
        if count_match:
            print(f"  Found {count_match.group(0)}")
        print(f"  Body preview: {body[:800]}")

        await browser.close()

asyncio.run(test())
