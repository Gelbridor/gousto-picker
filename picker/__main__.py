"""python -m picker  ->  docs/data/shortlist.json (+ printed top 8)"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .fetch import fetch_menu_for, fetch_menus, fetch_versions, upcoming_dates
from .ingredients import fetch_ingredients
from .profile import learn, load_history
from .rank import eligible, key, load_config, menu_items, personalise
from .versions import choose, group

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "shortlist.json"
ING_OUT = OUT.with_name("ingredients.json")


def week_items(menus, labels, cfg):
    """All recipes across the week's menu versions. A recipe missing from some versions gets "menus": [labels it's on]."""
    raw = {}
    for m in menus:
        for rid, r in m["recipes"].items():
            raw.setdefault(rid, r)
    items = menu_items(list(raw.values()), cfg)
    if len(menus) > 1:
        on = {lab: {key(r["name"]) for r in m["recipes"].values()} for lab, m in zip(labels, menus)}
        for it in items:
            have = [lab for lab in labels if key(it["name"]) in on[lab]]
            if len(have) < len(labels):
                it["menus"] = have
    return items


def on_menu(item, mine):
    return mine is None or "menus" not in item or mine in item["menus"]


def build_week(menus, labels, mine, cfg, profile, history):
    items = week_items(menus, labels, cfg)
    period = menus[0]["period"]
    yours = menus[labels.index(mine)] if mine else menus[0]
    shortlist = personalise([i for i in items if eligible(i) and on_menu(i, mine)], profile, history, period["when_start"], cfg)
    return {
        "period": period,
        "counts": {"feed": len(yours["recipes"]), "eligible": len(shortlist)},
        "top": shortlist[: cfg["top_n"]],
        "all": sorted(items, key=lambda i: i["score"], reverse=True),
    }


def fetch_weeks(cfg, history):
    """Upcoming menus, one list of version menus per week, plus which version is yours.
    Returns (weeks, labels, version_info, device_for_your_version, source)."""
    try:
        dates = upcoming_dates(cfg.get("weeks", 3))
        recent = [d for d in sorted({h["week"] for h in history})[-4:] if d not in dates]
        by_date = fetch_versions(dates + recent)
        versions = group(by_date)
        if versions:
            info = choose(versions, history)
            mine = next(v for v in versions if v["label"] == info["mine"])
            print(f"Gousto is showing {len(versions)} versions of the menu; yours looks like version {info['mine']} "
                  f"(past picks on each version: {info['match']}, from {info['checked']} picks in test weeks)", flush=True)
            return [[v["menus"][d] for v in versions] for d in dates], info["labels"], info, mine["devices"][0], "api"
        weeks = [[next(iter(by_date[d].values()))] for d in dates if by_date.get(d)]
        if len(weeks) == len(dates):
            return weeks, [], None, None, "api"
        print("Some menus did not load; retrying the simple way", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"Menu versions unavailable ({exc}); using a single menu", flush=True)
    menus, source = fetch_menus(cfg.get("weeks", 3))
    return [[m] for m in menus], [], None, None, source


def past_menus(history, cfg, device=None, budget=90):
    """Eligible recipes on the menu each past pick was chosen from, so taste is judged against what was on offer.
    Fetched in daemon threads with one overall time limit: a slow or stuck request can't hold up the weekly build,
    and any week not fetched in time falls back to the current menu mix."""
    import threading
    import time

    weeks = sorted({h["week"] for h in history})[-52:]
    raw = {}

    def get(week):
        try:
            raw[week] = fetch_menu_for(week, device)
        except Exception as exc:  # noqa: BLE001
            print(f"Could not fetch the {week} menu ({exc}); using the current menu mix for those picks", flush=True)

    threads = [threading.Thread(target=get, args=(w,), daemon=True) for w in weeks]
    for t in threads:
        t.start()
    deadline = time.monotonic() + budget
    for t in threads:
        t.join(max(0, deadline - time.monotonic()))
    late = [w for w in weeks if w not in raw]
    if late:
        print(f"Past menus not available for {', '.join(late)}; using the current menu mix for those picks", flush=True)
    return {w: [i for i in menu_items(list(m["recipes"].values()), cfg) if eligible(i)] for w, m in dict(raw).items()}


def write_ingredients(weeks):
    """Ingredient lists for every recipe on the menus, so the page can hide recipes with ingredients you avoid."""
    from collections import Counter

    recipes = {i["id"]: {"id": i["id"], "name": i["name"]} for w in weeks for i in w["all"]}
    found = fetch_ingredients(recipes.values())
    names = sorted({n for v in found.values() for n in v["n"]})
    index = {n: k for k, n in enumerate(names)}
    freq = Counter(n for v in found.values() for n in v["n"])
    ING_OUT.write_text(json.dumps({
        "names": names,
        "recipes": {rid: [index[n] for n in v["n"]] for rid, v in found.items()},
        "slugs": {rid: v["s"] for rid, v in found.items()},   # cookbook page slug: gousto.co.uk/cookbook/recipes/<slug>
        "common": [n for n, c in freq.most_common(250) if c >= 3],
    }, separators=(",", ":")))
    print(f"\nIngredient lists found for {len(found)} of {len(recipes)} recipes")


def main():
    cfg = load_config()
    history = load_history()
    print("Fetching the upcoming menus (every version Gousto is testing)", flush=True)
    upcoming, labels, versions, device, source = fetch_weeks(cfg, history)
    mine = versions["mine"] if versions else None
    print(f"Got {len(upcoming)} weeks via {source}; fetching past menus for your picks", flush=True)
    seen, pool = set(), []
    for menus in upcoming:  # unique non-vegan, non-premium recipes on your menus = what the menu "offers" now
        for i in week_items(menus, labels, cfg):
            if eligible(i) and on_menu(i, mine) and i["name"] not in seen:
                seen.add(i["name"])
                pool.append(i)
    profile = learn(history, pool, past_menus(history, cfg, device), cfg["learning"])
    print(f"Learned from {len(history)} picks ({profile['menus_matched']} compared with the menu they were chosen from)")
    weeks = [build_week(m, labels, mine, cfg, profile, history) for m in upcoming]
    if not weeks or not weeks[0]["top"]:
        sys.exit("No eligible recipes found - the feed format may have changed")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "config": cfg,
        "weeks": weeks,
        "profile": profile,
        "menu_versions": versions,   # None, or {labels, mine, match, checked, sure}; recipes carry "menus" when not on all
        "history": history,   # [{name, week}] from picks.json, for the page's "picked before" bonus
        **{k: weeks[0][k] for k in ("period", "counts", "top", "all")},  # current week, for older pages
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print("Fetching ingredient lists", flush=True)
    try:
        write_ingredients(weeks)
    except Exception as exc:  # noqa: BLE001 - the shortlist still works without ingredient data
        print(f"Could not fetch ingredient lists: {exc}")
    OUT.write_text(json.dumps(payload, indent=1))
    for w in weeks:
        pd = w["period"]
        print(f"\n=== Menu {pd['when_start'][:10]} -> {pd['when_cutoff'][:10]} ({source}): "
              f"{w['counts']['feed']} in feed, {w['counts']['eligible']} eligible ===")
        for n, it in enumerate(w["top"], 1):
            print(f"{n}. {it['name']}  |  {it['cook_time']} min  |  {it['calories']} kcal  |  {it['final']} (base {it['score']}, tags {it['tag_bonus']:+}, repeat {it['repeat_bonus']:+})\n   {it['why']}")


if __name__ == "__main__":
    main()
