"""
Finalize Script
Merges all individual JSON extractions and triggers the aggregator logic.
"""

import json
from pathlib import Path

# Import the existing logic from your aggregator file
from aggregator import aggregate_and_export

PROCESSED_DIR = Path("./data/processed_registry")

def merge_and_aggregate():
    print("[finalize] Gathering individual JSON extractions...")
    all_records = []
    
    # Gather all individual json files in the directory
    for json_file in PROCESSED_DIR.glob("*.json"):
        if json_file.name == "all_extractions.json":
            continue # Skip the master file if it already exists
            
        with open(json_file, "r", encoding="utf-8") as f:
            try:
                records = json.load(f)
                if isinstance(records, list):
                    all_records.extend(records)
                elif isinstance(records, dict):
                    all_records.append(records)
            except Exception as e:
                print(f"[finalize] Error reading {json_file.name}: {e}")

    # Save the combined file that aggregator.py expects
    combined_path = PROCESSED_DIR / "all_extractions.json"
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"[finalize] Merged {len(all_records)} records into all_extractions.json")

    # Run the existing aggregator
    print("[finalize] Handing over to aggregator module...")
    aggregate_and_export()

if __name__ == "__main__":
    merge_and_aggregate()