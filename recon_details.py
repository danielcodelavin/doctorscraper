"""Recon: check what's on a gesund.bund.de doctor detail page."""
import asyncio
from playwright.async_api import async_playwright


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="de-DE", viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        # Go to search, find München results, click first "Details anzeigen"
        await page.goto("https://gesund.bund.de/suchen/aerztinnen-und-aerzte", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        # Dismiss cookie
        try:
            btn = page.locator("#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
            if await btn.count() > 0:
                await btn.first.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Fill search
        fach = page.locator("#arztsuche-fachrichtung")
        await fach.click()
        await fach.fill("Kinder")
        await asyncio.sleep(2)
        opt = page.locator("[role='option']:has-text('Kinderarzt / Kinderärztin')").first
        await opt.click()
        await asyncio.sleep(0.5)

        ort = page.locator("#arztsuche__field_where")
        await ort.click()
        await ort.fill("München")
        await asyncio.sleep(2)
        pac = page.locator(".pac-item").first
        if await pac.count() > 0:
            await pac.click()
        await asyncio.sleep(1)

        submit = page.locator("button:has-text('Jetzt suchen')").first
        await submit.click()
        await asyncio.sleep(5)

        # Click first "Details anzeigen"
        details_btn = page.locator("text=Details anzeigen").first
        if await details_btn.count() > 0:
            await details_btn.click()
            await asyncio.sleep(3)

            await page.screenshot(path="data/raw_html/recon_detail_expanded.png", full_page=True)
            text = await page.inner_text("body")
            # Find the detail section
            idx = text.find("Details anzeigen")
            if idx > 0:
                snippet = text[max(0, idx-200):idx+2000]
            else:
                snippet = text[:3000]
            print("=== Detail section text ===")
            print(snippet)
        else:
            print("No 'Details anzeigen' found")

        # Also check if there's a separate detail page URL pattern
        links = await page.locator("a[href]").all()
        detail_hrefs = []
        for link in links:
            href = await link.get_attribute("href") or ""
            text = await link.inner_text()
            if "detail" in href.lower() or "profil" in href.lower() or "arzt" in href.lower():
                detail_hrefs.append(f"{text.strip()[:50]} -> {href[:100]}")
        if detail_hrefs:
            print("\n=== Detail links found ===")
            for h in detail_hrefs[:10]:
                print(f"  {h}")

        await browser.close()


asyncio.run(recon())
