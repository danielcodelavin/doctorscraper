"""Quick recon script to understand site structure."""
import asyncio
from playwright.async_api import async_playwright


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="de-DE")
        page = await context.new_page()

        # ---- gesund.bund.de ----
        print("=== gesund.bund.de ===")
        await page.goto("https://gesund.bund.de/suchen/aerztinnen-und-aerzte", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # Dismiss cookie banner via Cookiebot
        try:
            for sel in ["#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                        "button#CybotCookiebotDialogBodyButtonDecline",
                        "a#CybotCookiebotDialogBodyButtonAccept"]:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    await btn.first.click()
                    print(f"  Clicked cookie button: {sel}")
                    await asyncio.sleep(2)
                    break
        except Exception as e:
            print(f"  Cookie dismiss error: {e}")

        # Check what's on the page
        html = await page.content()
        with open("data/raw_html/recon_gesund.html", "w") as f:
            f.write(html)

        # Look for search form elements
        inputs = await page.locator("input, select").all()
        print(f"  Found {len(inputs)} form elements")
        for inp in inputs[:15]:
            tag = await inp.evaluate("el => el.tagName")
            name = await inp.get_attribute("name") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            id_ = await inp.get_attribute("id") or ""
            type_ = await inp.get_attribute("type") or ""
            print(f"    <{tag}> name={name} id={id_} type={type_} placeholder={placeholder}")

        # Take screenshot
        await page.screenshot(path="data/raw_html/recon_gesund.png", full_page=False)

        # Try the search URL with query params
        print("\n  Trying search with params...")
        await page.goto(
            "https://gesund.bund.de/suchen/aerztinnen-und-aerzte?fachgebiet=Kinder-+und+Jugendmedizin&standort=Bayern",
            wait_until="domcontentloaded", timeout=30000
        )
        await asyncio.sleep(5)

        # Dismiss cookies again
        try:
            for sel in ["#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                        "a#CybotCookiebotDialogBodyButtonAccept"]:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    await btn.first.click()
                    await asyncio.sleep(2)
                    break
        except Exception:
            pass

        await page.screenshot(path="data/raw_html/recon_gesund_search.png", full_page=False)

        # Look for result items
        body_text = await page.inner_text("body")
        # Print first 2000 chars of visible text
        print(f"  Body text (first 2000 chars):\n{body_text[:2000]}")

        # ---- KVB ----
        print("\n=== KVB Arztsuche ===")
        await page.goto("https://arztsuche.kvb.de/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # Cookie dismiss
        try:
            for sel in ["#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                        "button:has-text('Alle akzeptieren')",
                        "button:has-text('Zustimmen')",
                        "button:has-text('Akzeptieren')"]:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    await btn.first.click()
                    print(f"  Clicked cookie button: {sel}")
                    await asyncio.sleep(2)
                    break
        except Exception as e:
            print(f"  Cookie: {e}")

        await page.screenshot(path="data/raw_html/recon_kvb.png", full_page=False)

        inputs = await page.locator("input, select").all()
        print(f"  Found {len(inputs)} form elements")
        for inp in inputs[:15]:
            tag = await inp.evaluate("el => el.tagName")
            name = await inp.get_attribute("name") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            id_ = await inp.get_attribute("id") or ""
            type_ = await inp.get_attribute("type") or ""
            print(f"    <{tag}> name={name} id={id_} type={type_} placeholder={placeholder}")

        body_text = await page.inner_text("body")
        print(f"  Body text (first 2000 chars):\n{body_text[:2000]}")

        html = await page.content()
        with open("data/raw_html/recon_kvb.html", "w") as f:
            f.write(html)

        await browser.close()


asyncio.run(recon())
