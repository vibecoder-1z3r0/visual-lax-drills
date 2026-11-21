# Visual Lax Drills. The shipped artifact is a single dist/index.html (open it straight from disk).
PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
DENO ?= $(if $(wildcard .venv/bin/deno),.venv/bin/deno,deno)

SOURCES := $(shell find src icons-custom -type f 2>/dev/null) scripts/build.py

.PHONY: build lint test clean setup

# CI runs these three, in this order, as separate steps: make build, make lint, make test.
# lint and test use the built page, so they only rebuild it if it is missing or out of date.

build:            ## always rebuild dist/index.html from src/
	$(PY) scripts/build.py

dist/index.html: $(SOURCES)
	$(PY) scripts/build.py

lint: dist/index.html ## deno lint (JS), HTML check, ruff (Python)
	$(DENO) lint
	$(PY) scripts/lint_html.py
	$(PY) -m ruff check scripts tests
	$(PY) -m ruff format --check scripts tests

test: dist/index.html ## run the Playwright suite against dist/index.html
	$(PY) -m pytest

setup:            ## install the dev tooling (Python only) and the Playwright browser
	python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
	.venv/bin/python -m playwright install chromium

clean:
	rm -rf dist test-artifacts
