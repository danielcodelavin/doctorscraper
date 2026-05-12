"""
Data Retrieval Module
Automated retrieval from the public gesund.bund.de registry using Playwright.
Dynamically fetches Bavarian municipalities via Wikipedia API.
"""

import asyncio
import html
import json
import os
import random
import ssl
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright

RAW_HTML_DIR = Path("./data/raw_html")
RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
ERROR_DIR = RAW_HTML_DIR / "_errors"
ERROR_DIR.mkdir(parents=True, exist_ok=True)
CITY_TIMEOUT_SECONDS = 180
PAGE_GOTO_TIMEOUT_MS = 25000
MAX_CITY_ATTEMPTS = 3
PAGE_RECYCLE_EVERY = 25
RETRYABLE_ERROR_SNIPPETS = (
    "ERR_TIMED_OUT",
    "Timeout",
    "Target page, context or browser has been closed",
    "net::ERR",
)

def get_bavarian_cities():
    """Dynamically fetch all Bavarian municipalities using the official Wikipedia JSON API."""
    print("[scraper] Fetching list of all Bavarian municipalities via Wikipedia API...")
    cities = []
    ssl_context = None
    
    base_url = "https://de.wikipedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Kategorie:Gemeinde_in_Bayern&cmlimit=500&format=json"
    url = base_url

    try:
        while True:
            req = urllib.request.Request(url, headers={'User-Agent': 'Bavaria-Academic-Research-Bot/1.0'})
            try:
                with urllib.request.urlopen(req, context=ssl_context) as response:
                    data = json.loads(response.read().decode('utf-8'))
            except Exception as fetch_error:
                if "CERTIFICATE_VERIFY_FAILED" not in str(fetch_error) or ssl_context is not None:
                    raise

                # Some local Python installs do not have an up-to-date CA bundle.
                ssl_context = ssl._create_unverified_context()
                with urllib.request.urlopen(req, context=ssl_context) as response:
                    data = json.loads(response.read().decode('utf-8'))

            for member in data['query']['categorymembers']:
                title = member['title']
                if ":" in title:  
                    continue
                
                clean_name = title.split(" (")[0].strip()
                cities.append(clean_name)

            if 'continue' in data and 'cmcontinue' in data['continue']:
                cmcontinue = data['continue']['cmcontinue']
                params = urllib.parse.urlencode({'cmcontinue': cmcontinue})
                url = f"{base_url}&{params}"
            else:
                break

        cities = list(set(cities))
        
        if len(cities) > 500:
            print(f"[scraper] Successfully loaded {len(cities)} municipalities via API.")
            return cities
        else:
            raise ValueError(f"API returned too few results: {len(cities)}")
            
    except Exception as e:
        print(f"[scraper] API fetch failed: {e}")
        print("[scraper] Falling back to robust built-in list.")
        return [
            "München", "Nürnberg", "Augsburg", "Regensburg", "Ingolstadt",
            "Würzburg", "Fürth", "Erlangen", "Bamberg", "Bayreuth"
        ]


async def polite_delay(min_sec=2.0, max_sec=5.0):
    await asyncio.sleep(random.uniform(min_sec, max_sec))


def safe_city(city):
    return city.replace(" ", "_").replace("ü", "ue").replace("ö", "oe").replace("ä", "ae").replace("/", "_")


def error_marker_path(source_name, city):
    return ERROR_DIR / f"{source_name}_{safe_city(city)}.json"


def build_text_snapshot_html(title, source_url, text):
    paragraphs = []
    for block in text.split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        paragraphs.append("<p>" + "<br/>\n".join(html.escape(line) for line in lines) + "</p>")

    body = "\n".join(paragraphs) if paragraphs else f"<p>{html.escape(text.strip())}</p>"
    return (
        "<!doctype html>\n"
        "<html><head>"
        f"<meta charset='utf-8'><title>{html.escape(title)}</title>"
        "</head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f"<p>Source URL: {html.escape(source_url)}</p>"
        f"{body}"
        "</body></html>"
    )


def extract_relevant_text(text, start_markers, end_markers):
    """Trim large rendered pages down to the most useful results section."""
    working = text.strip()
    start_idx = -1
    for marker in start_markers:
        idx = working.find(marker)
        if idx >= 0 and (start_idx == -1 or idx < start_idx):
            start_idx = idx
    if start_idx >= 0:
        working = working[start_idx:]

    end_idx = -1
    for marker in end_markers:
        idx = working.find(marker)
        if idx >= 0 and (end_idx == -1 or idx < end_idx):
            end_idx = idx
    if end_idx >= 0:
        working = working[:end_idx]

    return working.strip()


