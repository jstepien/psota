PYPYPATH ?= ../pypy
PYTHON ?= python2
TRANSLATE = $(PYTHON) $(PYPYPATH)/rpython/translator/goal/translate.py
ifeq ($(shell rlwrap -v 2> /dev/null | grep rlwrap -c), 1)
	RLWRAP = rlwrap
else
	RLWRAP =
endif

.PHONY: all clean repl-O2 repl-Ojit repl

all: psota-O2

psota-O2:
	PYTHONPATH=$(PYPYPATH) $(TRANSLATE) -O2 --output $@ psota/targetpsota.py

psota-Ojit:
	PYTHONPATH=$(PYPYPATH) $(TRANSLATE) -Ojit --output $@ psota/targetpsota.py

clean:
	-rm -f psota-O2 psota-Ojit

repl:
	PYTHONPATH=$(PYPYPATH) $(RLWRAP) $(PYTHON) psota/targetpsota.py ./repl.clj

repl-Ojit: psota-Ojit
	$(RLWRAP) ./psota-Ojit ./repl.clj

repl-O2: psota-O2
	$(RLWRAP) ./psota-O2 ./repl.clj
