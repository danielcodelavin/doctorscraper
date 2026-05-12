import unittest
from pathlib import Path

from extractor import split_gesund_bund_blocks
from parser import parse_html_to_markdown


class GesundBundPartitioningTest(unittest.TestCase):
    def test_muenchen_results_split_into_provider_blocks(self):
        md_path = Path("data/parsed_markdown/gesund_bund_Muenchen.md")
        if not md_path.exists():
            html_path = Path("data/raw_html/gesund_bund_Muenchen.html")
            self.assertTrue(html_path.exists(), "Missing gesund_bund_Muenchen.html control file")
            md_path.write_text(
                parse_html_to_markdown(html_path.read_text(encoding="utf-8")),
                encoding="utf-8",
            )

        text = md_path.read_text(encoding="utf-8")
        blocks = split_gesund_bund_blocks(text)

        self.assertGreaterEqual(len(blocks), 8)
        self.assertIn("Henrik Halboni", blocks[0])
        self.assertIn("089 297448", blocks[0])
        self.assertNotIn("Lilian Ziegler", blocks[0])

        joined = "\n\n".join(blocks[:3])
        self.assertIn("David Wiesenäcker", joined)

        for block in blocks[:5]:
            self.assertIn("Telefon:", block)
            self.assertRegex(block, r"\d{5}\s+München")


if __name__ == "__main__":
    unittest.main()
