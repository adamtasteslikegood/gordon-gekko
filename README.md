# Gordon Gekko

Minimal FastAPI project for crypto stats (CoinGecko proxy).

## Quick Start

- Create a virtual environment and install deps:
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`

- Run the API:
  - `python main.py`
  - Visit `http://localhost:8000/docs` for Swagger UI.

- CLI (no install):
  - `PYTHONPATH=src python -m gekko.cli --help`
  - Examples:
    - `PYTHONPATH=src python -m gekko.cli tickers --coin bitcoin --vs usd --pages 2`
    - `PYTHONPATH=src python -m gekko.cli arbitrage --coin bitcoin --vs usd --pages 2 --min-spread-pct 1 --buy-fee-pct 0.1 --sell-fee-pct 0.1`
    - `PYTHONPATH=src python -m gekko.cli agent`

### Agent subcommand

The `agent` subcommand exposes Gordon Gekko tools over a JSON-based stdin/stdout protocol that can be connected to GPT-5 function calling or any automation framework capable of streaming JSON.

1. Start the agent:

   ```bash
   PYTHONPATH=src python -m gekko.cli agent
   ```

   The process writes an initial `ready` message describing the available tools using OpenAI's function-calling schema.

2. Send tool invocations as line-delimited JSON objects. Each request **must** provide `tool`, and may include an optional `request_id` for correlation:

   ```json
   {"request_id": "req-1", "tool": "list_tickers", "arguments": {"coin": "bitcoin", "vs": "usd"}}
   ```

3. Read responses from stdout. Successful results include `status: "ok"` and the tool payload; validation, HTTP, or runtime problems return machine-readable errors:

   ```json
   {"status": "ready", "tools": [{"type": "function", "function": {"name": "list_tickers", "description": "...", "parameters": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}}}]}
   {"request_id": "req-1", "tool": "list_tickers", "status": "ok", "data": {"count": 25, "tickers": [...]}}
   {"request_id": "req-2", "tool": "find_arbitrage", "status": "error", "error": {"type": "validation_error", "message": "'coin' is a required property"}}
   ```

External AI systems should maintain an open pipe to the process, inspect the `ready` handshake to learn tool schemas, and then stream requests/responses as needed.

## Docker

Step-by-step
- Build image:
  - `docker build -t gordon-gekko:latest .`
- Run API (port 8000):
  - `docker run --rm -p 8000:8000 --name gekko gordon-gekko:latest`
  - Open `http://localhost:8000/docs`
- Health check:
  - `curl http://localhost:8000/health`
- Simple price:
  - `curl 'http://localhost:8000/market/simple-price?ids=bitcoin&vs_currencies=usd'`
- Arbitrage example:
  - `curl 'http://localhost:8000/market/arbitrage?coin_id=bitcoin&vs_currency=usd&pages=2&min_spread_pct=1'`

CLI inside container
- TTY session (bash):
  - `docker run --rm -it --entrypoint bash gordon-gekko:latest`
  - Then run: `PYTHONPATH=/app/src python -m gekko.cli interactive`
- One-off run (non-interactive):
  - `docker run --rm -it --entrypoint python gordon-gekko:latest -m gekko.cli tickers --coin bitcoin --vs usd --pages 2`

## Endpoints

- `GET /health` – simple health check.
- Market data:
  - `GET /market/simple-price?ids=bitcoin,ethereum&vs_currencies=usd,eur`
  - `GET /market/supported-vs-currencies`
  - `GET /market/coins-markets?vs_currency=usd&ids=bitcoin,ethereum`
  - `GET /market/exchanges?per_page=100&page=1`
  - `GET /market/coin-tickers?coin_id=bitcoin&vs_currency=usd&pages=2` – normalized per-exchange prices for a coin
- Arbitrage helper:
  - `GET /market/arbitrage?coin_id=bitcoin&vs_currency=usd&min_spread_pct=1&pages=2` – compute top cross-exchange spreads with optional fees/slippage

## Layout

- `src/gekko/app.py` – FastAPI app factory and instance.
- `src/gekko/routers/` – route modules (`health`, `market`).
- `src/gekko/services/` – CoinGecko integration.
- `tests/` – tests for health and arbitrage helpers.

## Notes

- This project calls the public CoinGecko API; no API key required.
- Arbitrage calculations are heuristic and ignore fees, slippage, latency, and transfer times. Not financial advice.
