# normfmt

*[Version française](README.fr.md)*

Stop fixing the Norm by hand. `normfmt` formats your C to the 42 Norm, writes
the header, runs norminette, and tells you what is left. Terminal, vim,
VS Code. One install command.

No sudo. No Homebrew. Works on a cluster iMac and on your own laptop, ~20 MB
under `$HOME`.

## What it does

Tabs, parentheses, blank lines. All the parts of the Norm that have nothing to
do with your algorithm and everything to do with where the whitespace goes. You
write the logic, it handles the rest.

What you write:

```c
int	ft_max(int *tab, int len) {
  int i = 0;
  int max=tab[0];
  while(i<len)
  {
    if (tab[i] > max) max = tab[i];
    i++;
  }
  return max;
}
```

What you get, header on top with your login, and `norminette: OK!`

```c
int	ft_max(int *tab, int len)
{
	int	i;
	int	max;

	i = 0;
	max = tab[0];
	while (i < len)
	{
		if (tab[i] > max)
			max = tab[i];
		i++;
	}
	return (max);
}
```

Ten errors gone, and you never had to read one of them.

## Install

```sh
git clone https://github.com/m2moiz/normfmt.git ~/normfmt
cd ~/normfmt
./tools/install.sh
```

That covers the terminal command, vim, and VS Code in one go. Open a new
terminal when it finishes.

It reads your login from `$USER`, which is already right on a cluster machine.
On your own laptop, pass it yourself:

```sh
./tools/install.sh --login <your_login>
```

This ends up in the header of every file the tool touches, so get it right the
first time.

**VS Code needs one extension.** Install *Run on Save* by *emeraldwalk* from the
Extensions sidebar. The installer does it for you when the `code` command is on
your `$PATH`, and says so when it could not. Without it, saving does nothing.

Other flags: `--core-only` if you want the command and nothing touched in your
editor, `--email <addr>`, and `--uninstall` to take it all back off.

## Using it

```sh
normfmt ft_strlen.c     # format one file, then check it
normfmt                 # every .c/.h below the current directory
normfmt -n              # check only, rewrite nothing
```

In vim it runs on `:w`, and `:NormFmt` runs it on demand. Put
`let g:normfmt_on_save = 0` in your `.vimrc` if you want the command without the
autosave. In VS Code it runs on save.

Its exit code is norminette's, so it drops into a Makefile as is:

```make
norm:
	@normfmt
```

## Before you push

A leftover `main()` and files the subject never asked for are two of the easier
ways to collect a zero. `normsubmit` reads what you are about to commit and says
what looks wrong.

```
$ normsubmit

main() found — the subject usually wants the function only:
  ./ft_strlen.c
  ./main.c  (looks like a test driver, do not submit it at all)
  fix: normsubmit --strip-main ./ft_strlen.c

build output / junk — delete before committing:
  ./a.out   ./ft_strlen.o   ./ft_strlen.dSYM   ./.DS_Store
  fix: normsubmit --clean

git is already tracking these — they WILL be submitted:
  ./main.c
  fix: git rm --cached <file>, and add it to .gitignore
```

```sh
normsubmit --strip-main     # comment main() out, reversibly
normsubmit --restore-main   # put it back so you can keep testing
normsubmit --clean          # delete build junk (it asks first)
normsubmit --gitignore      # a .gitignore that suits a 42 repo
```

`--strip-main` comments the function out behind a marker, so `--restore-main`
hands you back the original file byte for byte and you can keep testing. The
commented version still passes norminette.

**It will not delete anything you wrote.** `--clean` prints the list and waits
for a yes, and it only removes build output: `.o`, `.a`, `a.out`, `.dSYM`,
`.DS_Store`, compiled binaries. Your source files get reported, never removed.

It exits 1 when something looks wrong, so it works as a pre-commit hook.
Whatever it says, stage your files by name. `git add .` is how people lose
points.

## What it will not fix

Anything that needs a decision about your program rather than its layout. A tool
that guessed here would be worse than no tool, so it prints these with a short
hint instead.

| Norm error | Why it is yours |
| --- | --- |
| `TOO_MANY_LINES` | Splitting a function is a design call |
| `TOO_MANY_FUNCS` | Which file does it move to? |
| `TOO_MANY_VARS_FUNC` | Fewer variables, or split the function |
| `FORBIDDEN_CS` | Turning a `for` into a `while` changes the code |
| `ASSIGN_IN_CONTROL` | Move the assignment out of the condition |
| `FORBIDDEN_CHAR_NAME` | No rule turns a bad name into a good one |
| `WRONG_SCOPE_COMMENT` | The Norm bans comments inside a function, and deleting yours is not the tool's call |

## Is it safe on my code?

Fair thing to ask about anything that rewrites your files. Four suites run
before every change, and a file that is already clean comes back byte for byte
identical.

