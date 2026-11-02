# Per-user install into ~/.local (no root needed). Override with PREFIX=...
#   make install     add launcher, menu entry and icon
#   make uninstall   remove them again
# The launcher is a symlink into this repo, so code changes apply without
# reinstalling. Re-run "make install" after moving the repo.

APP_ID   := io.github.chris_lep.LedControl
PREFIX   ?= $(HOME)/.local
BINDIR   := $(PREFIX)/bin
APPSDIR  := $(PREFIX)/share/applications
ICONROOT := $(PREFIX)/share/icons/hicolor
ICONDIR  := $(ICONROOT)/scalable/apps

REPO_BIN := $(CURDIR)/bin/led-control
BIN      := $(BINDIR)/led-control
DESKTOP  := $(APPSDIR)/$(APP_ID).desktop
ICON     := $(ICONDIR)/$(APP_ID).svg

# Dev tools: run inside any Python environment that has pytest and ruff
# (e.g. a venv). Override with PYTHON=/path/to/python.
PYTHON        ?= python3
SYSTEM_PYTHON ?= /usr/bin/python3

.PHONY: install uninstall test test-all lint

install:
	install -d "$(BINDIR)" "$(APPSDIR)" "$(ICONDIR)"
	ln -sfn "$(REPO_BIN)" "$(BIN)"
	sed 's|@BIN@|$(BIN)|' data/$(APP_ID).desktop.in > "$(DESKTOP)"
	chmod 644 "$(DESKTOP)"
	install -m 644 data/$(APP_ID).svg "$(ICON)"
	@$(MAKE) --no-print-directory _refresh

uninstall:
	@if [ -L "$(BIN)" ] && [ "$$(readlink "$(BIN)")" = "$(REPO_BIN)" ]; then \
		rm -f "$(BIN)"; echo "removed $(BIN)"; \
	elif [ -e "$(BIN)" ]; then echo "kept $(BIN): not a link to this repo"; fi
	rm -f "$(DESKTOP)" "$(ICON)"
	@$(MAKE) --no-print-directory _refresh

# Refresh desktop/icon caches, but only ones that already exist: creating an
# icon cache where there was none would hide icons other apps add later.
.PHONY: _refresh
_refresh:
	-@command -v update-desktop-database >/dev/null && update-desktop-database -q "$(APPSDIR)"
	-@if [ -f "$(ICONROOT)/icon-theme.cache" ] && command -v gtk-update-icon-cache >/dev/null; \
		then gtk-update-icon-cache -q -t -f "$(ICONROOT)"; fi

test:
	$(PYTHON) -m pytest

# The GUI tests need GTK, which only the system Python has (unless your venv was
# made with --system-site-packages, then "make test" runs them already). This
# runs the system Python with pytest borrowed from $(PYTHON)'s environment.
test-all:
	@$(PYTHON) -c 'import pytest' 2>/dev/null || { \
		echo "$(PYTHON) has no pytest: activate your dev environment or pass PYTHON=..." >&2; \
		exit 1; } && \
	env_ver=$$($(PYTHON) -c 'import sys; print("%d.%d" % sys.version_info[:2])') && \
	sys_ver=$$($(SYSTEM_PYTHON) -c 'import sys; print("%d.%d" % sys.version_info[:2])') && \
	if [ "$$env_ver" != "$$sys_ver" ]; then \
		echo "$(PYTHON) is Python $$env_ver, $(SYSTEM_PYTHON) is $$sys_ver: they must match" >&2; \
		exit 1; fi && \
	site=$$($(PYTHON) -c 'import os, pytest; print(os.path.dirname(os.path.dirname(pytest.__file__)))') && \
	PYTHONPATH="$$site" $(SYSTEM_PYTHON) -m pytest -p no:cacheprovider

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
