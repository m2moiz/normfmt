#!/usr/bin/env python3
"""Keep the web guide and the READMEs from drifting apart.

docs/guide.html and the two READMEs say the same things in two formats. They
are maintained by hand, so this checks that every sentence in the guide still
appears in the README for that language.

The check runs one way only. The READMEs carry extra material the page does not
(the fixer table, the repo layout, credits), and that is deliberate.

    python3 tools/tests/test_docs.py
"""

from __future__ import annotations

import html
import os
import re
import sys
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUIDE = os.path.join(ROOT, "docs", "guide.html")
READMES = {
    "en": os.path.join(ROOT, "README.md"),
    "fr": os.path.join(ROOT, "README.fr.md"),
}

# Sentences the guide states as prose and the README states as a table row or a
# heading. The words differ by design, so comparing them is not meaningful.
# Each entry needs a reason; an exemption without one is just a hidden failure.
EXEMPT = {
    "~/.42tools/ holds the virtualenv":
        "README renders this as the 'Where did it put everything' table",
    "~/.42tools/ contient le virtualenv":
        "README renders this as the 'Il a mis quoi, et où ?' table",
    "clone it, run one command":
        "step heading on the page, plain prose in the README",
    "clone, puis une seule commande":
        "step heading on the page, plain prose in the README",
    "check your login":
        "step heading on the page, plain prose in the README",
    "vérifie ton login":
        "step heading on the page, plain prose in the README",
    "vs code needs one extension":
        "step heading on the page, bolded lead-in in the README",
    "vs code a besoin d'une extension":
        "step heading on the page, bolded lead-in in the README",
}

# The shortest prefix we require to match. Long enough that a coincidence is
# implausible, short enough to survive a reworded clause at the end.
PROBE = 55


def normalise(text: str) -> str:
    """Reduce markdown and HTML to comparable plain text."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)   # markdown links
    text = text.replace("`", "").replace("*", "").replace("_", "")
    text = text.replace(" ", " ").replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    # Stripping a tag leaves a space behind, so `<code>$USER</code>,` becomes
    # "$USER ,". Pull punctuation back onto the word.
    text = re.sub(r"\s+([,.;:!?)])(?=\s|$)", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text.strip().lower()


def guide_blocks() -> Dict[str, List[str]]:
    with open(GUIDE) as f:
        src = f.read()
    src = re.sub(r"<style>.*?</style>", "", src, flags=re.S)
    src = re.sub(r"<script>.*?</script>", "", src, flags=re.S)
    src = re.sub(r"<pre.*?</pre>", "", src, flags=re.S)   # code, compared by eye

    out: Dict[str, List[str]] = {"en": [], "fr": []}
    for m in re.finditer(r"<(p|h3|td)([^>]*)>(.*?)</\1>", src, flags=re.S):
        lang = re.search(r'data-lang="(\w+)"', m.group(2))
        if not lang:
            continue                                       # shared cell, no prose
        text = normalise(m.group(3))
        if len(text) > 25:
            out[lang.group(1)].append(text)
    return out


def main() -> int:
    if not os.path.exists(GUIDE):
        print(f"FAIL  {GUIDE} is missing")
        return 1

    blocks = guide_blocks()
    failures = 0
    exempted = 0

    for lang, path in READMES.items():
        with open(path) as f:
            raw = f.read()
        # Drop fenced code blocks, the same way <pre> is dropped from the guide.
        # A sentence the page writes straight through is often split around a
        # code block in the README, and only then do the two read the same.
        raw = re.sub(r"```.*?```", " ", raw, flags=re.S)
        readme = normalise(raw)

        for block in blocks[lang]:
            probe = block[:PROBE]
            reason = next((r for k, r in EXEMPT.items() if block.startswith(k)), None)
            if reason:
                exempted += 1
                continue
            if probe not in readme:
                failures += 1
                print(f"FAIL  [{lang}] in the guide but not in {os.path.basename(path)}:")
                print(f"        {block[:110]}")

        print(f"ok    [{lang}] {len(blocks[lang])} guide blocks checked "
              f"against {os.path.basename(path)}")

    if exempted:
        print(f"\n{exempted} block(s) exempted, by name and with a reason, in EXEMPT")

    if failures:
        print(f"\n{failures} failed — update the README, or the guide, so they agree")
        return 1
    print("\nguide and READMEs agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
