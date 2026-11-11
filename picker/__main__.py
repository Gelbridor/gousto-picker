"""python -m picker  ->  docs/data/shortlist.json (+ printed top 8)"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .fetch import fetch_menus
from .profile import learn
from .rank import load_config, rank

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "shortlist.json"


def build_week(menu, cfg):
    recipes = list(menu["recipes"].values())
    items = rank(recipes, cfg)
    shortlist = [i for i in items if not i["vegan"] and not i["premium"]]
    return {
        "period": menu["period"],
        "counts": {"feed": len(recipes), "eligible": len(shortlist)},
        "top": shortlist[: cfg["top_n"]],
        "all": items,
    }


def main():
    cfg = load_config()
    menus, source = fetch_menus(cfg.get("weeks", 3))
    weeks = [build_week(m, cfg) for m in menus]
    seen, pool = set(), []
    for w in weeks:  # unique non-vegan, non-premium recipes across the weeks = what the menu "offers"
        for i in w["all"]:
            if not i["vegan"] and not i["premium"] and i["name"] not in seen:
                seen.add(i["name"])
                pool.append(i)
    profile = learn(pool)
    if not weeks or not weeks[0]["top"]:
        sys.exit("No eligible recipes found - the feed format may have changed")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "config": cfg,
        "weeks": weeks,
        "profile": profile,
        **{k: weeks[0][k] for k in ("period", "counts", "top", "all")},  # current week, for older pages
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))
    for w in weeks:
        pd = w["period"]
        print(f"\n=== Menu {pd['when_start'][:10]} -> {pd['when_cutoff'][:10]} ({source}): "
              f"{w['counts']['feed']} in feed, {w['counts']['eligible']} eligible ===")
        for n, it in enumerate(w["top"], 1):
            print(f"{n}. {it['name']}  |  {it['cook_time']} min  |  {it['calories']} kcal  |  {it['score']}\n   {it['why']}")


if __name__ == "__main__":
    main()
