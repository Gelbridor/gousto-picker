"""python -m picker  ->  docs/data/shortlist.json (+ printed top 8)"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .fetch import fetch_menu_for, fetch_menus
from .ingredients import fetch_ingredients
from .profile import learn, load_history
from .rank import eligible, load_config, menu_items, personalise

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "shortlist.json"
ING_OUT = OUT.with_name("ingredients.json")


def build_week(menu, cfg, profile, history):
    recipes = list(menu["recipes"].values())
    items = menu_items(recipes, cfg)
    shortlist = personalise([i for i in items if eligible(i)], profile, history, menu["period"]["when_start"], cfg)
    return {
        "period": menu["period"],
        "counts": {"feed": len(recipes), "eligible": len(shortlist)},
        "top": shortlist[: cfg["top_n"]],
        "all": sorted(items, key=lambda i: i["score"], reverse=True),
    }


def past_menus(history, cfg):
    """Eligible recipes on the menu each past pick was chosen from, so taste is judged against what was on offer."""
    out = {}
    for week in sorted({h["week"] for h in history})[-52:]:
        try:
            out[week] = [i for i in menu_items(list(fetch_menu_for(week)["recipes"].values()), cfg) if eligible(i)]
        except Exception as exc:  # noqa: BLE001 - fall back to the current menu mix for that week
            print(f"Could not fetch the {week} menu ({exc}); using the current menu mix for those picks")
    return out


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
    menus, source = fetch_menus(cfg.get("weeks", 3))
    seen, pool = set(), []
    for m in menus:  # unique non-vegan, non-premium recipes across the weeks = what the menu "offers" now
        for i in menu_items(list(m["recipes"].values()), cfg):
            if eligible(i) and i["name"] not in seen:
                seen.add(i["name"])
                pool.append(i)
    history = load_history()
    profile = learn(history, pool, past_menus(history, cfg), cfg["learning"])
    print(f"Learned from {len(history)} picks ({profile['menus_matched']} compared with the menu they were chosen from)")
    weeks = [build_week(m, cfg, profile, history) for m in menus]
    if not weeks or not weeks[0]["top"]:
        sys.exit("No eligible recipes found - the feed format may have changed")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "config": cfg,
        "weeks": weeks,
        "profile": profile,
        "history": history,   # [{name, week}] from picks.json, for the page's "picked before" bonus
        **{k: weeks[0][k] for k in ("period", "counts", "top", "all")},  # current week, for older pages
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
