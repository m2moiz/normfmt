#!/usr/bin/env python3
"""Randomised robustness test for normfmt.

Takes known-good programs, applies semantics-preserving mutations that mangle
the layout (join lines, strip blank lines, spaces instead of tabs, merge
declarations, add trailing whitespace), then formats and checks that the
program still compiles, still prints the same thing, and that a second format
pass changes nothing.

    python3 tools/tests/test_fuzz.py [rounds]
"""

from __future__ import annotations

import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORMFMT = os.path.join(ROOT, "normfmt")
CC = "/usr/bin/cc"
SEED = int(os.environ.get("NORMFMT_FUZZ_SEED", 20260813))

SOURCES = [
    r"""#include <stdio.h>

int	ft_max(int a, int b)
{
	if (a > b)
		return (a);
	return (b);
}

int	main(void)
{
	int	i;
	int	best;
	int	acc;

	i = 0;
	best = -100;
	acc = 0;
	while (i < 12)
	{
		best = ft_max(best, i * 3 % 7);
		acc = acc + best;
		i++;
	}
	printf("%d|%d\n", best, acc);
	return (0);
}
""",
    r"""#include <stdio.h>

int	ft_strlen(char *s)
{
	int	i;

	i = 0;
	while (s[i])
		i++;
	return (i);
}

int	main(void)
{
	char	*s;
	int	n;
	int	sum;

	s = "hello, 42 world";
	n = ft_strlen(s);
	sum = 0;
	while (n > 0)
	{
		sum = sum + s[n - 1];
		n--;
	}
	printf("%d|%d\n", ft_strlen(s), sum);
	return (0);
}
""",
    r"""#include <stdio.h>

int	main(void)
{
	int	tab[5];
	int	i;
	int	total;

	i = 0;
	while (i < 5)
	{
		tab[i] = i * i;
		i++;
	}
	total = 0;
	i = 0;
	while (i < 5)
	{
		if (tab[i] % 2 == 0)
			total = total + tab[i];
		else
			total = total - tab[i];
		i++;
	}
	printf("%d\n", total);
	return (0);
}
""",
]

DECL_RE = re.compile(r"^(\s*)((?:unsigned |long |short |const )*\w+)\s+(\**\w+);$")


def mutate(source: str, rng: random.Random) -> str:
    lines = source.split("\n")

    # 1. merge two adjacent declarations of the same type into one line
    if rng.random() < 0.7:
        for i in range(len(lines) - 1):
            a, b = DECL_RE.match(lines[i]), DECL_RE.match(lines[i + 1])
            if a and b and a.group(2) == b.group(2):
                lines[i:i + 2] = [f"{a.group(1)}{a.group(2)} {a.group(3)}, {b.group(3)};"]
                break

    # 2. join two adjacent simple statements onto one line
    if rng.random() < 0.7:
        simple = [
            i
            for i, ln in enumerate(lines[:-1])
            if ln.strip().endswith(";")
            and not ln.strip().startswith("return")
            and "{" not in lines[i + 1]
            and lines[i + 1].strip().endswith(";")
            and not lines[i + 1].strip().startswith("return")
            and ln[: len(ln) - len(ln.lstrip())] == lines[i + 1][: len(lines[i + 1]) - len(lines[i + 1].lstrip())]
        ]
        if simple:
            i = rng.choice(simple)
            lines[i:i + 2] = [lines[i] + " " + lines[i + 1].strip()]

    out = []
    for ln in lines:
        # 3. blank lines: drop some, duplicate others
        if ln.strip() == "":
            r = rng.random()
            if r < 0.4:
                continue
            if r < 0.6:
                out.extend(["", "", ""])
                continue
            if r < 0.75:
                out.append("   ")
                continue

        # 4. tabs -> spaces, sometimes the wrong number
        if ln.startswith("\t") and rng.random() < 0.6:
            depth = len(ln) - len(ln.lstrip("\t"))
            ln = " " * (depth * rng.choice([1, 2, 3, 4])) + ln.lstrip("\t")

        # 5. trailing whitespace
        if rng.random() < 0.3:
            ln = ln + "  "

        # 6. space before the semicolon
        if rng.random() < 0.15 and ln.rstrip().endswith(";"):
            ln = ln.rstrip()[:-1] + " ;"

        out.append(ln)

    return "\n".join(out)


def compile_and_run(src: str, workdir: str, tag: str):
    exe = os.path.join(workdir, tag)
    comp = subprocess.run([CC, "-o", exe, src], capture_output=True, text=True, cwd=workdir)
    if comp.returncode != 0:
        return False, comp.stderr.strip()
    run = subprocess.run([exe], capture_output=True, text=True, cwd=workdir)
    return True, run.stdout


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    rng = random.Random(SEED)
    tmp = tempfile.mkdtemp(prefix="normfmt-fuzz-")
    passed = failed = 0

    try:
        for n in range(rounds):
            base = SOURCES[n % len(SOURCES)]
            work = os.path.join(tmp, f"round{n}")
            os.makedirs(work)

            ref_path = os.path.join(work, "ref.c")
            with open(ref_path, "w") as f:
                f.write(base)
            ok, expected = compile_and_run(ref_path, work, "ref")
            if not ok:
                print(f"FAIL  round {n}: reference does not compile: {expected}")
                failed += 1
                continue

            mutated = mutate(base, rng)
            path = os.path.join(work, "prog.c")
            with open(path, "w") as f:
                f.write(mutated)

            subprocess.run([NORMFMT, path], capture_output=True, text=True, cwd=work)

            ok, got = compile_and_run(path, work, "out")
            with open(path) as f:
                first = f.read()
            subprocess.run([NORMFMT, path], capture_output=True, text=True, cwd=work)
            with open(path) as f:
                second = f.read()

            norm = subprocess.run(["norminette", path], capture_output=True, text=True, cwd=work)
            clean = "OK!" in norm.stdout

            problems = []
            if not ok:
                problems.append(f"does not compile after formatting:\n{got}")
            elif got != expected:
                problems.append(f"output changed: expected {expected!r}, got {got!r}")
            if first != second:
                problems.append("not idempotent")
            if not clean:
                errs = [ln for ln in norm.stdout.splitlines() if ln.startswith("Error")]
                problems.append("not norm clean:\n" + "\n".join(errs))

            if problems:
                failed += 1
                print(f"FAIL  round {n}")
                for p in problems:
                    print("      " + p.replace("\n", "\n      "))
                keep = os.environ.get("NORMFMT_FUZZ_KEEP")
                if keep:
                    os.makedirs(keep, exist_ok=True)
                    with open(os.path.join(keep, f"round{n}.in.c"), "w") as f:
                        f.write(mutated)
                    with open(os.path.join(keep, f"round{n}.out.c"), "w") as f:
                        f.write(first)
                    print(f"      artifacts written to {keep}/round{n}.*.c")
                else:
                    print("      --- mutated input ---")
                    print("      " + mutated.replace("\n", "\n      "))
            else:
                passed += 1
                print(f"ok    round {n}  ({expected.strip()!r}, norm clean)")

        print(f"\n{passed} passed, {failed} failed  (seed {SEED})")
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
