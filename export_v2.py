"""
Export v2: produces two CSVs from the current extraction data.
  1. bavaria_pediatricians_full.csv     — all records (with and without email)
  2. bavaria_pediatricians_emails.csv   — only records that have an email address
"""

import json
import unicodedata
import re
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path("./data/processed_registry")
OUTPUT_DIR = Path("./data/v2_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_text(text):
    if not text or not isinstance(text, str):
        return text
    text = unicodedata.normalize("NFC", text).strip()
    text = re.sub(r'\bStr\.\b', 'Straße', text)
    text = re.sub(r'\bstr\.\b', 'straße', text)
    text = re.sub(r'\bPl\.\b', 'Platz', text)
    return text


def deduplicate(df):
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

    return pd.concat([has_email, no_email], ignore_index=True)


def is_bavarian_plz(plz):
    """Check if a German postal code belongs to Bavaria."""
    if not plz or not isinstance(plz, str):
        return False
    plz = plz.strip()[:5]
    if not plz.isdigit() or len(plz) != 5:
        return False
    n = int(plz)
    # Bavarian PLZ ranges:
    # 63700-63939: Unterfranken (Aschaffenburg, Miltenberg)
    # 80000-87999: Oberbayern, Schwaben
    # 88100-88179: Lindau area
    # 89200-89449: Memmingen, Kaufbeuren area
    # 90000-97999: Franken, Oberpfalz, Niederbayern
    return (
        (63700 <= n <= 63939)
        or (80000 <= n <= 87999)
        or (88100 <= n <= 88179)
        or (89200 <= n <= 89449)
        or (90000 <= n <= 97999)
    )


def run():
    combined = PROCESSED_DIR / "all_extractions.json"
    with open(combined, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"Loaded {len(records)} raw records")

    schema_cols = [
        "title", "first_name", "last_name", "clinic_name",
        "street_address", "postal_code", "city", "searched_locality",
        "email", "phone", "profile_url"
    ]

    df = pd.DataFrame(records)
    for col in schema_cols:
        if col not in df.columns:
            df[col] = None

    # Extract searched locality from source filename
    if "_source_file" in df.columns:
        def extract_locality(filename):
            if not isinstance(filename, str):
                return None
            name = filename.replace(".md", "")
            for prefix in ("gesund_bund_", "116117_"):
                if name.startswith(prefix):
                    return name[len(prefix):]
            return name
        df["searched_locality"] = df["_source_file"].apply(extract_locality)

    df = df[schema_cols]

    # Normalize
    for col in schema_cols:
        df[col] = df[col].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)
    df = df.replace({"null": None, "NULL": None, "None": None, "none": None, "": None})

    # Deduplicate
    before = len(df)
    df = deduplicate(df)
    print(f"Deduplicated: {before} -> {len(df)} records")

    # Filter to Bavaria only (by postal code)
    before_filter = len(df)
    df = df[df["postal_code"].apply(is_bavarian_plz)].copy()
    print(f"Bavaria filter: {before_filter} -> {len(df)} records ({before_filter - len(df)} non-Bavarian removed)")

    df = df.sort_values(["city", "last_name"], na_position="last").reset_index(drop=True)

    # Export FULL dataset
    full_csv = OUTPUT_DIR / "bavaria_pediatricians_full.csv"
    full_xlsx = OUTPUT_DIR / "bavaria_pediatricians_full.xlsx"
    df.to_csv(full_csv, index=False, encoding="utf-8-sig")
    df.to_excel(full_xlsx, index=False, engine="openpyxl")
    print(f"\nFULL dataset: {len(df)} records")
    print(f"  CSV:  {full_csv}")
    print(f"  XLSX: {full_xlsx}")

    # Export EMAILS-ONLY dataset
    df_email = df[df["email"].notna()].copy().reset_index(drop=True)
    email_csv = OUTPUT_DIR / "bavaria_pediatricians_emails.csv"
    email_xlsx = OUTPUT_DIR / "bavaria_pediatricians_emails.xlsx"
    df_email.to_csv(email_csv, index=False, encoding="utf-8-sig")
    df_email.to_excel(email_xlsx, index=False, engine="openpyxl")
    print(f"\nEMAILS-ONLY dataset: {len(df_email)} records")
    print(f"  CSV:  {email_csv}")
    print(f"  XLSX: {email_xlsx}")

    # Summary
    print(f"\n--- Summary ---")
    print(f"Total unique doctors: {len(df)}")
    print(f"With email: {len(df_email)} ({len(df_email)/len(df)*100:.1f}%)")
    print(f"Without email: {len(df) - len(df_email)}")
    print(f"Unique cities: {df['city'].nunique()}")
    print(f"Unique emails: {df_email['email'].nunique()}")

    # Sample of email records
    print(f"\nSample email records:")
    sample = df_email[["title", "first_name", "last_name", "city", "email"]].head(10)
    print(sample.to_string(index=False))


if __name__ == "__main__":
    run()
