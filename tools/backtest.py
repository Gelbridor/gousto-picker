"""Back-test the ranking against real picks: for each week in picks.json, score that week's menu using only the
picks made BEFORE it, then report where the recipes you actually chose landed.

    python tools/backtest.py            # current config.json
    python tools/backtest.py --sweep    # also try a few weight / bonus variations

Past menus are cached in .cache/menus so repeat runs don't refetch.
"""
import copy
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from picker.fetch import fetch_menu_for  # noqa: E402
from picker.profile import learn, load_history  # noqa: E402
from picker.rank import eligible, key, load_config, menu_items, personalise  # noqa: E402

CACHE = ROOT / ".cache" / "menus"


def menu(week):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{week}.json"
    if not f.exists():
        f.write_text(json.dumps(fetch_menu_for(week)))
    return json.loads(f.read_text())


def evaluate(cfg, history, raw, variety=True):
    weeks = sorted({h["week"] for h in history})
    all_items = {w: menu_items(list(raw[w]["recipes"].values()), cfg) for w in weeks}
    menus = {w: [i for i in all_items[w] if eligible(i)] for w in weeks}
    ranks, missing = [], []
    for w in weeks:
        before = [h for h in history if h["week"] < w]
        items = copy.deepcopy(menus[w])
        profile = learn(before, items, {x: menus[x] for x in weeks if x < w}, cfg["learning"])
        ranked = personalise(items, profile, before, raw[w]["period"]["when_start"], cfg, variety)
        pos = {key(i["name"]): k + 1 for k, i in enumerate(ranked)}
        premium = {key(i["name"]) for i in all_items[w] if i["premium"]}
        for h in history:
            if h["week"] != w:
                continue
            k = key(h["name"])
            if k in pos:
                ranks.append((w, pos[k], len(ranked), h["name"]))
            else:
                missing.append((w, h["name"], "premium, hidden by default" if k in premium else "not on that menu"))
    return ranks, missing


def evaluate_legacy(cfg, history, raw):
    """The ranking as it was before Nov 2026: min-max scaling over the whole menu, 50/20/15/15 weights,
    uncapped tag bonuses (up to +/-16 each) against the current menu mix, no repeat bonus, no variety."""
    import math
    from collections import Counter
    from picker.tags import tag
    weeks = sorted({h["week"] for h in history})
    ranks = []
    for w in weeks:
        items = menu_items(list(raw[w]["recipes"].values()), cfg)
        def mm(v, lo, hi, inv=False):
            x = 0.5 if hi == lo else max(0, min(1, (v - lo) / (hi - lo)))
            return 1 - x if inv else x
        rng = {k: (min(i[k] for i in items), max(i[k] for i in items)) for k in ("bayes_rating", "calories", "cook_time")}
        pr = [i["protein_g"] / max(i["calories"], 1) for i in items]
        for i, d in zip(items, pr):
            i["old"] = 100 * (.5 * mm(i["bayes_rating"], *rng["bayes_rating"]) + .2 * mm(d, min(pr), max(pr))
                              + .15 * mm(i["calories"], *rng["calories"], True) + .15 * mm(i["cook_time"], *rng["cook_time"], True))
        pool = [i for i in items if eligible(i)]
        before = [h for h in history if h["week"] < w]
        bonus = {}
        for k, dim in enumerate(("main", "style", "dish")):
            menu = Counter(i[dim] for i in pool)
            picked = Counter(tag(h["name"])[k] for h in before)
            for v, c in menu.items():
                share = c / len(pool)
                p = (picked.get(v, 0) + 20 * share) / (len(before) + 20)
                bonus[(dim, v)] = max(-16, min(16, round(8 * math.log2(p / share)))) if before else 0
        ranked = sorted(pool, key=lambda i: -(i["old"] + sum(bonus[(d, i[d])] for d in ("main", "style", "dish"))))
        pos = {key(i["name"]): k + 1 for k, i in enumerate(ranked)}
        ranks += [(w, pos[key(h["name"])], len(ranked), h["name"]) for h in history if h["week"] == w and key(h["name"]) in pos]
    return ranks


def summary(ranks, n):
    r = [x[1] for x in ranks]
    return {"picks": len(r), f"in_top_{n}": sum(x <= n for x in r), "in_top_16": sum(x <= 16 for x in r),
            "median_rank": st.median(r), "mean_recip_rank": round(st.mean(1 / x for x in r), 3)}


def main():
    cfg = load_config()
    history = load_history()
    raw = {w: menu(w) for w in sorted({h["week"] for h in history})}
    ranks, missing = evaluate(cfg, history, raw)
    for w, k, total, name in ranks:
        print(f"{w}  #{k:>3} of {total}  {name}")
    for w, name, why in missing:
        print(f"{w}  not ranked ({why}): {name}")
    print("\nOld algorithm: ", summary(evaluate_legacy(cfg, history, raw), cfg["top_n"]))
    print("Current config:", summary(ranks, cfg["top_n"]))
    if "--sweep" not in sys.argv:
        return
    variants = {
        "no variety": (cfg, False),
        "no history at all": ({**cfg, "learning": {**cfg["learning"], "tag_cap": 0, "repeat_max": 0}}, True),
        "no repeat bonus": ({**cfg, "learning": {**cfg["learning"], "repeat_max": 0}}, True),
        "no tag bonus": ({**cfg, "learning": {**cfg["learning"], "tag_cap": 0}}, True),
        "old weights 50/20/15/15": ({**cfg, "weights": {"rating": .5, "protein": .2, "calories": .15, "time": .15}}, True),
        "rating only": ({**cfg, "weights": {"rating": 1, "protein": 0, "calories": 0, "time": 0}}, True),
        "rating 80 / time 20": ({**cfg, "weights": {"rating": .8, "protein": 0, "calories": 0, "time": .2}}, True),
        "rating 60 / protein 20 / time 20": ({**cfg, "weights": {"rating": .6, "protein": .2, "calories": 0, "time": .2}}, True),
        "bigger repeat (30, max 40)": ({**cfg, "learning": {**cfg["learning"], "repeat_points": 30, "repeat_max": 40}}, True),
        "smaller tag cap (12)": ({**cfg, "learning": {**cfg["learning"], "tag_cap": 12}}, True),
        "bigger tag cap (30)": ({**cfg, "learning": {**cfg["learning"], "tag_cap": 30, "tag_limit": 16}}, True),
    }
    for name, (c, v) in variants.items():
        print(f"{name:34}", summary(evaluate(c, history, raw, v)[0], cfg["top_n"]))


if __name__ == "__main__":
    main()
