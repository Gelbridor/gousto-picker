"""Turn docs/index.html into the body-only page the Claude Artifact tool publishes.

Usage: python tools/make_artifact.py OUTPUT.html
The artifact is published together with docs/data/shortlist.json and docs/data/ingredients.json,
with capabilities {db: {rules: [...]}, user: {}} so two people can share preferences and votes.
"""
import re
import sys
from pathlib import Path

src = (Path(__file__).resolve().parent.parent / "docs" / "index.html").read_text()
head = re.search(r"<head>(.*?)</head>", src, re.S).group(1)
body = re.search(r"<body>(.*)</body>", src, re.S).group(1)
head = re.sub(r"<meta charset[^>]*>\s*|<meta name=\"viewport\"[^>]*>\s*", "", head)
page = head.strip().replace("<title>", '<meta name="claude:viewport-fit-sides" content="cover">\n<title>', 1)
# keep <title> first in the file
title = re.search(r"<title>.*?</title>", page).group(0)
page = page.replace(title, "").strip()
Path(sys.argv[1]).write_text(f"{title}\n{page}\n{body.strip()}\n")
