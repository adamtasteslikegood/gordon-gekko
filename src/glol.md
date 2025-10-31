* 44471c3 - (HEAD -> fixed-FEAT-cli-gpt5-agent-interactive, origin/fixed-FEAT-cli-gpt5-agent-interactive) - Refactor tool API payloads: rename `function` to flat structure. - Add `_normalize_block_type` for consistent content handling. - Introduce `resolve_coin_id` for flexible coin ID resolution. - Update tests and CLI to use `resolve_coin_id` for consistency. - Bug fixes and logging enhancements in `coingecko` service. (29 minutes ago) <adamtasteslikegood>
| 
|  README.md                       |   4 +-
|  src/gekko/agents/tools.py       |  13 +++--
|  src/gekko/ai/responses.py       | 104 ++++++++++++++++++++++++++++++++------
|  src/gekko/cli.py                |   9 ++--
|  src/gekko/services/coingecko.py |  65 ++++++++++++++++++++++++
|  tests/test_agent.py             |   2 +-
|  tests/test_responses_agent.py   |  84 +++++++++++++++++++++++++-----
|  7 files changed, 237 insertions(+), 44 deletions(-)
* 7a6ca23 - - Update `.gitignore` to exclude sensitive API key file - Change default `uvicorn` port in `main.py` to 7000 - Fix CLI subcommand parser method (4 days ago) <adamtasteslikegood>
| 
|  .gitignore       | 1 +
|  main.py          | 2 +-
|  src/gekko/cli.py | 2 +-
|  3 files changed, 3 insertions(+), 2 deletions(-)
*   5f41561 - Merge pull request #5 from adamtasteslikegood/codex/review-code-changes (5 days ago) <adam schoen>
|\  
| * 356228e - (origin/codex/review-code-changes) test: cover responses tool argument normalization (5 days ago) <adam schoen>
|/  
|   
|    src/gekko/ai/responses.py     | 37 +++++++++++-----
|    tests/test_responses_agent.py | 93 +++++++++++++++++++++++++++++++++++++++
|    2 files changed, 120 insertions(+), 10 deletions(-)
*   12c11a2 - Merge pull request #4 from adamtasteslikegood/codex/implement-interactive-gpt-5-agent-feature (7 days ago) <adam schoen>
|\  
| * c9b3b3a - (origin/codex/implement-interactive-gpt-5-agent-feature) feat: add gpt5 responses agent (7 days ago) <adam schoen>
|/  
|   
|    README.md                     |  22 +++-
|    requirements.txt              |   1 +
|    src/gekko/ai/__init__.py      |  16 ++-
|    src/gekko/ai/responses.py     | 254 ++++++++++++++++++++++++++++++++++++++
|    src/gekko/cli.py              |  41 ++++++
|    tests/test_responses_agent.py | 151 ++++++++++++++++++++++
|    6 files changed, 478 insertions(+), 7 deletions(-)
*   88a031b - Merge pull request #3 from adamtasteslikegood/codex/implement-gekkoagent-with-cli-support (7 days ago) <adam schoen>
|\  
| * c6b04d2 - (origin/codex/implement-gekkoagent-with-cli-support) feat: format agent tool metadata for function calling (7 days ago) <adam schoen>
| | 
| |  README.md                       |  29 ++++++
| |  requirements.txt                |   1 +
| |  src/gekko/agents/__init__.py    |   5 +
| |  src/gekko/agents/interactive.py |  72 ++++++++++++++
| |  src/gekko/agents/tools.py       | 186 ++++++++++++++++++++++++++++++++++++
| |  src/gekko/cli.py                | 114 +++++++++++++++++++++-
| |  tests/test_agent.py             | 147 ++++++++++++++++++++++++++++
| |  7 files changed, 553 insertions(+), 1 deletion(-)
* |   efd3c11 - Merge pull request #2 from adamtasteslikegood/codex/update-compute_opportunities-and-add-test (7 days ago) <adam schoen>
|\ \  
| * | da5c4f6 - (origin/codex/update-compute_opportunities-and-add-test) fix: filter arbitrage pairs per market (7 days ago) <adam schoen>
| |/  
| |   
| |    src/gekko/services/arbitrage.py | 17 +++++++-
| |    tests/test_arbitrage.py         | 78 +++++++++++++++++++++++++++++++++++
| |    2 files changed, 93 insertions(+), 2 deletions(-)
* |   fa5a2a7 - Merge pull request #1 from adamtasteslikegood/codex/add-tool-specification-module-and-async-wrappers (7 days ago) <adam schoen>
|\ \  
| |/  
|/|   
| * d765eab - (origin/codex/add-tool-specification-module-and-async-wrappers) feat: expose GPT tool specs for AI agents (7 days ago) <adam schoen>
|/  
|   
|    README.md                |  24 +++
|    src/gekko/__init__.py    |   5 +-
|    src/gekko/ai/__init__.py |   5 +
|    src/gekko/ai/tools.py    | 470 +++++++++++++++++++++++++++++++++++++++++++
|    tests/test_ai_tools.py   | 188 +++++++++++++++++
|    5 files changed, 691 insertions(+), 1 deletion(-)
* 5f45777 - Added AGENTS.md. Local codex activity modified main.py (13 days ago) <adamtasteslikegood>
| 
|  AGENTS.md | 46 ++++++++++++++++++++++++++++++++++++++++++++++
|  1 file changed, 46 insertions(+)
* 32c7506 - ci: add GitHub Actions workflow for tests (3.11–3.13) and Docker build (2 weeks ago) <adamtasteslikegood>
| 
|  .github/workflows/ci.yml | 49 ++++++++++++++++++++++++++++++++++++++++++++++
|  1 file changed, 49 insertions(+)
* 2c6697c - chore: add Dockerfile and .dockerignore; document Docker build/run and CLI usage in README (2 weeks ago) <adamtasteslikegood>
| 
|  .dockerignore | 14 ++++++++++++++
|  Dockerfile    | 25 +++++++++++++++++++++++++
|  README.md     | 22 ++++++++++++++++++++++
|  3 files changed, 61 insertions(+)
* 28aa27e - feat: FastAPI crypto API with CoinGecko integration, arbitrage helpers, and CLI (incl. interactive mode)\n\n- App + health + market endpoints\n- CoinGecko services (prices, markets, exchanges, tickers)\n- Arbitrage normalization and opportunity calculation\n- CLI subcommands + interactive menu\n- Tests and README updates (2 weeks ago) <adamtasteslikegood>
| 
|  .gitignore                      |  37 ++++
|  README.md                       |  45 ++++-
|  main.py                         |  16 ++
|  requirements.txt                |   6 +
|  src/gekko/__init__.py           |   1 +
|  src/gekko/analysis/__init__.py  |   1 +
|  src/gekko/analysis/arbitrage.py |  95 ++++++++++
|  src/gekko/app.py                |  17 ++
|  src/gekko/cli.py                | 357 ++++++++++++++++++++++++++++++++++++++
|  src/gekko/routers/__init__.py   |   1 +
|  src/gekko/routers/arbitrage.py  |  77 ++++++++
|  src/gekko/routers/health.py     |   9 +
|  src/gekko/routers/market.py     | 154 ++++++++++++++++
|  src/gekko/services/__init__.py  |   1 +
|  src/gekko/services/arbitrage.py | 184 ++++++++++++++++++++
|  src/gekko/services/coingecko.py |  86 +++++++++
|  tests/conftest.py               |  10 ++
|  tests/test_arbitrage.py         |  38 ++++
|  tests/test_arbitrage_fees.py    |  51 ++++++
|  tests/test_health.py            |  11 ++
|  20 files changed, 1195 insertions(+), 2 deletions(-)
* 5ae3045 - (origin/create-readme) Initial commit (1 year ago) <adamtasteslikegood>
  
   LICENSE   | 121 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
   README.md |   2 +
   2 files changed, 123 insertions(+)
