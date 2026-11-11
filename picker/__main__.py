"""python -m picker  ->  docs/data/shortlist.json (+ printed top 8)"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .fetch import fetch_menu
from .rank import load_config, rank

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "shortlist.json"


def main():
    cfg = load_config()
    menu, source = fetch_menu()
    recipes = list(menu["recipes"].values())
    items = rank(recipes, cfg)
    if not items:
        sys.exit("No eligible recipes found - the feed format may have changed")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "period": menu["period"],
        "config": cfg,
        "counts": {"feed": len(recipes), "eligible": len(items)},
        "top": items[: cfg["top_n"]],
        "all": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))
    print(f"Menu {menu['period']['when_start'][:10]} -> {menu['period']['when_cutoff'][:10]} "
          f"({source}); {len(recipes)} in feed, {len(items)} eligible\n")
    for n, it in enumerate(payload["top"], 1):
        print(f"{n}. {it['name']}  |  {it['cook_time']} min  |  {it['calories']} kcal  |  {it['score']}\n   {it['why']}")


if __name__ == "__main__":
    main()
