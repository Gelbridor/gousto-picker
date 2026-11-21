"""Fetch this week's Gousto menu.

Primary: the JSON feed the menu page itself calls (production-api.gousto.co.uk/menu/v3/menus).
Fallback: drive the real page with Playwright and capture that same response.
"""
import json
import threading
import time
import urllib.request
import uuid
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


# Gousto A/B tests its menu: the same week can have several versions, and which one you get depends on your
# visitor (device) ID - a visitor stays in the same group week after week. These fixed IDs are enough to find
# every version (with 8 IDs the chance of missing one of two equal groups is under 1%).
VERSION_DEVICES = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"gousto-picker/visitor/{n}")) for n in range(8)]


def _get(url, device=None):
    headers = {**HEADERS, "x-gousto-device-id": device} if device else HEADERS
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def _delivery_date(period):
    # Gousto delivers a few days after the Tuesday-noon rollover; any valid day in the period works.
    return (datetime.fromisoformat(period["from"]) + timedelta(days=4)).date().isoformat()


def fetch_via_api(weeks=3):
    periods = sorted(_get(f"{API}/menu/v1/active-periods")["data"], key=lambda p: p["offset"])[:weeks]
    return [_get(f"{API}/menu/v3/menus?" + MENU_QS.format(date=_delivery_date(p))) for p in periods]


def fetch_menu_for(delivery_date, device=None):
    """The menu that was (or will be) delivered on this date, e.g. a past week's menu for learning."""
    return _get(f"{API}/menu/v3/menus?" + MENU_QS.format(date=delivery_date), device)


def upcoming_dates(weeks=3):
    periods = sorted(_get(f"{API}/menu/v1/active-periods")["data"], key=lambda p: p["offset"])[:weeks]
    return [_delivery_date(p) for p in periods]


def fetch_versions(dates, devices=VERSION_DEVICES, budget=150):
    """{date: {device: menu}} for every date as seen by every test visitor. Daemon threads with one overall time
    limit, so a stuck request can't hold up the build; anything not back in time is simply missing."""
    out = {d: {} for d in dates}

    def get(d, dev):
        try:
            out[d][dev] = fetch_menu_for(d, dev)
        except Exception as exc:  # noqa: BLE001
            print(f"Menu {d} for test visitor {dev[:8]} failed: {exc}", flush=True)

    threads = [threading.Thread(target=get, args=(d, dev), daemon=True) for d in dates for dev in devices]
    for n, t in enumerate(threads):
        t.start()
        if n % 8 == 7:
            time.sleep(0.5)   # be gentle: at most ~16 requests a second
    deadline = time.monotonic() + budget
    for t in threads:
        t.join(max(0, deadline - time.monotonic()))
    return {d: dict(v) for d, v in out.items()}


def fetch_via_playwright(weeks=3):
    """Open the real menu page, then call the same feed from inside it for each upcoming week."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.gousto.co.uk/menu", wait_until="networkidle", timeout=90000)
        menus = page.evaluate(
            """async ([api, qs, weeks]) => {
              const get = async u => (await fetch(u, {headers: {'x-gousto-device-id': crypto.randomUUID()}})).json();
              const periods = (await get(api + '/menu/v1/active-periods')).data
                .sort((a, b) => a.offset - b.offset).slice(0, weeks);
              const out = [];
              for (const p of periods) {
                const d = new Date(new Date(p.from).getTime() + 4 * 864e5).toISOString().slice(0, 10);
                out.push(await get(api + '/menu/v3/menus?' + qs.replace('{date}', d)));
              }
              return out;
            }""",
            [API, MENU_QS, weeks],
        )
        browser.close()
    if not menus:
        raise RuntimeError("Playwright did not get any menus")
    return menus


def fetch_menus(weeks=3):
    try:
        return fetch_via_api(weeks), "api"
    except Exception as exc:  # noqa: BLE001 - any failure -> try the browser route
        print(f"API fetch failed ({exc}); falling back to Playwright")
        return fetch_via_playwright(weeks), "playwright"
