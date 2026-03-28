.PHONY: venv install test test-api test-worker

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

$(PYTHON):
	python -m venv $(VENV)

venv: $(PYTHON)

install: $(PYTHON)
	$(PIP) install -r requirements-dev.txt

test: install
	$(PYTEST) -q tests

test-api: install
	$(PYTEST) -q tests/test_api_contract.py

test-worker: install
	$(PYTEST) -q tests/test_worker_task.py
