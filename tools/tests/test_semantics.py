#!/usr/bin/env python3
"""Semantic-equivalence tests for normfmt.

For each program: compile and run it, run normfmt over it, compile and run it
again, and assert the output is byte-identical. A formatter that changes what
your program prints is worse than no formatter, so this is the test that
matters most.

    python3 tools/tests/test_semantics.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORMFMT = os.path.join(ROOT, "normfmt")
CC = "/usr/bin/cc"

PROGRAMS = {}


def program(name: str, source: str) -> None:
    PROGRAMS[name] = source


program(
    "comma operator and multiple declarations",
    r"""
#include <stdio.h>

int	main(void)
{
	int	tab[3];
	char	*s = "hello, world";
	char	c = ',';
	int	a, b;

	tab[0] = 1;
	tab[1] = 2;
	tab[2] = 3;
	a = tab[0], b = tab[1];
	printf("%s|%c|%d|%d|%d\n", s, c, a, b, tab[2]);
	return (0);
}
""",
)

program(
    "pointer declarations keep their levels",
    r"""
#include <stdio.h>

int	main(void)
{
	char	*a, b;
	int	*p, **q;
	unsigned long	x, y;
	int	n;

	b = 'Z';
	a = &b;
	n = 7;
	p = &n;
	q = &p;
	x = 1;
	y = 2;
	printf("%c|%d|%d|%lu\n", *a, *p, **q, x + y);
	return (0);
}
""",
)

program(
    "commas and semicolons inside literals and comments",
    r"""
#include <stdio.h>

int	main(void)
{
	char	*tricky = "a, b; c \" d, e";
	char	semi = ';';
	int	i, j;

	i = 1;
	j = 2;
	printf("%s|%c|%d\n", tricky, semi, i + j);
	return (0);
}
""",
)

program(
    "multiple statements on one line",
    r"""
#include <stdio.h>

int	main(void)
{
	int	a;
	int	b;
	int	c;

	a = 1; b = 2; c = 3;
	printf("%d\n", a * 100 + b * 10 + c);
	return (0);
}
""",
)

program(
    "nested loops and recursion",
    r"""
#include <stdio.h>

int	fact(int n)
{
	if (n <= 1)
		return (1);
	return (n * fact(n - 1));
}

int	main(void)
{
	int	i, j, total;

	total = 0;
	i = 0;
	while (i < 4)
	{
		j = 0;
		while (j < 3)
		{
			total = total + i * j;
			j++;
		}
		i++;
	}
	printf("%d|%d\n", total, fact(5));
	return (0);
}
""",
)

program(
    "preprocessor defines with commas",
    r"""
#include <stdio.h>

#define WIDTH 4
#define HEIGHT 3

int	main(void)
{
	int	w, h;

	w = WIDTH;
	h = HEIGHT;
	printf("%d\n", w * h);
	return (0);
}
""",
)

program(
    "string escapes and arithmetic precedence",
    r"""
#include <stdio.h>

int	main(void)
{
	int	a, b, c;
	char	*s;

	a = 2;
	b = 3;
	c = 4;
	s = "tab\there\nnewline";
	printf("%d|%d|%s\n", a + b * c, (a + b) * c, s);
	return (0);
}
""",
)

program(
    "already norm-clean file must not change behaviour",
    r"""
#include <stdio.h>

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

	i = 0;
	best = -100;
	while (i < 10)
	{
		best = ft_max(best, i * 3 % 7);
		i++;
	}
	printf("%d\n", best);
	return (0);
}
""",
)


def compile_and_run(src: str, workdir: str, tag: str) -> tuple[bool, str]:
    exe = os.path.join(workdir, tag)
    comp = subprocess.run(
        [CC, "-o", exe, src], capture_output=True, text=True, cwd=workdir
    )
    if comp.returncode != 0:
        return False, comp.stderr.strip()
    run = subprocess.run([exe], capture_output=True, text=True, cwd=workdir)
    return True, run.stdout


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="normfmt-sem-")
    passed = failed = 0

    try:
        for i, (name, source) in enumerate(PROGRAMS.items()):
            work = os.path.join(tmp, f"case{i}")
            os.makedirs(work)
            path = os.path.join(work, "prog.c")
            with open(path, "w") as f:
                f.write(source.lstrip("\n"))

            ok_before, out_before = compile_and_run(path, work, "before")
            if not ok_before:
                print(f"SKIP  {name}\n      source does not compile: {out_before}")
                failed += 1
                continue

            subprocess.run([NORMFMT, path], capture_output=True, text=True, cwd=work)

            ok_after, out_after = compile_and_run(path, work, "after")

            problems = []
            if not ok_after:
                problems.append(f"formatted source does not compile:\n{out_after}")
            elif out_after != out_before:
                problems.append(
                    f"output changed:\n  before: {out_before!r}\n  after:  {out_after!r}"
                )

            if problems:
                failed += 1
                print(f"FAIL  {name}")
                for p in problems:
                    print("      " + p.replace("\n", "\n      "))
                with open(path) as f:
                    print("      --- formatted ---")
                    print("      " + f.read().replace("\n", "\n      "))
            else:
                norm = subprocess.run(
                    ["norminette", path], capture_output=True, text=True, cwd=work
                )
                clean = "OK!" in norm.stdout
                passed += 1
                mark = "norm clean" if clean else "NORM ERRORS REMAIN"
                print(f"ok    {name}  ({out_before.strip()!r}) [{mark}]")
                if not clean:
                    for ln in norm.stdout.splitlines():
                        if ln.startswith("Error"):
                            print("      " + ln)

        print(f"\n{passed} passed, {failed} failed")
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