async def save_rendered_text_snapshot(page, expected_file, title, selectors):
    text = ""
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            if await locator.count() > 0:
                candidate = (await locator.inner_text()).strip()
                if len(candidate) > len(text):
                    text = candidate
        except Exception:
            continue

    if not text:
        text = (await page.inner_text("body")).strip()

    snapshot_html = build_text_snapshot_html(title, page.url, text)
    expected_file.write_text(snapshot_html, encoding="utf-8")


def get_target_cities():
    """Return the city list, optionally narrowed for local testing via env vars."""
    only_cities = os.getenv("SCRAPER_CITIES", "").strip()
    if only_cities:
        requested = [c.strip() for c in only_cities.split(",") if c.strip()]
        if requested:
            return requested

    cities = get_bavarian_cities()

    limit = os.getenv("SCRAPER_CITY_LIMIT", "").strip()
    if limit.isdigit():
        return cities[: int(limit)]

    return cities


async def dismiss_cookies(page):
    for sel in [
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Alle Akzeptieren')",
        "button:has-text('Alle zulassen')",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(timeout=3000)
                await asyncio.sleep(1)
        except Exception:
            pass


async def wait_for_gesund_results(page):
    """Wait for either a result page or a valid no-results state."""
    for sel in [
        "text=Weitere Ergebnisse anzeigen",
        "text=keine Ergebnisse",
        "text=Keine Ergebnisse",
        "text=Ergebnis",
        "text=Treffer",
    ]:
        try:
            await page.locator(sel).first.wait_for(timeout=12000)
            return
        except Exception:
            continue

    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass


async def wait_for_116117_results(page):
    """Wait for the results view to render after clicking the custom search control."""
    for sel in [
        "text=Ergebnisse gefunden",
        "text=Ergebnis gefunden",
        "text=keine Ergebnisse",
        "text=Keine Ergebnisse",
        "text=Filter löschen",
        "text=Leider ist ein Fehler aufgetreten",
    ]:
        try:
            await page.locator(sel).first.wait_for(timeout=4000)
            return
        except Exception:
            continue

    try:
        await page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass


async def run_with_timeout(coro, city, source):
    """Prevent a single city from blocking the full scraper run."""
    try:
        return await asyncio.wait_for(coro, timeout=CITY_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        print(f"    Skipping {city}: {source} timed out after {CITY_TIMEOUT_SECONDS}s")
        return None


def is_retryable_error(exc: Exception) -> bool:
    message = str(exc)
    return any(snippet in message for snippet in RETRYABLE_ERROR_SNIPPETS)


async def new_page(context):
    page = await context.new_page()
    page.set_default_timeout(10000)
    return page


async def recycle_page(page, context):
    try:
        await page.close()
    except Exception:
        pass
    return await new_page(context)


async def scrape_gesund_city(page, city, expected_file):
    base_url = "https://gesund.bund.de/suchen/aerztinnen-und-aerzte"
    await page.goto(base_url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
    await dismiss_cookies(page)

    fach = page.locator("#arztsuche-fachrichtung")
    await fach.wait_for(state="visible", timeout=10000)
    await fach.click(timeout=5000)
    await asyncio.sleep(0.3)
    await fach.fill("Kinder", timeout=5000)
    await asyncio.sleep(1.5)

    opt = page.locator("[role='option']:has-text('Kinderarzt / Kinderärztin')").first
    if await opt.count() > 0:
        await opt.click(timeout=5000)
    else:
        alt_opt = page.locator("[role='option']:has-text('Kinderarzt')").first
        if await alt_opt.count() > 0:
            await alt_opt.click(timeout=5000)
        else:
            await fach.press("ArrowDown")
            await asyncio.sleep(0.3)
            await fach.press("Enter")

    ort = page.locator("#arztsuche__field_where")
    await ort.click(timeout=5000)
    await ort.fill(city, timeout=5000)
    await asyncio.sleep(1.5)

    pac = page.locator(".pac-item").first
    if await pac.count() > 0:
        await pac.click(timeout=5000)
    else:
        await ort.press("ArrowDown")
        await asyncio.sleep(0.3)
        await ort.press("Enter")

    submit = page.locator("button:has-text('Jetzt suchen')").first
    if await submit.count() == 0:
        submit = page.locator("button:has-text('Suchen')").first
    await submit.click(timeout=5000)

    await wait_for_gesund_results(page)

    # Load ALL results by clicking "Weitere Ergebnisse anzeigen" repeatedly
    for _ in range(20):
        try:
            mehr_btn = page.locator("text=Weitere Ergebnisse anzeigen").first
            if await mehr_btn.count() > 0 and await mehr_btn.is_visible():
                await mehr_btn.click(timeout=5000)
                await asyncio.sleep(1.5)
            else:
                break
        except Exception:
            break

    # Expand ALL "Details anzeigen" via JS (much faster than clicking one by one)
    await page.evaluate("""
        () => {
            document.querySelectorAll('button, [role="button"], a').forEach(el => {
                if (el.innerText && el.innerText.trim() === 'Details anzeigen') {
                    el.click();
                }
            });
        }
    """)
    await asyncio.sleep(2)

    text = await page.inner_text("body")
    text = extract_relevant_text(
        text,
        start_markers=["Suchergebnisse", "Suchergebnisse:"],
        end_markers=[
            "Haben Sie Anmerkungen zur Arztsuche",
            "Zurück nach oben",
            "gesund.bund.de",
        ],
    )
    if not text:
        text = await page.inner_text("body")
    expected_file.write_text(
        build_text_snapshot_html(
            f"gesund.bund results for {city}",
            page.url,
            text,
        ),
        encoding="utf-8",
    )


async def scrape_116117_city(page, city, expected_file):
    base_url = "https://arztsuche.116117.de/"
    await page.goto(base_url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
    await dismiss_cookies(page)

    fach = page.locator("#WenoderWasSearchInput")
    ort = page.locator("#Ort-PflichtfeldSearchInput")
    await fach.wait_for(state="visible", timeout=10000)
    await ort.wait_for(state="visible", timeout=10000)

    await fach.click(timeout=5000)
    await asyncio.sleep(0.3)
    await fach.fill("Kinder", timeout=5000)
    await asyncio.sleep(2)

    fach_opt = page.locator("[role='option']:has-text('Kinderarzt / Kinderärztin')").first
    if await fach_opt.count() > 0:
        await fach_opt.click(timeout=5000)
    else:
        fallback_opt = page.locator("[role='option']:has-text('Kinderarzt')").first
        if await fallback_opt.count() > 0:
            await fallback_opt.click(timeout=5000)
        else:
            await fach.press("ArrowDown")
            await asyncio.sleep(0.3)
            await fach.press("Enter")

    await asyncio.sleep(0.5)
    await ort.click(timeout=5000)
    await ort.fill(city, timeout=5000)
    await asyncio.sleep(2)

    matching_options = page.locator(f"[role='option']:has-text('{city}')")
    if await matching_options.count() > 0:
        await matching_options.first.click(timeout=5000)
    else:
        loc_opt = page.locator("[role='option']").first
        if await loc_opt.count() > 0:
            await loc_opt.click(timeout=5000)
        else:
            await ort.press("ArrowDown")
            await asyncio.sleep(0.3)
            await ort.press("Enter")

    await asyncio.sleep(1)
    await page.locator("#searchBtn").first.click(timeout=5000)
    await wait_for_116117_results(page)
    body = await page.inner_text("body")
    if "Leider ist ein Fehler aufgetreten" in body:
        return {"status": "error", "reason": "site_error"}

    text = extract_relevant_text(
        body,
        start_markers=["Ergebnisse gefunden", "Ergebnis gefunden"],
        end_markers=["Diese Seite teilen", "Nach oben", "Herausgegeben von"],
    )
    if not text:
        text = body

    expected_file.write_text(
        build_text_snapshot_html(
            f"116117 results for {city}",
            page.url,
            text,
        ),
        encoding="utf-8",
    )
    return {"status": "saved"}


async def scrape_gesund_bund(context):
    print("\n[scraper] Starting gesund.bund.de retrieval...")
    saved_files = []
    cities = get_target_cities()
    page = await new_page(context)

    total_cities = len(cities)

    for idx, city in enumerate(cities, start=1):
        safe_name = safe_city(city)
        expected_file = RAW_HTML_DIR / f"gesund_bund_{safe_name}.html"
        error_marker = error_marker_path("gesund_bund", city)
        
        if expected_file.exists():
            print(f"  Skipping {city} (gesund.bund.de) - already downloaded.")
            saved_files.append(str(expected_file))
            continue
        if error_marker.exists():
            print(f"  Skipping {city} (gesund.bund.de) - previous error recorded.")
            continue

        print(f"  Searching {city}... ({idx}/{total_cities})")
        try:
            result = await run_with_timeout(
                scrape_gesund_city(page, city, expected_file),
                city,
                "gesund.bund.de",
            )
            if result is None and not expected_file.exists():
                continue

            saved_files.append(str(expected_file))
            print(f"    Saved {expected_file.name}")
            
            await polite_delay(1.0, 2.0)

        except Exception as e:
            err_msg = str(e).split('\n')[0]
            print(f"    Skipping {city}: {err_msg}")

        if idx % PAGE_RECYCLE_EVERY == 0:
            page = await recycle_page(page, context)

    try:
        await page.close()
    except Exception:
        pass

    print(f"\n  [gesund.bund] Completed parsing cycle.")
    return saved_files


async def scrape_116117(context):
    print("\n[scraper] Starting arztsuche.116117.de retrieval...")
    saved_files = []
    cities = get_target_cities()
    page = await new_page(context)
    consecutive_failures = 0

    total_cities = len(cities)

    for idx, city in enumerate(cities, start=1):
        safe_name = safe_city(city)
        expected_file = RAW_HTML_DIR / f"116117_{safe_name}.html"
        error_marker = error_marker_path("116117", city)
        
        if expected_file.exists():
            print(f"  Skipping {city} (116117) - already downloaded.")
            saved_files.append(str(expected_file))
            continue
        if error_marker.exists():
            print(f"  Skipping {city} (116117) - previous error recorded.")
            continue

        print(f"  Searching {city}... ({idx}/{total_cities})")
        success = False

        for attempt in range(1, MAX_CITY_ATTEMPTS + 1):
            try:
                result = await run_with_timeout(
                    scrape_116117_city(page, city, expected_file),
                    city,
                    "arztsuche.116117.de",
                )
                if result is None and not expected_file.exists():
                    if attempt < MAX_CITY_ATTEMPTS:
                        print(f"    Retrying {city} after timeout ({attempt}/{MAX_CITY_ATTEMPTS})")
                        page = await recycle_page(page, context)
                        await polite_delay(5.0, 9.0)
                        continue
                    consecutive_failures += 1
                    break

                if isinstance(result, dict) and result.get("status") == "error":
                    if attempt < MAX_CITY_ATTEMPTS:
                        print(f"    Retrying {city} after site error ({attempt}/{MAX_CITY_ATTEMPTS})")
                        page = await recycle_page(page, context)
                        await polite_delay(6.0, 10.0)
                        continue

                    error_marker.write_text(
                        json.dumps(
                            {
                                "city": city,
                                "source": "116117",
                                "reason": result.get("reason"),
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    print(f"    Recorded 116117 error for {city}")
                    consecutive_failures += 1
                    break

                saved_files.append(str(expected_file))
                print(f"    Saved {expected_file.name}")
                success = True
                consecutive_failures = 0
                break

            except Exception as e:
                err_msg = str(e).split('\n')[0]
                if attempt < MAX_CITY_ATTEMPTS and is_retryable_error(e):
                    print(f"    Retry {attempt}/{MAX_CITY_ATTEMPTS} for {city}: {err_msg}")
                    page = await recycle_page(page, context)
                    await polite_delay(5.0, 9.0)
                    continue

                print(f"    Skipping {city}: {err_msg}")
                consecutive_failures += 1
                break

        if success:
            await polite_delay(4.0, 8.0)

        if idx % PAGE_RECYCLE_EVERY == 0 or consecutive_failures >= 5:
            if consecutive_failures >= 5:
                print("    Recycling 116117 page after repeated failures")
                await polite_delay(10.0, 15.0)
                consecutive_failures = 0
            page = await recycle_page(page, context)

    try:
        await page.close()
    except Exception:
        pass

    print(f"\n  [116117] Completed parsing cycle.")
    return saved_files


async def run_scraper():
    """Main scraper entry point."""
    all_results = {"gesund_bund": []}
    skip_gesund = False

    # Check for --skip argument in sys.argv
    if "--skip" in sys.argv:
        try:
            skip_idx = sys.argv.index("--skip")
            skip_val = sys.argv[skip_idx + 1]
            if skip_val == "2":
                skip_gesund = True
        except IndexError:
            pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="de-DE",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        if not skip_gesund:
            all_results["gesund_bund"] = await scrape_gesund_bund(context)
        else:
            print("\n[scraper] Skipping gesund.bund.de (--skip 2 activated).")
        await browser.close()

    # Save index
    index_path = RAW_HTML_DIR / "url_index.json"
    index_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    return all_results

if __name__ == "__main__":
    asyncio.run(run_scraper())
