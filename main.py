"""
Controller Node - Phase 1
Central orchestrator for the Bavaria Pediatric Infrastructure Data Aggregation pipeline.
"""

import asyncio
import subprocess
import sys
import time


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def verify_dependencies():
    """Verify all Python dependencies are available."""
    log("Verifying Python dependencies...")
    deps = ["pandas", "openpyxl", "playwright"]
    missing = []
    for dep in deps:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)

    if missing:
        log(f"  Missing: {', '.join(missing)}")
        log("  Install with: pip install " + " ".join(missing))
        return False

    log("  All dependencies satisfied.")
    return True


def verify_playwright_browser():
    """Ensure the Chromium browser runtime exists for Playwright."""
    log("Verifying Playwright Chromium runtime...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        log("  Chromium runtime is ready.")
        return True
    except subprocess.TimeoutExpired:
        log("  ERROR: Playwright browser install timed out.")
        return False
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or str(e)).strip().splitlines()
        log(f"  ERROR: Failed to prepare Chromium: {detail[-1] if detail else e}")
        return False


async def run_pipeline():
    """Execute the full Phase 1 pipeline."""
    start = time.time()
    log("=" * 60)
    log("Bavaria Pediatric Infrastructure Data Aggregation - Phase 1")
    log("=" * 60)

    # Step 0: Verify dependencies
    if not verify_dependencies():
        log("ABORT: Missing dependencies.")
        sys.exit(1)

    if not verify_playwright_browser():
        log("ABORT: Playwright Chromium runtime unavailable.")
        sys.exit(1)

    # Step 1: Data Retrieval (parallel scraper)
    skip_scrape = False
    for i, arg in enumerate(sys.argv):
        if arg == "--skipscrape" and i + 1 < len(sys.argv):
            if sys.argv[i + 1].upper() == "TRUE":
                skip_scrape = True
        elif arg == "--skipscrape=TRUE":
            skip_scrape = True

    if skip_scrape:
        log("-" * 40)
        log("MODULE 1: Data Retrieval [SKIPPED via args]")
        log("-" * 40)
    else:
        log("-" * 40)
        log("MODULE 1: Data Retrieval (4 parallel workers)")
        log("-" * 40)
        from scrape_parallel import run_parallel_scrape
        await run_parallel_scrape()

    # Step 2: HTML Parsing
    log("-" * 40)
    log("MODULE 2: HTML → Markdown Parsing")
    log("-" * 40)
    from parser import process_all_html_files
    parsed_count = process_all_html_files()

    if parsed_count == 0:
        log("WARNING: No HTML files were parsed. Check scraper output.")

    # Step 3: Regex Extraction
    log("-" * 40)
    log("MODULE 3: Regex-based Data Extraction")
    log("-" * 40)
    from extractor import process_markdown_files
    process_markdown_files()

    # Step 4: Data Aggregation
    log("-" * 40)
    log("MODULE 4: Data Aggregation & Deduplication")
    log("-" * 40)
    from aggregator import aggregate_and_export
    aggregate_and_export()

    # Step 5: Export v2 (full + emails-only CSVs)
    log("-" * 40)
    log("MODULE 5: Final Export (Full + Emails-Only)")
    log("-" * 40)
    from export_v2 import run as export_v2_run
    export_v2_run()

    # Final report
    elapsed = time.time() - start
    log("=" * 60)
    log(f"Phase 1 Complete. Total time: {elapsed:.1f}s")
    log("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_pipeline())
