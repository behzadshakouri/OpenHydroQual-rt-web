.PHONY: venv install test test-fast test-api test-worker

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
DEPS_STAMP := $(VENV)/.deps-installed
DEV_REQUIREMENTS := requirements-dev.txt apps/api/requirements.txt apps/worker/requirements.txt

$(PYTHON):
	python -m venv $(VENV)

venv: $(PYTHON)

$(DEPS_STAMP): $(DEV_REQUIREMENTS) | $(PYTHON)
	$(PIP) install -r requirements-dev.txt
	touch $(DEPS_STAMP)

install: $(DEPS_STAMP)

test: $(DEPS_STAMP)
	$(PYTEST) -q tests

test-fast: $(DEPS_STAMP)
	$(PYTEST) -q tests/test_ohquery_adapter.py tests/test_worker_task.py

test-api: $(DEPS_STAMP)
	$(PYTEST) -q tests/test_api_contract.py

test-worker: $(DEPS_STAMP)
	$(PYTEST) -q tests/test_worker_task.py
