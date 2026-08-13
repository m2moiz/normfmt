#!/usr/bin/env bash
# Install the 42 Norm auto-formatter. No sudo, no Homebrew, no admin rights.
#
#   ./tools/install.sh                     everything, login taken from $USER
#   ./tools/install.sh --login mumoiz --email mumoiz@learner.42.tech
#   ./tools/install.sh --core-only         terminal command only, no editors
#   ./tools/install.sh --uninstall         remove all of it
#
# Installs:
#   ~/.42tools/            venv + scripts   (~20 MB, survives between sessions)
#   ~/.local/bin/           normfmt and normsubmit
#   ~/.42toolsrc           your login and email, for the 42 header
#   ~/.vim/plugin/         format-on-save for vim / neovim
#   VS Code / Cursor       format-on-save rule in your user settings
#
# Re-running is safe: it upgrades in place and never duplicates anything.

set -euo pipefail

TOOLS_HOME="${FT_TOOLS_HOME:-$HOME/.42tools}"
BIN_DIR="$HOME/.local/bin"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LOGIN=""
EMAIL=""
DO_CORE=1
DO_EDITORS=1
UNINSTALL=0

while [ "$#" -gt 0 ]; do
	case "$1" in
		--login) LOGIN="${2-}"; shift 2 ;;
		--email) EMAIL="${2-}"; shift 2 ;;
		--core-only) DO_EDITORS=0; shift ;;
		--editors-only) DO_CORE=0; shift ;;
		--uninstall) UNINSTALL=1; shift ;;
		-h|--help)
			awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' \
				"${BASH_SOURCE[0]}"
			exit 0
			;;
		-*) echo "install.sh: unknown option $1" >&2; exit 2 ;;
		*)
			# Positional form: install.sh <login> [email]
			if [ -z "$LOGIN" ]; then LOGIN="$1"; else [ -z "$EMAIL" ] && EMAIL="$1"; fi
			shift
			;;
	esac
done

# Re-running without --login must not clobber an identity already set up.
if [ -z "$LOGIN" ] && [ -f "$HOME/.42toolsrc" ]; then
	# shellcheck disable=SC1091
	. "$HOME/.42toolsrc"
	LOGIN="${FT_LOGIN:-}"
	[ -z "$EMAIL" ] && EMAIL="${FT_EMAIL:-}"
fi

LOGIN="${LOGIN:-$USER}"
EMAIL="${EMAIL:-$LOGIN@learner.42.tech}"

# --------------------------------------------------------------- uninstall ---

if [ "$UNINSTALL" -eq 1 ]; then
	echo "==> removing the 42 formatter"
	[ -f "$TOOLS_HOME/vscode_setup.py" ] &&
		python3 "$TOOLS_HOME/vscode_setup.py" --remove || true
	rm -f "$BIN_DIR/normfmt" "$BIN_DIR/normsubmit"
	rm -f "$HOME/.vim/plugin/normfmt.vim" "$HOME/.config/nvim/plugin/normfmt.vim"
	rm -rf "$TOOLS_HOME"
	rm -f "$HOME/.42toolsrc"
	echo "==> done. Your PATH line in .zshrc (if any) was left in place."
	exit 0
fi

# -------------------------------------------------------------------- core ---

