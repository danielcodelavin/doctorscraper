"""
Data Structuring Module
Aggregates JSON extractions into deduplicated CSV and XLSX datasets.
Includes dynamic searched_locality extraction.
"""

import json
import unicodedata
import re
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path("./data/processed_registry")


def normalize_text(text: str) -> str:
    """Normalize German text: Unicode NFC, trim whitespace, standardize abbreviations."""
    if not text or not isinstance(text, str):
        return text

    text = unicodedata.normalize("NFC", text)
    text = text.strip()

    text = re.sub(r'\bStr\.\b', 'Straße', text)
    text = re.sub(r'\bstr\.\b', 'straße', text)
    text = re.sub(r'\bPl\.\b', 'Platz', text)

    return text


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deterministic deduplication:
    - Primary key: email + last_name 
    - Secondary key: last_name + postal_code
    """
    if df.empty:
        return df

    has_email = df[df["email"].notna() & (df["email"] != "")]
    no_email = df[df["email"].isna() | (df["email"] == "")]

    if not has_email.empty:
        has_email = has_email.drop_duplicates(subset=["email", "last_name"], keep="first")

    if not no_email.empty:
        valid = no_email[no_email["last_name"].notna() & (no_email["last_name"] != "")]
        if not valid.empty:
            valid = valid.drop_duplicates(subset=["last_name", "postal_code"], keep="first")
        no_email = valid if not valid.empty else pd.DataFrame()

    result = pd.concat([has_email, no_email], ignore_index=True)
    return result


def aggregate_and_export():
    """Main aggregation pipeline."""
    combined_path = PROCESSED_DIR / "all_extractions.json"

    if not combined_path.exists():
        print("[aggregator] No extraction data found. Run extractor first.")
        return

    with open(combined_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not records:
        print("[aggregator] No records to process.")
        return

    print(f"[aggregator] Loading {len(records)} raw records...")

    # Expanded Schema
    schema_cols = [
        "title", "first_name", "last_name", "clinic_name",
        "street_address", "postal_code", "city", "searched_locality", 
        "email", "phone", "profile_url"
    ]

    df = pd.DataFrame(records)

    for col in schema_cols:
        if col not in df.columns:
            df[col] = None

    # Extract searched locality from the source filename
    if "_source_file" in df.columns:
        def extract_locality(filename):
            if not isinstance(filename, str):
                return None
            name = filename.replace(".md", "").replace(".html", "").replace(".json", "")
            if name.startswith("116117_"):
                return name.replace("116117_", "")
            if name.startswith("gesund_bund_"):
                return name.replace("gesund_bund_", "")
            return name
            
        df["searched_locality"] = df["_source_file"].apply(extract_locality)

    # Clean up df for final export
    df = df[schema_cols]

    print("[aggregator] Step 1: Normalizing text...")
    for col in schema_cols:
        df[col] = df[col].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)

    df = df.replace({"null": None, "NULL": None, "None": None, "none": None, "": None})

    print("[aggregator] Step 2: Deduplicating...")
    before = len(df)
    df = deduplicate(df)
    after = len(df)
    print(f"  Removed {before - after} duplicates ({before} -> {after} records)")

    df = df.sort_values(["city", "last_name"], na_position="last").reset_index(drop=True)
    
    csv_path = PROCESSED_DIR / "bavaria_pediatricians_dataset.csv"
    xlsx_path = PROCESSED_DIR / "bavaria_pediatricians_reference.xlsx"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[aggregator] Exported CSV: {csv_path} ({len(df)} records)")

    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"[aggregator] Exported XLSX: {xlsx_path} ({len(df)} records)")

    print(f"\n[aggregator] Dataset Summary:")
    print(f"  Total records: {len(df)}")
    print(f"  With email: {df['email'].notna().sum()}")
    print(f"  Without email: {df['email'].isna().sum()}")
    print(f"  Unique extracted cities: {df['city'].nunique()}")
    print(f"  Unique searched localities: {df['searched_locality'].nunique()}")

    return df


if __name__ == "__main__":
    aggregate_and_export()