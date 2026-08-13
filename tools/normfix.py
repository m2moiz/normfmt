#!/usr/bin/env python3
"""normfix — close the gap between c_formatter_42 and norminette.

c_formatter_42 reshapes whitespace but leaves a set of purely structural Norm
errors untouched. Rather than reimplementing a C parser to find them, normfix
asks norminette where they are, applies a targeted fix at that exact line, and
repeats until nothing fixable remains.

    run norminette -> parse "Error: CODE (line: N, col: M)"
                   -> apply FIXERS[CODE] at line N, bottom-up
                   -> re-run c_formatter_42 to re-align
                   -> repeat until fixpoint

Adding support for a new error is adding one entry to FIXERS.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Callable, Dict, List, NamedTuple

MAX_ROUNDS = 12

ERROR_RE = re.compile(
    r"^(?:Error|Notice):\s+(?P<code>[A-Z_0-9]+)\s+\(line:\s*(?P<line>\d+),"
    r"\s*col:\s*(?P<col>\d+)\)"
)

# Type keywords that may precede the actual type name in a declaration.
TYPE_PREFIX = r"(?:(?:const|static|volatile|register|unsigned|signed|struct|union|enum|long|short)\s+)*"
DECL_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?P<type>" + TYPE_PREFIX + r"[A-Za-z_]\w*)"
    r"(?P<sep>[ \t]+|(?=[ \t]*\*))"
    r"(?P<rest>[^;]*);"
    r"(?P<trail>[ \t]*(?:/\*.*\*/|//.*)?)[ \t]*$"
)


class Error(NamedTuple):
    code: str
    line: int  # 1-indexed
    col: int


def run(cmd: List[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def norminette(path: str) -> List[Error]:
    proc = run(["norminette", path])
    out = []
    for raw in (proc.stdout + proc.stderr).splitlines():
        m = ERROR_RE.match(raw.strip())
        if m:
            out.append(Error(m["code"], int(m["line"]), int(m["col"])))
    return out


def clang_pass(path: str) -> None:
    """Re-run c_formatter_42 so newly inserted lines get aligned and tabbed."""
    run(["c_formatter_42", path])


# --------------------------------------------------------------------------
# Fixers. Each takes (lines, error) and mutates `lines` in place.
# `lines` holds no trailing newlines. Return True if something changed.
# --------------------------------------------------------------------------


def fix_mult_decl(lines: List[str], err: Error) -> bool:
    """int a, b;  ->  int a;<nl>int b;"""
    i = err.line - 1
    if not (0 <= i < len(lines)):
        return False
    m = DECL_RE.match(lines[i])
    if not m:
        return False
    rest = m["rest"]
    # Function pointers and prototypes: leave them alone.
    if "(" in rest:
        return False
    decls = [d.strip() for d in split_top_level_char(rest, ",")]
    if len(decls) < 2 or not all(decls):
        return False
    indent, type_ = m["indent"], m["type"]
    new = [f"{indent}{type_}\t{d};" for d in decls]
    # Keep any trailing comment attached to the first declaration.
    if m["trail"].strip():
        new[0] += " " + m["trail"].strip()
    lines[i:i + 1] = new
    return True


def fix_insert_blank_before(lines: List[str], err: Error) -> bool:
    """NL_AFTER_VAR_DECL / NEWLINE_PRECEDES_FUNC: both want a blank line here."""
    i = err.line - 1
    if not (0 < i <= len(lines)):
        return False
    if lines[i - 1].strip() == "":
        return False
    lines.insert(i, "")
    return True


def fix_delete_line(lines: List[str], err: Error) -> bool:
    """CONSECUTIVE_NEWLINES / EMPTY_LINE_* : drop the offending blank line."""
    i = err.line - 1
    if not (0 <= i < len(lines)) or lines[i].strip() != "":
        return False
    del lines[i]
    return True


CONTROL_RE = re.compile(r"^[ \t]*(if|else|while|for|switch|do|return)\b")


def split_top_level_char(text: str, sep: str) -> List[str]:
    """Split on `sep` outside of (), [], {}, string and char literals."""
    parts, depth, buf = [], 0, ""
    quote = None
    escaped = False
    for ch in text:
        if quote:
            buf += ch
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf += ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return parts


def fix_many_instr(lines: List[str], err: Error) -> bool:
    """a = 1; b = 2;  ->  one statement per line."""
    i = err.line - 1
    if not (0 <= i < len(lines)):
        return False
    line = lines[i]
    if CONTROL_RE.match(line) or "{" in line or "}" in line:
        return False
    indent = line[: len(line) - len(line.lstrip(" \t"))]
    stmts = [s.strip() for s in split_top_level_char(line, ";")]
    if stmts and stmts[-1] == "":
        stmts.pop()
    if len(stmts) < 2 or not all(stmts):
        return False
    lines[i:i + 1] = [f"{indent}{s};" for s in stmts]
    return True


def fix_mult_assign(lines: List[str], err: Error) -> bool:
    """a = x, b = y;  ->  one assignment per line (the comma is a sequence point)."""
    i = err.line - 1
    if not (0 <= i < len(lines)):
        return False
    line = lines[i]
    if CONTROL_RE.match(line) or "{" in line or "}" in line:
        return False
    m = re.match(r"^(?P<indent>[ \t]*)(?P<body>.*);[ \t]*$", line)
    if not m:
        return False
    parts = [p.strip() for p in split_top_level_char(m["body"], ",")]
    if len(parts) < 2 or not all("=" in p for p in parts):
        return False
    lines[i:i + 1] = [f"{m['indent']}{p};" for p in parts]
    return True


def in_literal(line: str, index: int) -> bool:
    """Is `index` inside a string or char literal?"""
    quote = None
    escaped = False
    for i, ch in enumerate(line):
        if i == index:
            return quote is not None
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
    return False


TAB_WIDTH = 4


def col_to_index(line: str, col: int) -> int:
    """norminette reports a *visual* column, where a tab spans to the next
    multiple of TAB_WIDTH. Convert it to a character index."""
    visual = 1
    for index, ch in enumerate(line):
        if visual >= col:
            return index
        visual = (visual + TAB_WIDTH - 1) // TAB_WIDTH * TAB_WIDTH + 1 if ch == "\t" else visual + 1
    return len(line)


def fix_space_to_tab(lines: List[str], err: Error) -> bool:
    """SPACE_REPLACE_TAB: the run of spaces at this column should be one tab.

    c_formatter_42's align pass leaves these behind on declarators it does not
    recognise, e.g. `int tab[5];`.
    """
    i = err.line - 1
    if not (0 <= i < len(lines)):
        return False
    line = lines[i]
    j = col_to_index(line, err.col)
    if not (0 <= j < len(line)) or line[j] != " " or in_literal(line, j):
        return False
    end = j
    while end < len(line) and line[end] == " ":
        end += 1
    lines[i] = line[:j] + "\t" + line[end:]
    return True


def fix_strip_trailing(lines: List[str], err: Error) -> bool:
    """SPACE_EMPTY_LINE / SPC_BEFORE_NL: trailing whitespace."""
    i = err.line - 1
    if not (0 <= i < len(lines)):
        return False
    stripped = lines[i].rstrip()
    if stripped == lines[i]:
        return False
    lines[i] = stripped
    return True


FIXERS: Dict[str, Callable[[List[str], Error], bool]] = {
    "MULT_DECL_LINE": fix_mult_decl,
    "MULT_ASSIGN_LINE": fix_mult_assign,
    "TOO_MANY_INSTR": fix_many_instr,
    "NL_AFTER_VAR_DECL": fix_insert_blank_before,
    "NEWLINE_PRECEDES_FUNC": fix_insert_blank_before,
    "CONSECUTIVE_NEWLINES": fix_delete_line,
    "EMPTY_LINE_FUNCTION": fix_delete_line,
    "EMPTY_LINE_FILE_START": fix_delete_line,
    "EMPTY_LINE_EOF": fix_delete_line,
    "SPACE_EMPTY_LINE": fix_strip_trailing,
    "SPC_BEFORE_NL": fix_strip_trailing,
    "SPACE_REPLACE_TAB": fix_space_to_tab,
}

# Several errors can land on the same line. Structural edits (splitting a
# declaration, inserting a blank line) must win over cosmetic ones, otherwise
# the cosmetic fix claims the line and the real problem never gets addressed.
PRIORITY = {
    "SPACE_REPLACE_TAB": 1,
    "SPACE_EMPTY_LINE": 1,
    "SPC_BEFORE_NL": 1,
}

# Errors that require a decision about the program, not about its layout.
# Listed so `normfmt` can explain why it is not touching them.
UNFIXABLE = {
    "TOO_MANY_LINES": "split the function yourself",
    "TOO_MANY_FUNCS": "move a function to another file",
    "TOO_MANY_VARS_FUNC": "fewer variables, or split the function",
    "TOO_MANY_ARGS": "pass a struct, or split the function",
    "FORBIDDEN_CS": "rewrite the for/switch/do-while as a while",
    "GOTO_FBIDDEN": "restructure the control flow",
    "LABEL_FBIDDEN": "restructure the control flow",
    "TERNARY_FBIDDEN": "rewrite as if/else",
    "ASSIGN_IN_CONTROL": "move the assignment out of the condition",
    "VLA_FORBIDDEN": "use malloc or a fixed size",
    "MACRO_FUNC_FORBIDDEN": "write a real function",
    "FORBIDDEN_TYPEDEF": "move the typedef to a .h",
    "FORBIDDEN_STRUCT": "move the struct to a .h",
    "FORBIDDEN_UNION": "move the union to a .h",
    "FORBIDDEN_ENUM": "move the enum to a .h",
    "INCLUDE_HEADER_ONLY": "include a .h, not a .c",
    "GLOBAL_VAR_DETECTED": "justify it, or make it local",
    "FORBIDDEN_CHAR_NAME": "rename: lowercase, digits and _ only",
    "USER_DEFINED_TYPEDEF": "rename the typedef to t_*",
    "STRUCT_TYPE_NAMING": "rename the struct to s_*",
    "ENUM_TYPE_NAMING": "rename the enum to e_*",
    "UNION_TYPE_NAMING": "rename the union to u_*",
    "GLOBAL_VAR_NAMING": "rename the global to g_*",
    "MACRO_NAME_CAPITAL": "rename the macro in uppercase",
    "DECL_ASSIGN_LINE": "array/struct initialiser: declare it, then assign each element",
    "WRONG_SCOPE_COMMENT": "no comments inside a function — move it above the function",
    "WRONG_SCOPE_VAR": "move the declaration to the top of the function",
    "VAR_DECL_START_FUNC": "move the declaration to the top of the function",
}


# --------------------------------------------------------------------------
# Header protection for .h files (HEADER_PROT_*)
# --------------------------------------------------------------------------

HEADER_PROT_CODES = {
    "HEADER_PROT_ALL",
    "HEADER_PROT_ALL_AF",
    "HEADER_PROT_NAME",
    "HEADER_PROT_UPPER",
    "HEADER_PROT_MULT",
    "HEADER_PROT_NODEF",
}


def guard_name(path: str) -> str:
    base = os.path.basename(path)
    return re.sub(r"[^A-Z0-9]", "_", base.upper())


def fix_header_protection(path: str, lines: List[str]) -> bool:
    """Rewrite a .h file's include guard in the form norminette accepts:

        #ifndef FILE_H
        # define FILE_H
        ...
        #endif

    Only called when norminette reported a HEADER_PROT_* error. A .h with no
    guard at all is left alone — the Norm does not require one.
    """
    if not path.endswith(".h"):
        return False

    # Skip past the 42 header block: find its closing line, not its opening one.
    end = 0
    if lines and lines[0].startswith("/* *"):
        for i in range(1, len(lines)):
            if lines[i].startswith("/* *****"):
                end = i + 1
                break
        while end < len(lines) and lines[end].strip() == "":
            end += 1

    header, body = lines[:end], lines[end:]

    # Drop any existing guard so we do not stack a second one.
    name = guard_name(path)
    body = [
        ln
        for ln in body
        if not re.match(r"^\s*#\s*ifndef\s+\w+\s*$", ln)
        and not re.match(r"^\s*#\s*define\s+\w+\s*$", ln)
        and not re.match(r"^\s*#\s*endif\b", ln)
    ]
    while body and body[0].strip() == "":
        body.pop(0)
    while body and body[-1].strip() == "":
        body.pop()

    new = header + [f"#ifndef {name}", f"# define {name}", ""] + body + ["", "#endif"]
    if new == lines:
        return False
    lines[:] = new
    return True


# --------------------------------------------------------------------------


def fix_file(path: str, verbose: bool = False) -> List[Error]:
    """Converge `path` towards the Norm. Returns the errors that remain."""
    # A file not ending in a newline trips BRACE_SHOULD_EOL on its last brace.
    with open(path) as f:
        content = f.read()
    if content and not content.endswith("\n"):
        with open(path, "w") as f:
            f.write(content + "\n")

    errors = norminette(path)
    history = set()

    for _ in range(MAX_ROUNDS):
        if not any(e.code in FIXERS or e.code in HEADER_PROT_CODES for e in errors):
            break

        with open(path) as f:
            lines = f.read().split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        before = list(lines)

        if any(e.code in HEADER_PROT_CODES for e in errors):
            fix_header_protection(path, lines)
        else:
            # Bottom-up so earlier line numbers stay valid as we insert/delete,
            # and structural fixes before cosmetic ones on the same line.
            seen = set()
            for err in sorted(errors, key=lambda e: (-e.line, PRIORITY.get(e.code, 0))):
                if err.code not in FIXERS or err.line in seen:
                    continue
                if FIXERS[err.code](lines, err):
                    seen.add(err.line)

        if lines == before:
            break

        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")

        clang_pass(path)

        # A fixer and the formatter can disagree and undo each other forever.
        # If we land on a file state we have already produced, stop.
        with open(path) as f:
            state = f.read()
        if state in history:
            break
        history.add(state)

        errors = norminette(path)
        if verbose:
            print(f"  round: {len(errors)} error(s) left", file=sys.stderr)

    return errors


def hints(paths: List[str]) -> None:
    """Print what to do about the errors no formatter can fix."""
    seen = {}
    for path in paths:
        for err in norminette(path):
            if err.code in UNFIXABLE:
                seen.setdefault(err.code, UNFIXABLE[err.code])
    if seen:
        print("\nnot auto-fixable — these need a decision from you:")
        for code, hint in sorted(seen.items()):
            print(f"  {code:22} {hint}")


def main(argv: List[str]) -> int:
    verbose = "-v" in argv
    paths = [a for a in argv if not a.startswith("-")]
    if not paths:
        print("usage: normfix.py [-v] [--hints] FILE...", file=sys.stderr)
        return 2

    if "--hints" in argv:
        hints(paths)
        return 0

    rc = 0
    for path in paths:
        remaining = fix_file(path, verbose=verbose)
        if remaining:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
