#!/usr/bin/env python3
"""Test suite for normfmt / normfix.

Each case writes a file, runs normfmt on it, and asserts either that norminette
reports it clean or that exactly the expected unfixable errors remain.

    python3 tools/tests/test_normfix.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORMFMT = os.path.join(ROOT, "normfmt")

ERROR_RE = re.compile(r"^(?:Error|Notice):\s+([A-Z_0-9]+)\s")


def remaining_errors(path: str) -> list[str]:
    proc = subprocess.run(
        ["norminette", path], capture_output=True, text=True, cwd=os.path.dirname(path)
    )
    out = []
    for raw in (proc.stdout + proc.stderr).splitlines():
        m = ERROR_RE.match(raw.strip())
        if m:
            out.append(m.group(1))
    return out


def body(path: str) -> str:
    """File contents with the 42 header stripped."""
    with open(path) as f:
        lines = f.read().split("\n")
    if lines and lines[0].startswith("/* *"):
        for i, ln in enumerate(lines[1:], 1):
            if ln.startswith("/* *****"):
                lines = lines[i + 1:]
                break
    return "\n".join(lines).strip("\n")


CASES = []


def case(name, filename, source, expect=None, expect_body=None, forbid=()):
    """expect: the exact set of remaining errors. forbid: codes that must be gone,
    without pinning down the rest (for messy files with unrelated errors)."""
    CASES.append(
        (name, filename, source, None if expect is None else sorted(expect),
         expect_body, tuple(forbid))
    )


# ---------------------------------------------------------------- fixable ---

case(
    "multiple declarations",
    "a.c",
    "int\tf(void)\n{\n\tint\ta, b;\n\ta = 1;\n\tb = 2;\n\treturn (a + b);\n}\n",
    expect_body="int\tf(void)\n{\n\tint\ta;\n\tint\tb;\n\n\ta = 1;\n\tb = 2;\n\treturn (a + b);\n}",
)

case(
    "multiple pointer declarations",
    "b.c",
    "int\tf(char *s)\n{\n\tchar\t*a, *b;\n\ta = s;\n\tb = s;\n\treturn (a == b);\n}\n",
)

case(
    "declaration with array",
    "c.c",
    "int\tf(void)\n{\n\tint\ttab[3], n;\n\tn = 0;\n\ttab[0] = n;\n\treturn (tab[0]);\n}\n",
)

case(
    "no blank line after declarations",
    "d.c",
    "int\tf(void)\n{\n\tint\ta;\n\ta = 1;\n\treturn (a);\n}\n",
)

case(
    "no blank line between functions",
    "e.c",
    "int\tf(void)\n{\n\treturn (1);\n}\nint\tg(void)\n{\n\treturn (2);\n}\n",
)

case(
    "consecutive blank lines",
    "f.c",
    "int\tf(void)\n{\n\treturn (1);\n}\n\n\n\nint\tg(void)\n{\n\treturn (2);\n}\n",
)

case(
    "blank line at end of file",
    "g.c",
    "int\tf(void)\n{\n\treturn (1);\n}\n\n\n",
)

case(
    "whitespace on a blank line",
    "h.c",
    "int\tf(void)\n{\n\tint\ta;\n   \n\ta = 1;\n\treturn (a);\n}\n",
)

case(
    "everything at once",
    "i.c",
    "int\tf(void)\n{\n\tint\ta, b;\n\ta = 1;\n\tb = 2;\n\treturn (a + b);\n}\nint\tg(void)\n{\n\treturn (2);\n}\n\n\n",
)

case(
    "comma operator between assignments",
    "o.c",
    "int\tf(void)\n{\n\tint\ta;\n\tint\tb;\n\n\ta = 1, b = 2;\n\treturn (a + b);\n}\n",
)

case(
    "several statements on one line",
    "p.c",
    "int\tf(void)\n{\n\tint\ta;\n\tint\tb;\n\n\ta = 1; b = 2;\n\treturn (a + b);\n}\n",
)

case(
    "commas inside a string are not split points",
    "q.c",
    'int\tf(char *s)\n{\n\tchar\t*a, *b;\n\n\ta = "x, y";\n\tb = s;\n\treturn (a != b);\n}\n',
)

case(
    "declaration with a trailing comment is still split",
    "r.c",
    "int\tf(void)\n{\n\tint\ta, b; /* two counters */\n\n\ta = 1;\n\tb = 2;\n\treturn (a + b);\n}\n",
    forbid=["MULT_DECL_LINE"],
)

case(
    "array initialiser is not split on its commas",
    "s.c",
    "int\tf(void)\n{\n\tint\ttab[3];\n\n\ttab[0] = 1;\n\ttab[1] = 2;\n\ttab[2] = 3;\n\treturn (tab[0]);\n}\n",
)

case(
    "prototype at global scope is not split",
    "t.c",
    "int\tft_max(int a, int b);\n\nint\tft_max(int a, int b)\n{\n\tif (a > b)\n\t\treturn (a);\n\treturn (b);\n}\n",
)

case(
    "deeply nested blocks",
    "u.c",
    "int\tf(int n)\n{\n\tint\ti, j;\n\n\ti = 0;\n\twhile (i < n)\n\t{\n\t\tj = 0;\n\t\twhile (j < n)\n\t\t{\n\t\t\tif (i == j)\n\t\t\t\tj++;\n\t\t\tj++;\n\t\t}\n\t\ti++;\n\t}\n\treturn (i);\n}\n",
)

# ------------------------------------------------------------ header files ---

case(
    # The Norm does not require an include guard, so we must not invent one.
    "guardless header is left alone",
    "inc.h",
    "int\tft_max(int a, int b);\n",
    expect_body="int\tft_max(int a, int b);",
)

case(
    "wrongly named include guard",
    "wrong.h",
    "# ifndef FOO\n#  define FOO\n\nint\tft_max(int a, int b);\n\n# endif\n",
    expect_body="#ifndef WRONG_H\n# define WRONG_H\n\nint\tft_max(int a, int b);\n\n#endif",
)

case(
    "guard missing its #define",
    "nodef.h",
    "#ifndef NODEF_H\n\nint\tft_max(int a, int b);\n\n#endif\n",
    expect_body="#ifndef NODEF_H\n# define NODEF_H\n\nint\tft_max(int a, int b);\n\n#endif",
)

# -------------------------------------------------------------- unfixable ---

case(
    "for loop stays",
    "j.c",
    "int\tf(void)\n{\n\tint\ti;\n\n\ti = 0;\n\tfor (i = 0; i < 3; i++)\n\t\ti++;\n\treturn (i);\n}\n",
    expect=["FORBIDDEN_CS"],
)

case(
    "long function stays",
    "k.c",
    "int\tf(void)\n{\n\tint\tx;\n\n\tx = 0;\n" + "\tx++;\n" * 26 + "\treturn (x);\n}\n",
    expect=["TOO_MANY_LINES"],
)

case(
    "uppercase identifier stays",
    "l.c",
    "int\tBadName(void)\n{\n\treturn (1);\n}\n",
    expect=["FORBIDDEN_CHAR_NAME", "FORBIDDEN_CHAR_NAME"],
)

# ------------------------------------------------------ must not be broken ---

case(
    "function pointer declaration is left intact",
    "m.c",
    "int\tf(void)\n{\n\tint\t(*fp)(int, int);\n\n\tfp = 0;\n\treturn (fp == 0);\n}\n",
)

case(
    "struct members in a header are split",
    "st.h",
    "typedef struct s_point\n{\n\tint\tx, y;\n}\tt_point;\n",
)

case(
    "file containing only a header",
    "empty.c",
    "",
)

case(
    "already clean file is untouched",
    "n.c",
    "int\tf(void)\n{\n\tint\ta;\n\n\ta = 1;\n\treturn (a);\n}\n",
    expect_body="int\tf(void)\n{\n\tint\ta;\n\n\ta = 1;\n\treturn (a);\n}",
)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="normfix-tests-")
    passed = failed = 0

    try:
        for name, filename, source, expect, expect_body, forbid in CASES:
            path = os.path.join(tmp, filename)
            with open(path, "w") as f:
                f.write(source)

            subprocess.run(
                [NORMFMT, path], capture_output=True, text=True, cwd=tmp
            )

            problems = []

            got = sorted(remaining_errors(path))
            if expect is not None and got != expect:
                problems.append(f"errors: expected {expect or 'none'}, got {got or 'none'}")
            still_there = [c for c in forbid if c in got]
            if still_there:
                problems.append(f"should have been fixed but remain: {still_there}")

            if expect_body is not None and body(path) != expect_body:
                problems.append(
                    "body mismatch:\n--- expected ---\n"
                    + expect_body
                    + "\n--- got ---\n"
                    + body(path)
                )

            # Idempotency: a second run must not change the file.
            with open(path) as f:
                first = f.read()
            subprocess.run([NORMFMT, path], capture_output=True, text=True, cwd=tmp)
            with open(path) as f:
                second = f.read()
            if first != second:
                problems.append("not idempotent: second run changed the file")

            if problems:
                failed += 1
                print(f"FAIL  {name}")
                for p in problems:
                    print("      " + p.replace("\n", "\n      "))
            else:
                passed += 1
                print(f"ok    {name}")

        print(f"\n{passed} passed, {failed} failed")
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
