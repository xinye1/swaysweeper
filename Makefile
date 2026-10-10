PY      ?= /usr/bin/python3
ID      := io.github.xinye1.swaysweeper
BINDIR  := $(HOME)/.local/bin
LIBDIR  := $(HOME)/.local/share/swaysweeper
APPDIR  := $(HOME)/.local/share/applications

.PHONY: test install uninstall

test:
	$(PY) -m unittest discover -s tests -t . -v

# Exec= is absolute on purpose: the sway session's PATH has no ~/.local/bin,
# so a bare `swaysweeper` never resolves from fuzzel or Super+Space.
install:
	rm -rf $(LIBDIR)
	install -d $(LIBDIR)/swaysweeper $(BINDIR) $(APPDIR)
	install -m 644 swaysweeper/*.py $(LIBDIR)/swaysweeper/
	install -m 755 bin/swaysweeper $(BINDIR)/swaysweeper
	sed 's|@BINDIR@|$(BINDIR)|' data/$(ID).desktop.in > $(APPDIR)/$(ID).desktop
	-update-desktop-database $(APPDIR) 2>/dev/null

uninstall:
	rm -rf $(LIBDIR)
	rm -f $(BINDIR)/swaysweeper $(APPDIR)/$(ID).desktop