```sh
python3 tools/tests/test_normfix.py     # 26 passed, 0 failed
python3 tools/tests/test_semantics.py   #  8 passed, 0 failed
python3 tools/tests/test_submit.py      # 23 passed, 0 failed
python3 tools/tests/test_fuzz.py 30     # 30 passed, 0 failed
```

The semantics suite compiles each program, runs it, formats it, compiles and
runs it again, then checks the output is byte for byte the same. A formatter
that changes what your program prints is worse than no formatter.

The fuzzer mangles working programs at random, joining statements onto one line,
merging declarations, swapping tabs for spaces, scattering blank lines around.
Then it checks the result still compiles, still prints the same thing, passes
norminette, and does not change on a second run. 210 rounds across 6 seeds pass.
It found two real bugs, which is the only reason I trust the other three suites.

It only ever touches `.c` and `.h`, and `normfmt -n` checks without writing
anything at all.

Set `NORMFMT_FUZZ_SEED` to vary the mutations, and `NORMFMT_FUZZ_KEEP=<dir>` to
keep the artifacts of a failing round.

## When something breaks

**`normfmt: command not found`** — open a new terminal. If it still happens, run
`export PATH="$HOME/.local/bin:$PATH"`.

**`no python3 on PATH`** — run `xcode-select --install`, then start the
installer again.

**VS Code does nothing when I save** — the Run on Save extension is missing.
Look for "Run on Save" by emeraldwalk in the Extensions sidebar, then run
`./tools/install.sh --editors-only`.

**vim does nothing on `:w`** — check that `~/.vim/plugin/normfmt.vim` exists. If
it does not, run `./tools/install.sh` again. Neovim uses
`~/.config/nvim/plugin/`.

**Where did it put everything?**

| Path | What |
| --- | --- |
| `~/.42tools/` | virtualenv with norminette + c_formatter_42, plus the scripts |
| `~/.local/bin/` | `normfmt` and `normsubmit` |
| `~/.42toolsrc` | your login and email, used for the 42 header |
| `~/.vim/plugin/normfmt.vim` | vim format-on-save |
| editor `settings.json` | one `emeraldwalk.runonsave` rule, backed up first |

All of it lives under `$HOME`, so it survives between sessions, unlike
`~/goinfre`. `./tools/install.sh --uninstall` takes it all back off.

## How it works

Two tools that know nothing about each other, plus glue.
[c_formatter_42](https://github.com/cacharle/c_formatter_42), written by a 42
student, reshapes the code in ten passes. The first is clang-format driven by a
Norm-shaped config; the other nine handle what clang-format cannot express, like
putting return values in parentheses. norminette then checks the result.

The gap between the two is where the work went. Rather than write a C parser to
find the errors the formatter leaves behind, `normfix` asks norminette where they
are, applies a targeted fix at that line, re-runs the formatter to realign, and
repeats until nothing fixable is left. Supporting a new error is one entry in a
dict.

Errors `normfix` closes on top of the formatter:

| Error | Fix |
| --- | --- |
| `MULT_DECL_LINE` | `int a, b;` becomes one declaration per line |
| `MULT_ASSIGN_LINE` | `a = 1, b = 2;` becomes one assignment per line |
| `TOO_MANY_INSTR` | `a = 1; b = 2;` becomes one statement per line |
| `NL_AFTER_VAR_DECL` | blank line after the declaration block |
| `NEWLINE_PRECEDES_FUNC` | blank line between functions |
| `CONSECUTIVE_NEWLINES` | collapse to one |
| `EMPTY_LINE_FUNCTION` | drop the blank line |
| `EMPTY_LINE_FILE_START` / `EMPTY_LINE_EOF` | trim |
| `SPACE_EMPTY_LINE` / `SPC_BEFORE_NL` | strip trailing whitespace |
| `SPACE_REPLACE_TAB` | spaces the aligner left behind become a tab |
| `BRACE_SHOULD_EOL` | file not ending in a newline |
| `HEADER_PROT_*` | rewrite a `.h` include guard as `#ifndef FILE_H` / `# define FILE_H` / `#endif` |

Two details worth knowing if you work on it. norminette reports *visual*
columns, where a tab spans to the next multiple of 4, so a plain character index
points at the wrong character. And when two errors land on the same line, the
structural fix has to run before the cosmetic one, or the cosmetic fix claims
the line and the real problem never gets addressed. Both of those came out of
the fuzzer.

## Layout

```
tools/
  normfmt            the pipeline: format, header, fix, check
  normsubmit         pre-push checks: stray main(), junk files
  normfix.py         the norminette-driven fixer loop
  42header.py        42 header generator
  vscode_setup.py    editor settings merge, with backup
  install.sh         one-command install
  editor/            vim plugin, VS Code settings and tasks
  tests/             four suites
```

Python and bash. The only C++ in the stack is clang-format, which ships prebuilt
inside the `c_formatter_42` wheel, which is why nothing here needs a compiler.

## Credits

- [norminette](https://github.com/42School/norminette) by 42 School
- [c_formatter_42](https://github.com/cacharle/c_formatter_42) by cacharle
- clang-format, from LLVM