if [ "$DO_CORE" -eq 1 ]; then
	PY="${FT_PYTHON:-python3}"
	command -v "$PY" >/dev/null 2>&1 || {
		echo "install.sh: no python3 on PATH. On a campus Mac: xcode-select --install" >&2
		exit 1
	}

	echo "==> python:   $($PY --version 2>&1) at $(command -v "$PY")"
	echo "==> install:  $TOOLS_HOME"
	echo "==> identity: $LOGIN <$EMAIL>"

	mkdir -p "$TOOLS_HOME" "$BIN_DIR"

	# c_formatter_42 bundles its own clang-format binary per platform, so no
	# compiler, no Homebrew and no system clang-format are needed.
	[ -d "$TOOLS_HOME/venv" ] || "$PY" -m venv "$TOOLS_HOME/venv"
	"$TOOLS_HOME/venv/bin/python" -m pip install --quiet --upgrade pip
	"$TOOLS_HOME/venv/bin/pip" install --quiet --upgrade norminette c_formatter_42

	for script in normfmt normsubmit 42header.py normfix.py vscode_setup.py; do
		cp "$SRC_DIR/$script" "$TOOLS_HOME/$script"
		chmod +x "$TOOLS_HOME/$script"
	done
	cp "$SRC_DIR/editor/normfmt.vim" "$TOOLS_HOME/normfmt.vim"
	ln -sf "$TOOLS_HOME/normfmt" "$BIN_DIR/normfmt"
	ln -sf "$TOOLS_HOME/normsubmit" "$BIN_DIR/normsubmit"

	cat > "$HOME/.42toolsrc" <<EOF
FT_LOGIN=$LOGIN
FT_EMAIL=$EMAIL
EOF

	case ":$PATH:" in
		*":$BIN_DIR:"*) ;;
		*)
			for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
				[ -f "$rc" ] || continue
				grep -q 'HOME/.local/bin' "$rc" && continue
				printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
				echo "==> added ~/.local/bin to PATH in $rc"
			done
			echo "==> open a new shell, or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
			;;
	esac
fi

# ----------------------------------------------------------------- editors ---

if [ "$DO_EDITORS" -eq 1 ]; then
	echo "==> editors"

	if command -v vim >/dev/null 2>&1 || command -v nvim >/dev/null 2>&1; then
		if command -v vim >/dev/null 2>&1; then
			mkdir -p "$HOME/.vim/plugin"
			ln -sf "$TOOLS_HOME/normfmt.vim" "$HOME/.vim/plugin/normfmt.vim"
			echo "    vim: ~/.vim/plugin/normfmt.vim"
		fi
		if command -v nvim >/dev/null 2>&1; then
			mkdir -p "$HOME/.config/nvim/plugin"
			ln -sf "$TOOLS_HOME/normfmt.vim" "$HOME/.config/nvim/plugin/normfmt.vim"
			echo "    neovim: ~/.config/nvim/plugin/normfmt.vim"
		fi
	else
		echo "    no vim or neovim found — skipping"
	fi

	# The Run on Save extension is what actually triggers normfmt on save.
	EXT_DONE=0
	for cli in code cursor codium windsurf; do
		command -v "$cli" >/dev/null 2>&1 || continue
		if "$cli" --install-extension emeraldwalk.RunOnSave >/dev/null 2>&1; then
			echo "    $cli: installed the Run on Save extension"
			EXT_DONE=1
		fi
	done

	python3 "$TOOLS_HOME/vscode_setup.py"

	if [ "$EXT_DONE" -eq 0 ]; then
		echo "    NOTE: install the \"Run on Save\" extension by emeraldwalk in your"
		echo "          editor (Extensions sidebar), or format-on-save will not fire."
	fi
fi

# ------------------------------------------------------------------ report ---

if [ "$DO_CORE" -eq 1 ]; then
	echo
	echo "==> versions"
	"$TOOLS_HOME/venv/bin/norminette" --version 2>&1 | grep -v '^Setting locale'
	"$TOOLS_HOME/venv/bin/python" -c \
		'import importlib.metadata as m; print("c_formatter_42", m.version("c_formatter_42"))'
fi

echo
echo "Done."
echo "  normfmt file.c      format one file, then check it with norminette"
echo "  normfmt             format every .c/.h below the current directory"
echo "  normfmt -n          check only, do not rewrite"
echo "  normsubmit          check what you are about to hand to Moulinette"
echo "  vim                 formats on :w, or run :NormFmt"
echo "  VS Code / Cursor    formats on save"
