# ChallengeMap developer tasks. Run `make help` for the list.

.PHONY: help venv install dev api web-install web-dev web-build test backup lint-api

# Local development uses 3.13 (.venv313); CI runs the same suite on 3.12.
PYTHON ?= py -3.13
VENV ?= .venv313

help:
	@echo "venv          create the supported $(VENV) environment"
	@echo "install       install requirements/dev.txt into $(VENV)"
	@echo "dev           run API :8000 and web :3000 together (needs .env)"
	@echo "api           run only the API on :8000"
	@echo "web-install   install frontend dependencies"
	@echo "web-dev       run the Next.js dev server on :3000"
	@echo "web-build     production build of the frontend"
	@echo "test          run the Python test suite"
	@echo "backup        integrity-checked SQLite copy under backups/"
	@echo "lint-api      byte-compile the Python sources"

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(VENV)/Scripts/python.exe -m pip install -r requirements/dev.txt

# One command for a fresh clone: `cp .env.example .env` once, then `make dev`.
# scripts/dev.py reads .env, waits for /api/v1/health and starts the web app.
dev:
	@$(VENV)/Scripts/python.exe scripts/dev.py

api:
	@if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	$(VENV)/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

web-install:
	cd frontend && npm install

web-dev:
	@if [ -f .env ]; then set -a; . ./.env; set +a; fi; cd frontend && npm run dev

web-build:
	@if [ -f .env ]; then set -a; . ./.env; set +a; fi; cd frontend && npm run build

# -t . makes `tests` a package: tests/__init__.py must run before any test
# module imports the app, because it switches the rate limiter off.
test:
	$(VENV)/Scripts/python.exe -m unittest discover -s tests -t .

backup:
	@$(VENV)/Scripts/python.exe scripts/backup_db.py

lint-api:
	$(VENV)/Scripts/python.exe -m compileall -q api src scripts
