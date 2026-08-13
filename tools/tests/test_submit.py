#!/usr/bin/env python3
"""Tests for normsubmit.

The two things that must never go wrong: stripping main() must leave a file
norminette still accepts, and restoring it must give back the original file
byte for byte.

    python3 tools/tests/test_submit.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORMSUBMIT = os.path.join(ROOT, "normsubmit")

HEADER_GEN = os.path.expanduser("~/.42tools/42header.py")


def write_with_header(path: str, source: str) -> str:
    """Write `source` with a real 42 header on top, so norminette judges the
    code and not the header. Returns the resulting file contents."""
    with open(path, "w") as f:
        f.write(source)
    subprocess.run(
        ["python3", HEADER_GEN, "mumoiz", "mumoiz@learner.42.tech", path],
        capture_output=True, text=True,
    )
    with open(path) as f:
        return f.read()

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((ok, name, detail))


def run(args: list[str], cwd: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [NORMSUBMIT] + args, capture_output=True, text=True, cwd=cwd, input=stdin
    )


def norm_ok(path: str) -> bool:
    proc = subprocess.run(
        ["norminette", os.path.basename(path)],
        capture_output=True, text=True, cwd=os.path.dirname(path),
    )
    return "OK!" in proc.stdout


SIMPLE = """\
#include <stdio.h>

int\tft_strlen(char *s)
{
\tint\ti;

\ti = 0;
\twhile (s[i])
\t\ti++;
\treturn (i);
}

int\tmain(void)
{
\tprintf("%d\\n", ft_strlen("hello"));
\treturn (0);
}
"""

ARGV = """\
int\tft_one(void)
{
\treturn (1);
}

int\tmain(int argc, char **argv)
{
\tif (argc > 1 && argv[1][0] == '{')
\t\treturn (1);
\treturn (ft_one());
}
"""

NO_MAIN = """\
int\tdomain_of(int n)
{
\treturn (n);
}

int\tmainly(int n)
{
\treturn (n + 1);
}
"""


def case_strip_restore(tmp: str, name: str, source: str) -> None:
    work = os.path.join(tmp, name)
    os.makedirs(work)
    path = os.path.join(work, "f.c")
    original = write_with_header(path, source)

    run(["--strip-main", "f.c"], work)
    with open(path) as f:
        stripped = f.read()

    check("normsubmit: main()" in stripped, f"{name}: main() was commented out")
    check("int\tmain" not in stripped.replace("// int\tmain", ""),
          f"{name}: no live main() left")
    check(norm_ok(path), f"{name}: still passes norminette after strip")

    # Stripping again must be a no-op.
    run(["--strip-main", "f.c"], work)
    with open(path) as f:
        check(f.read() == stripped, f"{name}: strip is idempotent")

    run(["--restore-main", "f.c"], work)
    with open(path) as f:
        restored = f.read()
    check(restored == original, f"{name}: restore is byte-identical",
          "" if restored == original else f"got:\n{restored}")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="normsubmit-tests-")
    try:
        case_strip_restore(tmp, "simple", SIMPLE)
        case_strip_restore(tmp, "argv-and-brace-in-char", ARGV)

        # A file with no main() must be left completely alone.
        work = os.path.join(tmp, "nomain")
        os.makedirs(work)
        path = os.path.join(work, "f.c")
        expected = write_with_header(path, NO_MAIN)
        proc = run(["--strip-main", "f.c"], work)
        with open(path) as f:
            check(f.read() == expected, "lookalike names (domain_of, mainly) untouched")
        check("no main() to strip" in proc.stdout, "reports that there was no main()")

        # Junk detection, including a real compiled binary.
        work = os.path.join(tmp, "junk")
        os.makedirs(work)
        with open(os.path.join(work, "prog.c"), "w") as f:
            f.write("int main(void){return 0;}\n")
        subprocess.run(["/usr/bin/cc", "-o", "prog", "prog.c"], cwd=work,
                       capture_output=True)
        for name in ("a.out", ".DS_Store", "ft.o"):
            open(os.path.join(work, name), "w").close()
        os.makedirs(os.path.join(work, "prog.dSYM"))

        out = run([], work).stdout
        for expected in ("a.out", ".DS_Store", "ft.o", "prog.dSYM", "./prog"):
            check(expected in out, f"report lists {expected}")

        # --clean must delete nothing when the answer is no.
        before = sorted(os.listdir(work))
        run(["--clean"], work, stdin="n\n")
        check(sorted(os.listdir(work)) == before, "--clean deletes nothing without consent")

        run(["--clean", "--yes"], work)
        left = sorted(os.listdir(work))
        check(left == ["prog.c"], "--clean --yes removes exactly the junk", f"left: {left}")

        # Exit codes.
        work = os.path.join(tmp, "clean")
        os.makedirs(work)
        write_with_header(os.path.join(work, "ft_one.c"),
                          "int\tft_one(void)\n{\n\treturn (1);\n}\n")
        check(run([], work).returncode == 0, "clean directory exits 0")
        check(run([], os.path.join(tmp, "simple")).returncode == 1,
              "directory with problems exits 1")

        # --gitignore must not clobber an existing file.
        work = os.path.join(tmp, "gi")
        os.makedirs(work)
        run(["--gitignore"], work)
        check(os.path.exists(os.path.join(work, ".gitignore")), "--gitignore writes the file")
        with open(os.path.join(work, ".gitignore"), "w") as f:
            f.write("mine\n")
        run(["--gitignore"], work)
        with open(os.path.join(work, ".gitignore")) as f:
            check(f.read() == "mine\n", "--gitignore never overwrites an existing file")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for ok, _, _ in results if ok)
    for ok, name, detail in results:
        print(("ok    " if ok else "FAIL  ") + name)
        if not ok and detail:
            print("      " + detail.replace("\n", "\n      "))
    print(f"\n{passed} passed, {len(results) - passed} failed")
    return 1 if passed != len(results) else 0


if __name__ == "__main__":
    sys.exit(main())
