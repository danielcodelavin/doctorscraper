import asyncio
import unittest
from pathlib import Path

from playwright.async_api import async_playwright


OUT = Path("data/raw_html/jameda_bayern_probe.txt")
URL = "https://www.jameda.de/kinder-und-jugendarzt/bayern"


class JamedaProbeTest(unittest.TestCase):
    def test_jameda_listing_has_provider_style_content(self):
        async def run():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                text = await page.inner_text("body")
                OUT.write_text(text, encoding="utf-8")
                await browser.close()
                return text

        text = asyncio.run(run())
        self.assertIn("Kinder- und Jugendarzt Bayern", text)
        self.assertTrue("München" in text or "Erlangen" in text or "Fürth" in text)


if __name__ == "__main__":
    unittest.main()
