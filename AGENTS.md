# Repository Guidelines

## Project Structure & Module Organization
- Source lives under `src/gekko/`:
  - `app.py` (FastAPI app factory + `app`), `routers/` (API routes), `services/` (CoinGecko + arbitrage logic), `cli.py` (CLI + interactive mode).
- Entry point: `main.py` (starts Uvicorn; defaults to port `7000`).
- Tests in `tests/` (pytest). Docker assets: `Dockerfile`, `.dockerignore`. CI in `.github/workflows/ci.yml`.

## Build, Test, and Development Commands
- Install deps (recommended venv):
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
- Run API locally:
  - `python main.py` (serves `http://localhost:7000`)
  - Or: `PYTHONPATH=src uvicorn gekko.app:app --reload --port 7000`
- CLI examples:
  - `PYTHONPATH=src python -m gekko.cli tickers --coin bitcoin --vs usd --pages 2`
  - `PYTHONPATH=src python -m gekko.cli arbitrage --coin bitcoin --vs usd --min-spread-pct 1`
- Run tests:
  - `pytest -q`
- Docker:
  - `docker build -t gordon-gekko:latest .`
  - `docker run --rm -p 8000:8000 gordon-gekko:latest` (container exposes `8000`).

## Coding Style & Naming Conventions
- Python 3.11+; follow PEP 8 with 4‑space indentation and type hints.
- Modules and files: `snake_case`. Public functions/vars: `snake_case`; classes: `PascalCase`.
- Keep request/response handling in `routers/`; keep pure, testable logic in `services/`.
- Prefer small functions, explicit names, and docstrings for public functions.

## Testing Guidelines
- Framework: `pytest`. Place tests under `tests/` named `test_*.py` with functions `test_*`.
- Avoid real network calls; mock `httpx.AsyncClient` when exercising CoinGecko code.
- Use `tests/conftest.py` path setup; no need to set `PYTHONPATH` for tests.
- Add tests for new routers and services; keep them fast and deterministic.

## Commit & Pull Request Guidelines
- Use Conventional Commits (e.g., `feat:`, `fix:`, `chore:`, `ci:`) as in history.
- PRs should include:
  - Clear description and rationale, linked issues.
  - Before/after examples: `curl` for endpoints or CLI output.
  - Tests for new behavior and updates to `README.md` when user‑facing.

## Security & Configuration Tips
- No secrets required; respect CoinGecko rate limits. Keep HTTP timeouts (already set) and avoid adding blocking I/O in routes.
- When running from source, set `PYTHONPATH=src` for CLI or `uvicorn` commands.
