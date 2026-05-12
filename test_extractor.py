"""Test the regex extractor on real scraped pages."""
import json
from pathlib import Path
from extractor import extract_from_gesund_bund, split_gesund_bund_blocks

PARSED_MD_DIR = Path("./data/parsed_markdown")


def test_extraction():
    md_files = sorted(PARSED_MD_DIR.glob("gesund_bund_*.md"))
    if not md_files:
        print("ERROR: No gesund_bund markdown files found. Run scraper+parser first.")
        return False

    total_records = 0
    files_tested = 0
    empty_files = 0
    errors = []

    # Test a sample of files (every 50th + first 10)
    sample = md_files[:10] + md_files[10::50]
    sample = list(dict.fromkeys(sample))  # dedupe

    for md_file in sample:
        content = md_file.read_text(encoding="utf-8")
        if len(content) < 30:
            empty_files += 1
            continue

        records = extract_from_gesund_bund(content)
        files_tested += 1
        total_records += len(records)

        # Validate records
        for r in records:
            if not r.get("last_name"):
                errors.append(f"{md_file.name}: record missing last_name: {r}")
            if not r.get("postal_code"):
                errors.append(f"{md_file.name}: record missing postal_code: {r}")
            if r.get("postal_code") and not r["postal_code"].isdigit():
                errors.append(f"{md_file.name}: invalid postal_code: {r['postal_code']}")

        if len(records) == 0:
            # Check if the page actually has provider data
            blocks = split_gesund_bund_blocks(content)
            if blocks:
                errors.append(f"{md_file.name}: {len(blocks)} blocks found but 0 records parsed")

    print(f"Files tested: {files_tested}")
    print(f"Empty files: {empty_files}")
    print(f"Total records: {total_records}")
    print(f"Avg records/file: {total_records / max(files_tested, 1):.1f}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:20]:
            print(f"  {e}")
        return False
    else:
        print("\nAll tests PASSED.")
        return True


def test_known_good():
    """Test München which we know has 10 results."""
    muc = PARSED_MD_DIR / "gesund_bund_Muenchen.md"
    if not muc.exists():
        print("SKIP: München file not found")
        return True

    content = muc.read_text()
    records = extract_from_gesund_bund(content)

    print(f"\nMünchen test: {len(records)} records")
    assert len(records) >= 5, f"Expected >=5 records from München, got {len(records)}"

    # Check first record
    r = records[0]
    assert r["last_name"] == "Halboni", f"Expected Halboni, got {r['last_name']}"
    assert r["postal_code"] == "80538", f"Expected 80538, got {r['postal_code']}"
    assert r["phone"] == "089 297448", f"Expected 089 297448, got {r['phone']}"
    print("München assertions PASSED.")
    return True


def test_full_extraction():
    """Run extraction on ALL files and report stats."""
    md_files = sorted(PARSED_MD_DIR.glob("gesund_bund_*.md"))
    total = 0
    nonempty = 0
    for f in md_files:
        content = f.read_text()
        records = extract_from_gesund_bund(content)
        total += len(records)
        if records:
            nonempty += 1

    print(f"\nFull extraction: {total} records from {nonempty}/{len(md_files)} files")
    return total > 0


if __name__ == "__main__":
    ok = True
    ok = test_known_good() and ok
    ok = test_extraction() and ok
    ok = test_full_extraction() and ok
    print(f"\n{'ALL TESTS PASSED' if ok else 'SOME TESTS FAILED'}")
