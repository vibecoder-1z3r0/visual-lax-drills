# Visual Lax Drills. The shipped artifact is dist/index.html (open it straight from disk) plus the
# dist/takes/ folder with the extra seeds, which the page loads only when one is picked.
PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
DENO ?= $(if $(wildcard .venv/bin/deno),.venv/bin/deno,deno)

SOURCES := $(shell find src icons-custom -type f 2>/dev/null) scripts/build.py

.PHONY: build lint test clean setup screenshots session-log hooks serve choreography

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

screenshots: build ## rebuild docs/screenshots/ for the README (commit the result)
	$(PY) scripts/screenshots.py

choreography:     ## regenerate the generated drill data and src/takes/ from scripts/choreography.py
	$(PY) scripts/choreography.py

serve: dist/index.html ## serve dist/ at http://127.0.0.1:8000 (the page also opens straight from disk)
	cd dist && $(abspath $(PY)) -m http.server 8000 --bind 127.0.0.1

session-log:      ## write this session's timing log to session-logs/ (the pre-commit hook runs this)
	$(PY) scripts/session_timing.py --header scripts/session_log_header.md --out-dir session-logs

hooks:            ## use scripts/hooks as this checkout's git hooks (setup does this)
	git config core.hooksPath scripts/hooks

setup:            ## install the dev tooling (Python only) and the Playwright browser
	python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
	.venv/bin/python -m playwright install chromium
	$(MAKE) hooks

clean:
	rm -rf dist test-artifacts
