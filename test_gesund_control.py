import os
import subprocess
import sys
import unittest
from pathlib import Path

from parser import parse_html_to_markdown


ROOT = Path(__file__).resolve().parent
RAW_HTML = ROOT / "data" / "raw_html" / "gesund_bund_Muenchen.html"
PARSED_MD = ROOT / "data" / "parsed_markdown" / "gesund_bund_Muenchen.md"


class GesundBundControlTest(unittest.TestCase):
    def test_muenchen_scrape_produces_sensible_text(self):
        if RAW_HTML.exists():
            RAW_HTML.unlink()

        env = os.environ.copy()
        env["SCRAPER_CITIES"] = "München"

        subprocess.run(
            [sys.executable, "scraper.py"],
            cwd=ROOT,
            env=env,
            check=True,
            timeout=180,
        )

        self.assertTrue(RAW_HTML.exists(), "gesund_bund_Muenchen.html was not created")

        html_text = RAW_HTML.read_text(encoding="utf-8")
        markdown = parse_html_to_markdown(html_text)
        PARSED_MD.write_text(markdown, encoding="utf-8")

        self.assertNotIn("Cookiebot", html_text)
        self.assertNotIn("Cookiebot", markdown)
        self.assertIn("Suchergebnisse: 120", markdown)
        self.assertIn("Henrik Halboni", markdown)
        self.assertIn("Liebherrstraße 20", markdown)
        self.assertIn("80538 München", markdown)
        self.assertIn("089 297448", markdown)
        self.assertIn("Weitere Ergebnisse anzeigen", markdown)


if __name__ == "__main__":
    unittest.main()
