"""Deeper recon: interact with gesund.bund.de search form and find real KVB arztsuche."""
import asyncio
from playwright.async_api import async_playwright


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="de-DE")
        page = await context.new_page()

        # ---- gesund.bund.de: explore the search form ----
        print("=== gesund.bund.de search form ===")
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

        # Scroll down to find the form
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(1)

        # Screenshot the form area
        await page.screenshot(path="data/raw_html/recon2_form.png", full_page=True)

        # Find all interactive elements in the form area
        # The TYPO3 form uses tx_sitepackage_doctorsearchlist
        form_els = await page.locator("[class*='search'], [class*='filter'], [class*='doctor'], [class*='arzt'], button, select, [role='combobox'], [role='listbox']").all()
        print(f"  Found {len(form_els)} form-like elements")
        for el in form_els[:30]:
            tag = await el.evaluate("el => el.tagName")
            cls = await el.get_attribute("class") or ""
            id_ = await el.get_attribute("id") or ""
            text = (await el.inner_text())[:80] if tag in ["BUTTON", "A", "LABEL", "SPAN", "DIV"] else ""
            print(f"    <{tag}> class={cls[:60]} id={id_} text={text}")

        # Look for the Fachrichtung dropdown specifically
        print("\n  Looking for Fachrichtung controls...")
        fach_els = await page.locator("text=Fachrichtung").all()
        for el in fach_els:
            parent = await el.evaluate("el => el.parentElement ? el.parentElement.outerHTML.substring(0, 300) : ''")
            print(f"    Fachrichtung context: {parent[:200]}")

        # Look for the Ort field
        print("\n  Looking for Ort/location controls...")
        ort_els = await page.locator("text=Ort").all()
        for el in ort_els[:3]:
            parent = await el.evaluate("el => el.parentElement ? el.parentElement.outerHTML.substring(0, 300) : ''")
            print(f"    Ort context: {parent[:200]}")

        # Try to find the actual search form
        print("\n  All form elements with names:")
        named = await page.locator("[name]").all()
        for el in named:
            name = await el.get_attribute("name") or ""
            if "sitepackage" in name.lower() or "doctor" in name.lower() or "arzt" in name.lower() or "search" in name.lower():
                tag = await el.evaluate("el => el.tagName")
                type_ = await el.get_attribute("type") or ""
                print(f"    <{tag}> name={name} type={type_}")

        # ---- KVB: find the actual Arztsuche ----
        print("\n=== KVB: Finding real Arztsuche ===")

        # Try dienste.kvb.de
        try:
            await page.goto("https://dienste.kvb.de/arztsuche/", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            print(f"  dienste.kvb.de/arztsuche -> {page.url}")
            await page.screenshot(path="data/raw_html/recon2_kvb_dienste.png", full_page=False)
            body = await page.inner_text("body")
            print(f"  Body (first 500): {body[:500]}")
        except Exception as e:
            print(f"  dienste.kvb.de error: {e}")

        # Try the "Praxis suchen" link from the 116117 page
        try:
            await page.goto("https://arztsuche.kvb.de/", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            # Click cookie
            try:
                btn = page.locator("button:has-text('Alle akzeptieren')")
                if await btn.count() > 0:
                    await btn.first.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Find "Praxis suchen" link
            praxis_link = page.locator("a:has-text('Praxis suchen')")
            if await praxis_link.count() > 0:
                href = await praxis_link.first.get_attribute("href")
                print(f"  'Praxis suchen' href: {href}")
                await praxis_link.first.click()
                await asyncio.sleep(3)
                print(f"  Navigated to: {page.url}")
                await page.screenshot(path="data/raw_html/recon2_kvb_praxis.png", full_page=False)
                body = await page.inner_text("body")
                print(f"  Body (first 1000): {body[:1000]}")

                # Find form elements
                inputs = await page.locator("input, select").all()
                print(f"  Found {len(inputs)} form elements")
                for inp in inputs[:20]:
                    tag = await inp.evaluate("el => el.tagName")
                    name = await inp.get_attribute("name") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    id_ = await inp.get_attribute("id") or ""
                    type_ = await inp.get_attribute("type") or ""
                    print(f"    <{tag}> name={name} id={id_} type={type_} placeholder={placeholder}")
        except Exception as e:
            print(f"  KVB praxis suchen error: {e}")

        await browser.close()


asyncio.run(recon())
