# MIT Licence: Copyright (c) 2025 Baya Systems <https://bayasystems.com>
#
# Purple install and test
# =========================
#

# there can be multiple tst directories
# each must contain a run.py which takes the command-line options used below
# each test is a python module named xyz_test.py
# test names must be different even between tst directories
# use a vq-testname target to get STDOUT and QUICK (very common usage)

TEST_LIST_PY := $(wildcard tst*/*_test.py)
TEST_LIST := $(subst _test,,$(basename $(notdir $(TEST_LIST_PY))))
run_script = $(subst $(1)_test,run,$(filter tst%/$(1)_test.py,$(TEST_LIST_PY)))


all: $(TEST_LIST)

list-tests:
	@echo $(TEST_LIST)

clean:
	rm -fr $(VENV)
	rm -fr tst*/__pycache__
	rm -fr src/purple/__pycache__


# command-line options for a test run
STDOUT ?= /dev/null      ## or stdout or a filename
KEEP_GOING ?= 0          ## or 1
QUICK ?= 0               ## or 1


# tools
PYTHON ?= python
VENV_PYTHON = . $(VENV_ACTIVATE) && $(PYTHON)

PIP ?= pip3
VENV_PIP = . $(VENV_ACTIVATE) && $(PIP)


# files used as dependencies and install destinations
SOURCES := $(wildcard src/purple/*.py)

VENV ?= .venv
VENV_ACTIVATE := $(VENV)/bin/activate
VENV_WITH_PURPLE := $(VENV)/purple_installed


# rules for running each test; needs purple installed; needs a venv
$(TEST_LIST): $(VENV_WITH_PURPLE)
	@$(VENV_PYTHON) $(call run_script,$@) --test_name $@ --keep_going $(KEEP_GOING) --stdout $(STDOUT) --quick $(QUICK)

$(VENV_WITH_PURPLE): $(VENV_ACTIVATE) $(SOURCES)
	$(VENV_PIP) install --force-reinstall .
	touch $@

$(VENV_ACTIVATE):
	rm -fr $(VENV)
	$(PYTHON) -m venv $(VENV)


# vq-testname targets - convenient way to turn on stdout and quick options
VQ_TEST_LIST := $(foreach test,$(TEST_LIST),vq-$(test))

$(VQ_TEST_LIST): QUICK = 1
$(VQ_TEST_LIST): STDOUT = stdout
$(VQ_TEST_LIST): vq-%: %


# because pip has trouble without an internet connection
hack-install:
		cp -fr src/purple $(VENV)/lib/python*/site-packages/
		touch $(VENV_WITH_PURPLE)


# run python interactively
interact: $(VENV_WITH_PURPLE)
	@$(VENV_PYTHON)
