"""
Parallel scraper: runs N browser instances concurrently to scrape gesund.bund.de.
Skips already-scraped cities. Expands detail sections to capture emails.
"""

import asyncio
import html
import json
import os
import random
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright

RAW_HTML_DIR = Path("./data/raw_html")
RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)

NUM_WORKERS = 4
CITY_TIMEOUT_SECONDS = 120


def get_bavarian_cities():
    print("[scraper] Fetching Bavarian municipalities via Wikipedia API...")
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
            except Exception as e:
                if "CERTIFICATE_VERIFY_FAILED" not in str(e) or ssl_context is not None:
                    raise
                ssl_context = ssl._create_unverified_context()
                with urllib.request.urlopen(req, context=ssl_context) as response:
                    data = json.loads(response.read().decode('utf-8'))
            for member in data['query']['categorymembers']:
                title = member['title']
                if ":" in title:
                    continue
                cities.append(title.split(" (")[0].strip())
            if 'continue' in data and 'cmcontinue' in data['continue']:
                url = f"{base_url}&{urllib.parse.urlencode({'cmcontinue': data['continue']['cmcontinue']})}"
            else:
                break
        cities = list(set(cities))
        print(f"[scraper] Loaded {len(cities)} municipalities.")
        return cities
    except Exception as e:
        print(f"[scraper] API failed: {e}, using fallback.")
        return ["München", "Nürnberg", "Augsburg", "Regensburg", "Ingolstadt",
                "Würzburg", "Fürth", "Erlangen", "Bamberg", "Bayreuth"]


def safe_city(city):
    return city.replace(" ", "_").replace("ü", "ue").replace("ö", "oe").replace("ä", "ae").replace("/", "_")


def build_text_snapshot_html(title, source_url, text):
    paragraphs = []
    for block in text.split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        paragraphs.append("<p>" + "<br/>\n".join(html.escape(line) for line in lines) + "</p>")
    body = "\n".join(paragraphs) if paragraphs else f"<p>{html.escape(text.strip())}</p>"
    return (
        "<!doctype html>\n<html><head>"
        f"<meta charset='utf-8'><title>{html.escape(title)}</title>"
        f"</head><body><h1>{html.escape(title)}</h1>"
        f"<p>Source URL: {html.escape(source_url)}</p>{body}</body></html>"
    )


def extract_relevant_text(text, start_markers, end_markers):
    working = text.strip()
    start_idx = -1
    for m in start_markers:
        idx = working.find(m)
        if idx >= 0 and (start_idx == -1 or idx < start_idx):
            start_idx = idx
    if start_idx >= 0:
        working = working[start_idx:]
    end_idx = -1
    for m in end_markers:
        idx = working.find(m)
        if idx >= 0 and (end_idx == -1 or idx < end_idx):
            end_idx = idx
    if end_idx >= 0:
        working = working[:end_idx]
    return working.strip()


async def dismiss_cookies(page):
    for sel in [
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "button:has-text('Alle akzeptieren')",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(timeout=3000)
                await asyncio.sleep(1)
        except Exception:
            pass


async def scrape_one_city(page, city, expected_file):
    """Scrape a single city with detail expansion."""
    base_url = "https://gesund.bund.de/suchen/aerztinnen-und-aerzte"
    await page.goto(base_url, timeout=25000, wait_until="domcontentloaded")
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
        alt = page.locator("[role='option']:has-text('Kinderarzt')").first
        if await alt.count() > 0:
            await alt.click(timeout=5000)
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

    # Wait for results
    for sel in ["text=Weitere Ergebnisse anzeigen", "text=keine Ergebnisse",
                "text=Ergebnis", "text=Treffer"]:
        try:
            await page.locator(sel).first.wait_for(timeout=10000)
            break
        except Exception:
            continue

    # Load ALL results
    for _ in range(20):
        try:
            mehr = page.locator("text=Weitere Ergebnisse anzeigen").first
            if await mehr.count() > 0 and await mehr.is_visible():
                await mehr.click(timeout=5000)
                await asyncio.sleep(1.2)
            else:
                break
        except Exception:
            break

    # Expand ALL details via JS
    await page.evaluate("""
        () => {
            document.querySelectorAll('button, [role="button"], a').forEach(el => {
                if (el.innerText && el.innerText.trim() === 'Details anzeigen') {
                    el.click();
                }
            });
        }
    """)
    await asyncio.sleep(1.5)

    text = await page.inner_text("body")
    text = extract_relevant_text(
        text,
        start_markers=["Suchergebnisse", "Suchergebnisse:"],
        end_markers=["Haben Sie Anmerkungen zur Arztsuche", "Zurück nach oben", "gesund.bund.de"],
    )
    if not text:
        text = await page.inner_text("body")

    expected_file.write_text(
        build_text_snapshot_html(f"gesund.bund results for {city}", page.url, text),
        encoding="utf-8",
    )


async def worker(worker_id, city_queue, stats):
    """Worker that processes cities from a shared queue."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="de-DE",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        page.set_default_timeout(10000)
        cities_done = 0

        while not city_queue.empty():
            try:
                city = city_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            safe_name = safe_city(city)
            expected_file = RAW_HTML_DIR / f"gesund_bund_{safe_name}.html"

            if expected_file.exists():
                stats["skipped"] += 1
                continue

            try:
                await asyncio.wait_for(
                    scrape_one_city(page, city, expected_file),
                    timeout=CITY_TIMEOUT_SECONDS
                )
                stats["saved"] += 1
                total = stats["saved"] + stats["skipped"] + stats["failed"]
                print(f"  [W{worker_id}] Saved {expected_file.name} ({stats['saved']} saved, {total}/{stats['total']} processed)", flush=True)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                stats["failed"] += 1
                err = str(e).split('\n')[0][:80]
                print(f"  [W{worker_id}] Failed {city}: {err}", flush=True)

            cities_done += 1
            if cities_done % 20 == 0:
                try:
                    await page.close()
                except Exception:
                    pass
                page = await context.new_page()
                page.set_default_timeout(10000)

        try:
            await page.close()
            await browser.close()
        except Exception:
            pass


async def run_parallel_scrape():
    cities = get_bavarian_cities()
    random.shuffle(cities)

    queue = asyncio.Queue()
    for city in cities:
        await queue.put(city)

    stats = {"total": len(cities), "saved": 0, "skipped": 0, "failed": 0}
    print(f"[scraper] Starting parallel scrape with {NUM_WORKERS} workers for {len(cities)} cities...")

    workers = [worker(i, queue, stats) for i in range(NUM_WORKERS)]
    await asyncio.gather(*workers)

    print(f"\n[scraper] Complete!")
    print(f"  Saved: {stats['saved']}")
    print(f"  Skipped (already existed): {stats['skipped']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Total: {stats['saved'] + stats['skipped'] + stats['failed']}")


if __name__ == "__main__":
    asyncio.run(run_parallel_scrape())
