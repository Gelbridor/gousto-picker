"""Gousto runs several versions of the menu at once (an A/B test) and each customer only sees one.

We look at the menus a handful of fixed test visitors get, group visitors who get the same menu every week
into versions A, B, ..., then work out which version is yours from your past picks: your picks are all on your
version's menu but not always on the others. The page can override this, and also uses picks entered on the site.
"""
from collections import defaultdict

from .rank import key


def group(by_date):
    """by_date: {date: {device: menu}} -> [{"label", "devices", "menus": {date: menu}}], or [] if every
    visitor saw the same menus. Visitors missing any date are left out."""
    dates = sorted(by_date)
    devices = [d for d in next(iter(by_date.values()), {}) if all(d in by_date[x] for x in dates)]
    sigs = defaultdict(list)
    for dev in devices:
        sigs[tuple(by_date[x][dev]["id"] for x in dates)].append(dev)
    if len(sigs) < 2:
        return []
    ordered = sorted(sigs.values(), key=lambda devs: min(devices.index(d) for d in devs))  # stable labels
    return [{"label": chr(65 + n), "devices": devs, "menus": {x: by_date[x][devs[0]] for x in dates}}
            for n, devs in enumerate(ordered)]


def match(versions, history):
    """How many past picks are on each version's menu for the week they were picked. Only weeks where the
    versions differ tell us anything, so those are the only picks counted."""
    score, checked = {v["label"]: 0 for v in versions}, 0
    for h in history:
        menus = [v["menus"].get(h["week"]) for v in versions]
        if any(m is None for m in menus) or len({m["id"] for m in menus}) < 2:
            continue
        checked += 1
        for v, m in zip(versions, menus):
            score[v["label"]] += key(h["name"]) in {key(r["name"]) for r in m["recipes"].values()}
    return score, checked


def choose(versions, history):
    score, checked = match(versions, history)
    best = max(score.values()) if score else 0
    leaders = [k for k, s in score.items() if s == best]
    mine = leaders[0] if leaders else "A"
    return {"labels": [v["label"] for v in versions], "mine": mine, "match": score, "checked": checked,
            "sure": checked > 0 and len(leaders) == 1}
