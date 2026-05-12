"""
NLP Extraction Engine
Uses regex-based extraction for gesund.bund.de pages (fast, accurate).
Falls back to Ollama LLM only when regex fails.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

PARSED_MD_DIR = Path("./data/parsed_markdown")
PROCESSED_DIR = Path("./data/processed_registry")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "qwen3.5:4b"

POSTAL_CITY_RE = re.compile(r"^\d{5}\s+.+$")
PHONE_RE = re.compile(r"^(?:\+?\d[\d\s()/.-]+)$")
NAME_LINE_RE = re.compile(
    r"^(?:(?:Prof\.\s*)?(?:Dr\.\s*(?:med\.\s*)?)?|[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)"
)

# ── Helpers ──

def normalize_nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def looks_like_provider_name(line: str) -> bool:
    skip = {
        "Suchergebnisse", "Karte ausblenden", "Details anzeigen",
        "Telefon:", "Entfernung:", "Source URL:", "Weitere Ergebnisse anzeigen",
    }
    if line in skip or line.startswith("Suchergebnisse:") or line.startswith("Weitere Ergebnisse"):
        return False
    if any(ch.isdigit() for ch in line):
        return False
    if POSTAL_CITY_RE.match(line) or PHONE_RE.match(line):
        return False
    return bool(NAME_LINE_RE.match(line))


def is_provider_start(lines: list, idx: int) -> bool:
    if not looks_like_provider_name(lines[idx]):
        return False
    lookahead = lines[idx + 1: idx + 5]
    return any(POSTAL_CITY_RE.match(c) for c in lookahead)


# ── Block splitting ──

def split_gesund_bund_blocks(text: str) -> list[str]:
    """Split a gesund.bund result page into per-provider text blocks."""
    lines = normalize_nonempty_lines(text)
    if not lines:
        return []

    blocks, current = [], []
    i = 0
    while i < len(lines):
        if is_provider_start(lines, i):
            if current:
                blocks.append("\n".join(current))
            current = [lines[i]]
            i += 1
            continue

        if current:
            current.append(lines[i])
            # "Entfernung:" + value marks end of a block
            if lines[i] == "Entfernung:" and i + 1 < len(lines):
                current.append(lines[i + 1])
                blocks.append("\n".join(current))
                current = []
                i += 2
                continue

        i += 1

    if current:
        blocks.append("\n".join(current))

    # Keep only blocks that look like real provider entries
    return [b for b in blocks if "Telefon:" in b or POSTAL_CITY_RE.search(b)]


# ── Name parsing ──

def split_name_line(name_line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    parts = name_line.split()
    if not parts:
        return None, None, None

    title_parts = []
    idx = 0
    while idx < len(parts) and parts[idx].rstrip(".") in {"Dr", "med", "Prof"}:
        title_parts.append(parts[idx])
        idx += 1

    person = parts[idx:]
    title = " ".join(title_parts) or None
    if not person:
        return title, None, None
    if len(person) == 1:
        return title, None, person[0]
    return title, " ".join(person[:-1]), person[-1]


# ── Per-block extraction ──

def parse_gesund_bund_block(block: str) -> Optional[dict]:
    lines = normalize_nonempty_lines(block)
    if len(lines) < 3:
        return None

    name_line = lines[0]
    postal_idx = next((i for i, l in enumerate(lines) if POSTAL_CITY_RE.match(l)), -1)
    if postal_idx < 1:
        return None

    phone = None
    if "Telefon:" in lines:
        pi = lines.index("Telefon:")
        if pi + 1 < len(lines):
            phone = lines[pi + 1]

    email = None
    if "E-Mail:" in lines:
        ei = lines.index("E-Mail:")
        if ei + 1 < len(lines):
            candidate = lines[ei + 1]
            if "@" in candidate:
                email = candidate.strip()

    street = " ".join(lines[1:postal_idx]).strip() or None
    postal_code, city = lines[postal_idx].split(" ", 1)
    title, first_name, last_name = split_name_line(name_line)

    return {
        "title": title,
        "first_name": first_name,
        "last_name": last_name,
        "clinic_name": None,
        "street_address": street,
        "postal_code": postal_code,
        "city": city.strip() or None,
        "email": email,
        "phone": phone,
        "profile_url": None,
    }


# ── Main extraction entry points ──

def extract_from_gesund_bund(content: str) -> list[dict]:
    """Regex-based extraction for gesund.bund.de pages. No LLM needed."""
    records = []
    for block in split_gesund_bund_blocks(content):
        parsed = parse_gesund_bund_block(block)
        if parsed:
            records.append(parsed)
    return records


def process_markdown_files():
    """Process all Markdown files. Uses regex for gesund_bund, skips others."""
    md_files = sorted(PARSED_MD_DIR.glob("*.md"))
    print(f"[extractor] Found {len(md_files)} Markdown files to process.")

    all_records = []
    stats = {"total_files": len(md_files), "files_with_records": 0, "total_records": 0, "empty_files": 0}

    for i, md_file in enumerate(md_files):
        if (i + 1) % 100 == 0 or i == 0:
            print(f"  Processing {md_file.name} ({i+1}/{len(md_files)})...")

        content = md_file.read_text(encoding="utf-8")
        if len(content) < 30:
            stats["empty_files"] += 1
            continue

        # Use regex extraction for gesund_bund files
        if "gesund_bund" in md_file.name:
            file_records = extract_from_gesund_bund(content)
        else:
            file_records = []

        # Tag records with source
        for r in file_records:
            r["_source_file"] = md_file.name
            r["_source"] = "gesund.bund.de" if "gesund_bund" in md_file.name else "unknown"

        if file_records:
            all_records.extend(file_records)
            stats["files_with_records"] += 1
            stats["total_records"] += len(file_records)
        else:
            stats["empty_files"] += 1

        # Save per-file JSON
        json_file = PROCESSED_DIR / f"{md_file.stem}.json"
        json_file.write_text(
            json.dumps(file_records, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Save combined
    combined_path = PROCESSED_DIR / "all_extractions.json"
    combined_path.write_text(
        json.dumps(all_records, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\n[extractor] Complete.")
    print(f"  Files processed: {stats['total_files']}")
    print(f"  Files with records: {stats['files_with_records']}")
    print(f"  Files empty/skipped: {stats['empty_files']}")
    print(f"  Total records extracted: {stats['total_records']}")
    return all_records


if __name__ == "__main__":
    process_markdown_files()
