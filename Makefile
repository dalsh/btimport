PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin

all:
	@echo "Run 'sudo make install' to install btimport."

install:
	install -Dm755 btimport.py $(DESTDIR)$(BINDIR)/btimport

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/btimport

test:
	python3 test_btimport.py

.PHONY: all install uninstall test
