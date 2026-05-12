import asyncio
import re
import unittest
from pathlib import Path

from playwright.async_api import async_playwright


OUT = Path("data/raw_html/doctolib_muenchen_probe.txt")
URL = "https://www.doctolib.de/kinderheilkunde-kinder-und-jugendmedizin/muenchen/mathias-wendeborn"


class DoctolibProbeTest(unittest.TestCase):
    def test_doctolib_profile_has_provider_fields(self):
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
        self.assertIn("Mathias Wendeborn", text)
        self.assertIn("München", text)
        self.assertRegex(text, r"089[\s0-9]+")


if __name__ == "__main__":
    unittest.main()
