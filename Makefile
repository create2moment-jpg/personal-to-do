.PHONY: setup dev api web check test lint typecheck build backup doctor demo e2e

PY ?= .venv/bin/python
BIN := .venv/bin

setup:            ## create venv, install deps, install git hooks
	python3 -m venv .venv
	$(BIN)/pip install --require-hashes -r requirements-dev.lock
	$(BIN)/pip install --no-deps -e .
	cd apps/web && npm ci
	bash scripts/install-git-hooks.sh

api:              ## run the API on 127.0.0.1:8765
	$(BIN)/ppos serve

web:              ## run the Vite dev server (proxies /api to :8765)
	cd apps/web && npm run dev

build:            ## build the web UI so `ppos serve` serves it
	cd apps/web && npm run build

lint:
	$(BIN)/ruff check . && $(BIN)/ruff format --check .

typecheck:
	$(BIN)/mypy
	cd apps/web && npm run typecheck

test:
	$(BIN)/pytest
	cd apps/web && npm test

check: lint typecheck test   ## everything CI runs
	python3 scripts/check_repo_safety.py --all

demo:             ## synthetic showcase workspace in ~/PersonalProductivityDemo, then serve it
	$(BIN)/ppos --data-dir $(HOME)/PersonalProductivityDemo demo || true
	$(BIN)/ppos --data-dir $(HOME)/PersonalProductivityDemo serve

e2e:              ## browser tests against a throwaway demo workspace
	cd apps/web && npm run build && npx playwright test --trace off

backup:
	$(BIN)/ppos backup

doctor:
	$(BIN)/ppos doctor
