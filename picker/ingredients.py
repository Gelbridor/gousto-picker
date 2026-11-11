"""Fetch each recipe's ingredient list from the cookbook feed Gousto's recipe pages use."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

from .fetch import API, _get

WORKERS = 8


def _retry(fn, tries=3):
    for n in range(tries):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - transient gateway errors are common here
            if n == tries - 1:
                return None
            time.sleep(1 + n)


def slug_from_name(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "").replace("’", ""))
    return s.strip("-")


def id_to_slug():
    """Map a menu recipe id to its cookbook slug by paging the cookbook index."""
    def page(offset):
        r = _retry(lambda: _get(f"{API}/cmsreadbroker/v1/recipes?limit=50&offset={offset}"))
        return r["data"]["entries"] if r else []

    total = _get(f"{API}/cmsreadbroker/v1/recipes?limit=1")["data"]["count"]
    with ThreadPoolExecutor(WORKERS) as ex:
        pages = list(ex.map(page, range(0, total, 50)))
    return {e["gousto_uid"]: e["url"].rstrip("/").split("/")[-1] for p in pages for e in p}


def _one(item):
    recipe_id, name, slug = item
    for s in dict.fromkeys([slug, slug_from_name(name)]):
        if not s:
            continue
        r = _retry(lambda: _get(f"{API}/cmsreadbroker/v1/recipe/{s}"))
        if r:
            entry = r["data"]["entry"]
            names = {(i.get("name") or i.get("label") or "").strip().lower() for i in entry.get("ingredients", [])}
            return recipe_id, sorted(n for n in names if n), s
    return recipe_id, None, None


def fetch_ingredients(recipes):
    """recipes: iterable of {id, name}. Returns {id: {"n": [ingredient names], "s": cookbook slug}} for those found."""
    try:
        slugs = id_to_slug()
    except Exception as exc:  # noqa: BLE001
        print(f"cookbook index unavailable ({exc}); falling back to name-based slugs")
        slugs = {}
    todo = {r["id"]: (r["id"], r["name"], slugs.get(r["id"])) for r in recipes}
    with ThreadPoolExecutor(WORKERS) as ex:
        results = list(ex.map(_one, todo.values()))
    return {rid: {"n": names, "s": slug} for rid, names, slug in results if names}
