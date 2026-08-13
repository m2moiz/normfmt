#!/usr/bin/env python3
"""Wire normfmt into VS Code's format-on-save.

Adds an `emeraldwalk.runonsave` rule for .c/.h to the user settings of every
editor it finds. The settings file is backed up first, and if it cannot be
parsed it is left completely alone and the snippet is printed instead — a
broken settings.json is a much worse outcome than a manual paste.

    python3 vscode_setup.py [--print] [--remove]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from typing import Optional

KEY = "emeraldwalk.runonsave"
RULE = {"match": r"\.(c|h)$", "cmd": '$HOME/.local/bin/normfmt "${file}"'}

SUPPORT = os.path.expanduser("~/Library/Application Support")
EDITORS = {
    "VS Code": os.path.join(SUPPORT, "Code/User/settings.json"),
    "VS Code Insiders": os.path.join(SUPPORT, "Code - Insiders/User/settings.json"),
    "Cursor": os.path.join(SUPPORT, "Cursor/User/settings.json"),
    "VSCodium": os.path.join(SUPPORT, "VSCodium/User/settings.json"),
    "Windsurf": os.path.join(SUPPORT, "Windsurf/User/settings.json"),
}

# Linux paths, for a campus that is not on macOS.
CONFIG = os.path.expanduser("~/.config")
EDITORS.update(
    {
        "VS Code (linux)": os.path.join(CONFIG, "Code/User/settings.json"),
        "Cursor (linux)": os.path.join(CONFIG, "Cursor/User/settings.json"),
    }
)


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas, ignoring those inside strings."""
    out = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load(path: str) -> Optional[dict]:
    """Parsed settings, {} if the file is absent, None if it cannot be parsed."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        raw = f.read()
    if not raw.strip():
        return {}
    try:
        value = json.loads(strip_jsonc(raw))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def apply(settings: dict, remove: bool) -> bool:
    """Add or drop our rule. True if anything changed."""
    block = settings.get(KEY)
    if not isinstance(block, dict):
        block = {}
    commands = [c for c in block.get("commands", []) if isinstance(c, dict)]
    ours = [c for c in commands if c.get("match") == RULE["match"]]

    if remove:
        if not ours:
            return False
        commands = [c for c in commands if c.get("match") != RULE["match"]]
        if commands:
            block["commands"] = commands
            settings[KEY] = block
        else:
            settings.pop(KEY, None)
        return True

    if ours and ours[0].get("cmd") == RULE["cmd"]:
        return False
    commands = [c for c in commands if c.get("match") != RULE["match"]]
    commands.append(dict(RULE))
    block["commands"] = commands
    settings[KEY] = block
    return True


def snippet() -> str:
    return json.dumps({KEY: {"commands": [RULE]}}, indent=2)


def main(argv: list[str]) -> int:
    remove = "--remove" in argv

    if "--print" in argv:
        print(snippet())
        return 0

    found = 0
    for name, path in EDITORS.items():
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            continue
        found += 1

        settings = load(path)
        if settings is None:
            print(f"    {name}: settings.json could not be parsed — not touching it.")
            print(f"    add this yourself ({path}):")
            print("      " + snippet().replace("\n", "\n      "))
            continue

        if not apply(settings, remove):
            print(f"    {name}: already up to date")
            continue

        if os.path.exists(path):
            shutil.copy2(path, path + ".normfmt.bak")
        os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")
        action = "removed from" if remove else "added to"
        print(f"    {name}: rule {action} {path}")
        if os.path.exists(path + ".normfmt.bak"):
            print("      backup: settings.json.normfmt.bak "
                  "(rewriting drops any // comments you had)")

    if not found:
        print("    no VS Code installation found — skipping")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
