# Repository Map

Generated: 2025-10-24T22:28:49.563169+00:00

## Overview
- Total modules: 36
- Total LOC (approx): 3446

## Directory Tree (depth ≤ 3)
```
- AGENTS.md (files: 1, loc: 33)
- README.md (files: 1, loc: 87)
- main.py (files: 1, loc: 11)
- pytest.ini (files: 1, loc: 2)
- src (files: 18, loc: 1885)
  - src/gekko (files: 18, loc: 1885)
    - src/gekko/__init__.py (files: 1, loc: 3)
    - src/gekko/agents (files: 3, loc: 227)
    - src/gekko/ai (files: 3, loc: 669)
    - src/gekko/analysis (files: 2, loc: 79)
    - src/gekko/app.py (files: 1, loc: 10)
    - src/gekko/cli.py (files: 1, loc: 454)
    - src/gekko/routers (files: 4, loc: 205)
    - src/gekko/services (files: 3, loc: 238)
- tests (files: 12, loc: 678)
  - tests/conftest.py (files: 1, loc: 6)
  - tests/fixtures (files: 4, loc: 22)
    - tests/fixtures/sample_project (files: 4, loc: 22)
  - tests/test_agent.py (files: 1, loc: 122)
  - tests/test_ai_tools.py (files: 1, loc: 139)
  - tests/test_arbitrage.py (files: 1, loc: 99)
  - tests/test_arbitrage_fees.py (files: 1, loc: 39)
  - tests/test_health.py (files: 1, loc: 7)
  - tests/test_repo_mapper.py (files: 1, loc: 37)
  - tests/test_responses_agent.py (files: 1, loc: 207)
- tools (files: 2, loc: 750)
  - tools/__init__.py (files: 1, loc: 1)
  - tools/repo_mapper.py (files: 1, loc: 749)
```

## Language Breakdown
| Language | LOC | Files |
| --- | ---: | ---: |
| INI | 2 (0.1%) | 1 (2.8%) |
| Markdown | 120 (3.5%) | 2 (5.6%) |
| Python | 3324 (96.5%) | 33 (91.7%) |

## Packages
- **gekko** (lib) — path: `src/gekko`, deps: none
- **main** (app) — path: `main.py`, deps: none
- **tests** (lib) — path: `tests`, deps: gekko, gekko, gekko, gekko, tools, gekko, gekko, gekko
- **tools** (lib) — path: `tools`, deps: none

## Dependency Graph (top edges)
```mermaid
flowchart LR
    "tests/test_ai_tools.py" --> "src/gekko/ai/__init__.py"
    "tests/test_arbitrage_fees.py" --> "src/gekko/services/arbitrage.py"
    "tests/test_arbitrage.py" --> "src/gekko/services/arbitrage.py"
    "tests/test_responses_agent.py" --> "src/gekko/ai/responses.py"
    "tests/test_repo_mapper.py" --> "tools/__init__.py"
    "tests/test_health.py" --> "src/gekko/app.py"
    "tests/test_agent.py" --> "src/gekko/agents/interactive.py"
    "tests/test_agent.py" --> "src/gekko/cli.py"
```

### Hotspots

- Largest modules: tools/repo_mapper.py (749 LOC), src/gekko/cli.py (454 LOC), src/gekko/ai/tools.py (434 LOC), src/gekko/ai/responses.py (218 LOC), tests/test_responses_agent.py (207 LOC)
- Most dependents: src/gekko/services/arbitrage.py (2), src/gekko/cli.py (1), src/gekko/app.py (1), src/gekko/ai/__init__.py (1), src/gekko/ai/responses.py (1)
- Modules without tests: pytest.ini, main.py, README.md, AGENTS.md, src/gekko/cli.py

## Key Insights & Recommended Refactors
- Break down the largest modules (src/gekko/cli.py, src/gekko/ai/tools.py, src/gekko/ai/responses.py) into smaller units.
- Review complex modules for maintainability: src/gekko/cli.py, src/gekko/ai/tools.py, src/gekko/routers/arbitrage.py
- Add tests for modules without coverage, starting with pytest.ini, main.py, README.md
- Ensure IO-heavy modules have error handling and timeouts: src/gekko/agents/interactive.py, src/gekko/services/coingecko.py, tools/repo_mapper.py
- Resolve outstanding annotations (TODO/FIXME) in tools/repo_mapper.py, tests/fixtures/sample_project/src/sample_pkg/core.py