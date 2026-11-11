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


def _delivery_date(period):
    # Gousto delivers a few days after the Tuesday-noon rollover; any valid day in the period works.
    return (datetime.fromisoformat(period["from"]) + timedelta(days=4)).date().isoformat()


def fetch_via_api(weeks=3):
    periods = sorted(_get(f"{API}/menu/v1/active-periods")["data"], key=lambda p: p["offset"])[:weeks]
    return [_get(f"{API}/menu/v3/menus?" + MENU_QS.format(date=_delivery_date(p))) for p in periods]


def fetch_menu_for(delivery_date):
    """The menu that was (or will be) delivered on this date, e.g. a past week's menu for learning."""
    return _get(f"{API}/menu/v3/menus?" + MENU_QS.format(date=delivery_date))


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
