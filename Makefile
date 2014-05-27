PYPYPATH ?= ../pypy
PYTHON ?= python2
TRANSLATE = $(PYTHON) $(PYPYPATH)/rpython/translator/goal/translate.py
REVISION = $(shell git show --oneline | head -1 | sed 's/ .*//' | tr -d " ")
UNAME = $(shell uname -s -m | tr "A-Z " "a-z-" | tr -d " ")
PACKAGE = psota-$(REVISION)-$(UNAME)
PYTHON_SOURCES = $(shell git ls-files './psota/*.py')
CLJ_SOURCES = $(shell git ls-files './*.clj')
ifeq ($(shell rlwrap -v 2> /dev/null | grep rlwrap -c), 1)
	RLWRAP = rlwrap
else
	RLWRAP =
endif

.PHONY: all clean repl-O2 repl-Ojit repl tarball check

all: psota-O2

psota-O2: $(PYTHON_SOURCES)
	PYTHONPATH=$(PYPYPATH) $(TRANSLATE) -O2 --output $@ psota/targetpsota.py

psota-Ojit: $(PYTHON_SOURCES)
	PYTHONPATH=$(PYPYPATH) $(TRANSLATE) -Ojit --output $@ psota/targetpsota.py

clean:
	-rm -f psota-O2 psota-Ojit

repl:
	PYTHONPATH=$(PYPYPATH) $(RLWRAP) $(PYTHON) psota/targetpsota.py ./repl.clj

repl-Ojit: psota-Ojit
	$(RLWRAP) ./psota-Ojit ./repl.clj

repl-O2: psota-O2
	$(RLWRAP) ./psota-O2 ./repl.clj

check: psota-O2
	./psota-O2 test.clj

tarball: $(PACKAGE).tar.xz

$(PACKAGE).tar.xz: psota-Ojit README.md $(CLJ_SOURCES)
	test -d ./.git
	test "$(REVISION)"
	test "$(PACKAGE)"
	rm -rf ./$(PACKAGE)*
	mkdir $(PACKAGE)
	cp $(CLJ_SOURCES) README.md $(PACKAGE)/
	cp $< $(PACKAGE)/psota
	strip $(PACKAGE)/psota
	tar -cf $(PACKAGE).tar $(PACKAGE)/*
	xz --x86 --lzma2 $(PACKAGE).tar
	rm -rf ./$(PACKAGE)
