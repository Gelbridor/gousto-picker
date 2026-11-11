"""Fetch this week's Gousto menu.

Primary: the JSON feed the menu page itself calls (production-api.gousto.co.uk/menu/v3/menus).
Fallback: drive the real page with Playwright and capture that same response.
"""
import json
import urllib.request
from datetime import datetime, timedelta

API = "https://production-api.gousto.co.uk"
DEVICE_ID = "0511d6cb-2360-4fb0-a80a-ffcc30c47eaa"  # any UUID works; the site just wants one
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.gousto.co.uk/",
    "x-gousto-device-id": DEVICE_ID,
}
MENU_QS = (
    "include_core_recipe_id=true&include_core_menu_id=true&include_category_merchandising=true"
    "&delivery_date={date}&num_portions=2&option_types=none&option_types=recipes&option_types=ingredients"
)


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def fetch_via_api():
    periods = _get(f"{API}/menu/v1/active-periods")["data"]
    current = min(periods, key=lambda p: p["offset"])  # offset 0 = the week currently on sale
    start = datetime.fromisoformat(current["from"])
    # Gousto delivers a few days after the Tuesday-noon menu rollover; any valid day in the period works.
    delivery = (start + timedelta(days=4)).date().isoformat()
    menu = _get(f"{API}/menu/v3/menus?" + MENU_QS.format(date=delivery))
    return menu


def fetch_via_playwright():
    from playwright.sync_api import sync_playwright

    captured = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        def on_response(resp):
            if "/menu/v3/menus" in resp.url and resp.status == 200 and "menu" not in captured:
                captured["menu"] = resp.json()

        page.on("response", on_response)
        page.goto("https://www.gousto.co.uk/menu", wait_until="networkidle", timeout=90000)
        browser.close()
    if "menu" not in captured:
        raise RuntimeError("Playwright did not observe the menu feed")
    return captured["menu"]


def fetch_menu():
    try:
        return fetch_via_api(), "api"
    except Exception as exc:  # noqa: BLE001 - any failure -> try the browser route
        print(f"API fetch failed ({exc}); falling back to Playwright")
        return fetch_via_playwright(), "playwright"
