"""Recon: expand all details on a search page and extract emails."""
import asyncio
import re
from playwright.async_api import async_playwright


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="de-DE", viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

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

        # Search München
        fach = page.locator("#arztsuche-fachrichtung")
        await fach.click()
        await fach.fill("Kinder")
        await asyncio.sleep(2)
        await page.locator("[role='option']:has-text('Kinderarzt / Kinderärztin')").first.click()
        await asyncio.sleep(0.5)

        ort = page.locator("#arztsuche__field_where")
        await ort.click()
        await ort.fill("München")
        await asyncio.sleep(2)
        pac = page.locator(".pac-item").first
        if await pac.count() > 0:
            await pac.click()
        await asyncio.sleep(1)

        await page.locator("button:has-text('Jetzt suchen')").first.click()
        await asyncio.sleep(5)

        # Click ALL "Details anzeigen" buttons
        detail_buttons = await page.locator("text=Details anzeigen").all()
        print(f"Found {len(detail_buttons)} detail buttons")
        for i, btn in enumerate(detail_buttons):
            try:
                await btn.scroll_into_view_if_needed()
                await btn.click()
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"  Couldn't click detail {i}: {e}")

        await asyncio.sleep(2)

        # Now get the full page HTML and extract mailto links
        html = await page.content()

        # Find all mailto links
        emails = re.findall(r'href="mailto:([^"]+)"', html)
        print(f"\nFound {len(emails)} mailto links:")
        for e in emails:
            print(f"  {e}")

        # Get the full text with details expanded
        text = await page.inner_text("body")

        # Find email-related text patterns
        email_pattern = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        print(f"\nEmail patterns in text: {email_pattern}")

        # Save expanded HTML
        with open("data/raw_html/recon_expanded_muenchen.html", "w") as f:
            f.write(html)

        # Now let's see the structure - get the HTML around each doctor entry
        # to understand how emails relate to doctor blocks
        entries = await page.locator("[class*='result'], [class*='arzt'], [class*='doctor']").all()
        print(f"\nResult entries: {len(entries)}")

        # Alternative: examine the detail sections
        # Look for the expanded detail blocks
        detail_sections = await page.evaluate("""
            () => {
                const results = [];
                // Find all doctor entries with their details
                const items = document.querySelectorAll('[class*="result-item"], [class*="arztsuche__result"]');
                items.forEach(item => {
                    const name = item.querySelector('h2, h3, [class*="name"]');
                    const emails = item.querySelectorAll('a[href^="mailto:"]');
                    const text = item.innerText.substring(0, 500);
                    results.push({
                        name: name ? name.innerText : 'unknown',
                        emails: Array.from(emails).map(e => e.href.replace('mailto:', '')),
                        textPreview: text
                    });
                });
                return results;
            }
        """)
        print(f"\nStructured entries: {len(detail_sections)}")
        for entry in detail_sections[:5]:
            print(f"  {entry}")

        # If no structured entries, try to find the DOM structure
        if not detail_sections:
            structure = await page.evaluate("""
                () => {
                    const body = document.body;
                    // Find containers that have both doctor names and mailto links
                    const allMailto = document.querySelectorAll('a[href^="mailto:"]');
                    const results = [];
                    allMailto.forEach(m => {
                        let parent = m.parentElement;
                        // Walk up to find the containing result block
                        for (let i = 0; i < 10; i++) {
                            if (!parent) break;
                            const h = parent.querySelector('h2, h3');
                            if (h) {
                                results.push({
                                    email: m.href.replace('mailto:', ''),
                                    doctorName: h.innerText,
                                    containerClass: parent.className.substring(0, 80),
                                    containerTag: parent.tagName
                                });
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    });
                    return results;
                }
            """)
            print(f"\nEmail->Doctor mapping: {len(structure)}")
            for s in structure[:10]:
                print(f"  {s['email']} -> {s['doctorName']} (container: {s['containerTag']}.{s['containerClass'][:40]})")

        await browser.close()


asyncio.run(recon())
