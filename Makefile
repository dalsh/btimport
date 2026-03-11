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

dist:
	@mkdir -p dist
	tar -czf dist/btimport-$(shell grep '__version__ =' btimport.py | cut -d '"' -f 2).tar.gz btimport.py Makefile LICENSE README.md

.PHONY: all install uninstall test dist
