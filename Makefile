# Per-user install into ~/.local (no root needed). Override with PREFIX=...
#   make install     add launcher, menu entry and icon
#   make uninstall   remove them again
# The launcher is a symlink into this repo, so code changes apply without
# reinstalling. Re-run "make install" after moving the repo.

APP_ID   := dev.lepenik.LedControl
PREFIX   ?= $(HOME)/.local
BINDIR   := $(PREFIX)/bin
APPSDIR  := $(PREFIX)/share/applications
ICONROOT := $(PREFIX)/share/icons/hicolor
ICONDIR  := $(ICONROOT)/scalable/apps

REPO_BIN := $(CURDIR)/bin/led-control
BIN      := $(BINDIR)/led-control
DESKTOP  := $(APPSDIR)/$(APP_ID).desktop
ICON     := $(ICONDIR)/$(APP_ID).svg

# Dev tools from the conda env (see environment.yml).
ENV      ?= $(HOME)/miniconda3/envs/led-control
# Must match the system Python's version, since test-all mixes the two.
PYVER     = $(shell /usr/bin/python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
ENVSITE   = $(ENV)/lib/python$(PYVER)/site-packages

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
	"$(ENV)/bin/python" -m pytest

# Includes the GUI tests: system Python (GTK) + pytest from the conda env.
test-all:
	PYTHONPATH="$(ENVSITE)" /usr/bin/python3 -m pytest -p no:cacheprovider

lint:
	"$(ENV)/bin/ruff" check .
	"$(ENV)/bin/ruff" format --check .
