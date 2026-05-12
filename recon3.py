"""Targeted recon: find exact option values for both search forms."""
import asyncio
from playwright.async_api import async_playwright


async def recon():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="de-DE")
        page = await context.new_page()

        # ---- gesund.bund.de: explore the Arztsuche form deeply ----
        print("=== gesund.bund.de: Deep form exploration ===")
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

        # Scroll to form
        await page.evaluate("window.scrollTo(0, 600)")
        await asyncio.sleep(1)

        # Screenshot the search form area
        await page.screenshot(path="data/raw_html/recon3_form_visible.png", full_page=True)

        # Get all the HTML around the arztsuche form
        form_html = await page.evaluate("""
            () => {
                // Find the arztsuche form section
                const forms = document.querySelectorAll('form');
                let result = [];
                forms.forEach(f => {
                    if (f.innerHTML.includes('arztsuche') || f.innerHTML.includes('Fachrichtung') || f.innerHTML.includes('Ort')) {
                        result.push(f.outerHTML.substring(0, 3000));
                    }
                });
                // Also check for web components
                const comboboxes = document.querySelectorAll('a-combobox, [is="a-combobox"]');
                comboboxes.forEach(c => result.push(c.outerHTML.substring(0, 1000)));
                return result;
            }
        """)
        print("  Form HTML snippets:")
        for i, html in enumerate(form_html):
            print(f"  --- Form {i} ---")
            print(f"  {html[:500]}")

        # Click on the Fachrichtung input and check what options appear
        fach_input = page.locator("#arztsuche-fachrichtung")
        if await fach_input.count() > 0:
            print("\n  Found #arztsuche-fachrichtung, clicking...")
            await fach_input.click()
            await asyncio.sleep(1)
            await fach_input.fill("Kinder")
            await asyncio.sleep(2)

            # Screenshot after typing
            await page.screenshot(path="data/raw_html/recon3_fach_dropdown.png")

            # Get dropdown options
            options = await page.evaluate("""
                () => {
                    const opts = document.querySelectorAll('[role="option"], .select__option, .combobox__option, li[class*="option"]');
                    return Array.from(opts).map(o => ({text: o.textContent.trim(), value: o.getAttribute('value') || o.getAttribute('data-value') || ''}));
                }
            """)
            print(f"  Dropdown options after typing 'Kinder': {options}")

            # Also check listbox
            listbox = await page.locator("[role='listbox']").all()
            print(f"  Found {len(listbox)} listbox elements")
            for lb in listbox:
                inner = await lb.inner_text()
                print(f"    Listbox content: {inner[:300]}")

        # Check what's the Ort/location input
        print("\n  Looking for Ort input...")
        ort_candidates = await page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input, a-combobox');
                return Array.from(inputs).map(i => ({
                    tag: i.tagName,
                    id: i.id || '',
                    name: i.name || '',
                    placeholder: i.placeholder || '',
                    ariaLabel: i.getAttribute('aria-label') || '',
                    type: i.type || '',
                    className: (i.className || '').substring(0, 80)
                })).filter(i => !i.id.startsWith('Cybot'));
            }
        """)
        for o in ort_candidates:
            if any(kw in str(o).lower() for kw in ['ort', 'stand', 'adress', 'plz', 'arztsuche']):
                print(f"    {o}")

        # ---- 116117: find exact search term format ----
        print("\n=== 116117: Deep form exploration ===")
        await page.goto("https://arztsuche.116117.de/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        # Dismiss cookies
        try:
            btn = page.locator("button:has-text('Alle akzeptieren')")
            if await btn.count() > 0:
                await btn.first.click()
                await asyncio.sleep(2)
        except Exception:
            pass

        # Find the "Wen oder Was" input
        wen_input = await page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input');
                return Array.from(inputs).map(i => ({
                    id: i.id || '',
                    name: i.name || '',
                    placeholder: i.placeholder || '',
                    ariaLabel: i.getAttribute('aria-label') || '',
                    type: i.type || '',
                }));
            }
        """)
        print("  All inputs on 116117:")
        for w in wen_input:
            print(f"    {w}")

        # Type "Kinder" in the Wen oder Was field and check suggestions
        wen = page.locator("input").first
        # Try each input to find the right one
        all_inputs = await page.locator("input:not([type='checkbox']):not([type='hidden'])").all()
        for inp in all_inputs:
            id_ = await inp.get_attribute("id") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            print(f"\n  Trying input id={id_} placeholder={placeholder}")
            if "Wen" in id_ or "Search" in id_ or not id_.startswith("ccm"):
                await inp.click()
                await inp.fill("Kinder")
                await asyncio.sleep(2)

                await page.screenshot(path=f"data/raw_html/recon3_116117_{id_}.png")

                # Check for suggestions
                suggestions = await page.evaluate("""
                    () => {
                        const opts = document.querySelectorAll('[role="option"], .suggestion, li[class*="suggest"], [class*="autocomplete"] li, [class*="dropdown"] li');
                        return Array.from(opts).map(o => o.textContent.trim()).slice(0, 20);
                    }
                """)
                print(f"    Suggestions: {suggestions}")

                # Also get the listbox
                listbox_items = await page.locator("[role='option'], [role='listbox'] li").all()
                print(f"    Listbox items count: {len(listbox_items)}")
                for item in listbox_items[:10]:
                    text = await item.inner_text()
                    print(f"      Item: {text}")

                await inp.fill("")
                await asyncio.sleep(0.5)
                break

        await browser.close()


asyncio.run(recon())
