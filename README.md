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
- `src/gekko/ai/tools.py` – GPT tool metadata and handlers powered by Gordon Gekko services.
- `tests/` – tests for health and arbitrage helpers.

## AI assistants

Gordon Gekko exposes its core market and arbitrage routines as GPT-compatible tools. Retrieve the JSON function manifests via `gekko.list_tools()` and feed them to GPT-5 (or the GPT Functions API) alongside the Python handlers for invocation:

```python
from gekko import list_tools

tools = list_tools()

# Example with the GPT-5 client (pseudo-code)
response = gpt5.chat.completions.create(
    model="gpt-5.1",
    messages=[
        {"role": "user", "content": "Find arbitrage for bitcoin."},
    ],
    tools=tools,
)

print(response.choices[0])
```

Each tool advertises validated parameters and is backed by the same logic used by the REST and CLI interfaces, so the agent receives production-grade market data without additional plumbing.

## Notes

- This project calls the public CoinGecko API; no API key required.
- Arbitrage calculations are heuristic and ignore fees, slippage, latency, and transfer times. Not financial advice.
