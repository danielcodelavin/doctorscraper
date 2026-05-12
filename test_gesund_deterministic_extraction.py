import unittest
from pathlib import Path

from extractor import extract_from_gesund_bund_markdown


class GesundBundDeterministicExtractionTest(unittest.TestCase):
    def test_muenchen_records_are_split_and_parsed_correctly(self):
        md_path = Path("data/parsed_markdown/gesund_bund_Muenchen.md")
        self.assertTrue(md_path.exists(), "Missing gesund_bund_Muenchen.md control file")

        records = extract_from_gesund_bund_markdown(md_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(records), 8)

        first = records[0]
        self.assertEqual(first["first_name"], "Henrik")
        self.assertEqual(first["last_name"], "Halboni")
        self.assertEqual(first["postal_code"], "80538")
        self.assertEqual(first["city"], "München")
        self.assertEqual(first["phone"], "089 297448")
        self.assertIsNone(first["email"])

        second = records[1]
        self.assertEqual(second["first_name"], "Lilian")
        self.assertEqual(second["last_name"], "Ziegler")
        self.assertEqual(second["phone"], "089 299684")


if __name__ == "__main__":
    unittest.main()
