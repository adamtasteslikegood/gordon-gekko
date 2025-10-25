# Gordon Gekko MCP Server & ChatGPT Development Connector Guide

This guide walks through spinning up the Gordon Gekko tools as a local Model Context Protocol (MCP) server and wiring that server into ChatGPT connectors while working in "development mode".

## Prerequisites

1. **Python 3.11+** and a POSIX shell (macOS, Linux, or WSL).
2. **Git** for cloning the repository.
3. (Optional for ChatGPT tooling) An **OpenAI API key** available via the `OPENAI_API_KEY` environment variable if you plan to use the bundled GPT-5 CLI for quick smoke tests.

> Tip: All commands are expected to be executed from the project root. On Windows, run them inside WSL for the best experience.

## 1. Set up the project locally

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/<your-org>/gordon-gekko.git
   cd gordon-gekko
   ```

2. Create and activate an isolated environment, then install the runtime dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   These packages include FastAPI, httpx, jsonschema, and all helpers needed by the agent dispatcher and CoinGecko integrations. 【F:requirements.txt†L1-L14】

3. Keep the repository root on your `PYTHONPATH` when executing commands without installing the package. The examples below export `PYTHONPATH=src`, matching the development workflow documented in the README. 【F:README.md†L8-L27】

## 2. Run the MCP server locally

The Gordon Gekko MCP server is provided by the `gekko.cli agent` subcommand. It exposes the CoinGecko-derived tools over stdin/stdout using the JSON envelopes required by MCP clients. 【F:src/gekko/cli.py†L118-L208】【F:src/gekko/agents/interactive.py†L12-L75】

1. In one terminal, activate your virtual environment (if not already active) and launch the server:

   ```bash
   export PYTHONPATH=src
   python -m gekko.cli agent
   ```

2. On start-up the process emits a `ready` payload describing the available tools. You should see output similar to:

   ```json
   {"status": "ready", "tools": [{"type": "function", "function": {"name": "list_tickers", "description": "List normalized exchange tickers for a specific coin", "parameters": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}}}, ...]}
   ```

   The tool metadata is generated from the JSON Schemas defined in `gekko/agents/tools.py`. 【F:src/gekko/agents/tools.py†L11-L118】

3. Keep the process running; it listens for line-delimited JSON requests on stdin. Each request must supply a `tool` name, optional `request_id`, and an `arguments` object.

## 3. Send a quick manual request (optional smoke test)

You can exercise the MCP server with standard shell utilities by piping JSON into the process:

```bash
printf '%s\n' '{"request_id": "demo-1", "tool": "list_tickers", "arguments": {"coin": "bitcoin", "vs": "usd"}}' | \
  python -m gekko.cli agent
```

In another workflow, keep the server running and use a second terminal with `socat`, `tee`, or a lightweight script that opens the server process and writes JSON requests. Successful responses include `status: "ok"` and the normalized market payload; validation or HTTP errors are returned with machine-readable error types. 【F:src/gekko/cli.py†L209-L308】

## 4. Prepare ChatGPT connectors (development mode)

With the server running locally, you can connect it to ChatGPT by registering a development connector that spawns the MCP process on demand.

1. **Enable development mode**
   - Open ChatGPT in your browser.
   - Navigate to **Settings → Features → Connectors** and toggle **Development mode** on. This unlocks local connectors that run only for your account.

2. **Create a connector entry**
   - Still in the Connectors panel, click **Add connector** and choose **Create from command** (or similar wording depending on the current UI).
   - Supply a name such as `Gordon Gekko (Local)` and point the command to the MCP server:

     ```text
     /absolute/path/to/.venv/bin/python -m gekko.cli agent
     ```

   - If the UI requests an argument array instead of a single string, enter:

     ```json
     ["/absolute/path/to/.venv/bin/python", "-m", "gekko.cli", "agent"]
     ```

   - Leave the environment field empty unless you need to set variables like `PYTHONPATH=src`. When required, add `PYTHONPATH=src` and any proxy variables that your network mandates.

3. **Save and test**
   - After saving, ChatGPT spins up the command in an isolated sandbox when the connector is used. Because the process speaks MCP over stdin/stdout, no additional HTTP ports are necessary.
   - Open a new chat, switch to **Development connectors**, and select the connector you just added. Ask a question like "Find arbitrage for bitcoin." The ChatGPT UI should display tool invocations that mirror the JSON exchanges handled by `GekkoAgent.dispatch`. 【F:src/gekko/agents/interactive.py†L26-L60】【F:src/gekko/agents/tools.py†L68-L118】

4. **Troubleshooting tips**
   - If ChatGPT reports that the connector exited immediately, verify the command path and that the virtual environment is activated (or use the absolute interpreter path inside `.venv/bin/python`).
   - Use `chat.openai.com`'s connector logs (available next to the connector entry) to review stdout/stderr. The server logs helpful validation messages through `logging`, so enabling `logging.basicConfig(level=logging.INFO)` before launching can aid debugging. 【F:src/gekko/cli.py†L176-L207】
   - Ensure outbound internet access to CoinGecko is permitted from the machine running the connector; the tools make live HTTP requests via `httpx`. 【F:src/gekko/services/coingecko.py†L1-L160】

## 5. Optional: bridge to the GPT-5 CLI for local development

If you would rather test the toolchain without ChatGPT, the repository bundles a helper CLI that calls the OpenAI Responses API and automatically fulfils tool invocations using the same MCP dispatcher.

1. Export your API key and run the CLI:

   ```bash
   export OPENAI_API_KEY=sk-...
   export PYTHONPATH=src
   python -m gekko.cli gpt5-agent --model gpt-5.1-mini
   ```

2. The CLI prints the available tool names and streams responses while invoking the underlying MCP handlers via `generate_response_with_tools`. This mimics the development connector workflow end-to-end. 【F:src/gekko/cli.py†L209-L276】【F:src/gekko/ai/responses.py†L1-L205】

## 6. Clean shutdown

When you are done, stop the MCP server with `Ctrl+C`. Any active ChatGPT development sessions tied to the connector will detect the termination and mark the tool as unavailable until the command is started again.

You now have a repeatable process for spinning up Gordon Gekko as a local MCP server and iterating on ChatGPT integrations in development mode.
