# Gordon Gekko MCP Server Setup

This guide walks through creating a minimal [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server around Gordon Gekko's toolchain and wiring it into ChatGPT connectors while running everything locally. Follow the sections in order; each step builds on the previous one.

## 1. Prerequisites

- **Python** 3.11 or 3.12.
- **Node.js** 18+ (only needed if you plan to use a tunnelling proxy such as `npm` packages; not required for local-only testing).
- A **ChatGPT** account with access to *Connectors → Development mode*.
- CoinGecko has public endpoints, so **no API keys** are needed, but outbound HTTPS access is required when the tools query CoinGecko.

> 💡 These instructions assume you are working inside the cloned `gordon-gekko` repository and have the `PYTHONPATH` set to `src` when executing project modules.

## 2. Create a Python environment

```bash
cd /path/to/gordon-gekko
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Install MCP tooling
pip install fastmcp
```

`fastmcp` ships both a Python SDK and handy CLI commands for running and inspecting MCP servers.

## 3. Write a minimal MCP server

Create `tools/mcp_server.py` with the following contents:

```python
"""Expose Gordon Gekko tools over Model Context Protocol."""

from __future__ import annotations

import asyncio
import pathlib
import sys
from typing import Any, Dict

# Ensure the local src/ directory is importable when the server runs via fastmcp
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fastmcp import FastMCP
from fastmcp.server import Context

from gekko.agents.interactive import GekkoAgent

server = FastMCP("gordon-gekko")
agent = GekkoAgent()


async def _dispatch(tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
    response = await agent.dispatch(tool, params)
    if response.get("status") != "ok":
        error = response.get("error", {})
        message = error.get("message", "Unknown tool failure")
        raise RuntimeError(f"{tool} failed: {message}")
    return response["data"]


@server.tool(name="list_tickers", description="List normalized exchange tickers for a coin")
async def list_tickers(
    ctx: Context,
    *,
    coin: str,
    vs: str = "usd",
    pages: int = 1,
    min_trust: str = "yellow",
    include_risky: bool = False,
    min_volume: float | None = None,
) -> Dict[str, Any]:
    """Expose the list_tickers tool via MCP."""
    await ctx.info(f"Fetching tickers for {coin}/{vs}")
    return await _dispatch(
        "list_tickers",
        {
            "coin": coin,
            "vs": vs,
            "pages": pages,
            "min_trust": min_trust,
            "include_risky": include_risky,
            "min_volume": min_volume,
        },
    )


@server.tool(name="find_arbitrage", description="Compute cross-exchange arbitrage spreads")
async def find_arbitrage(
    ctx: Context,
    *,
    coin: str,
    vs: str = "usd",
    pages: int = 1,
    min_trust: str = "yellow",
    include_risky: bool = False,
    min_volume: float | None = None,
    min_spread_pct: float = 1.0,
    top_n: int = 5,
    buy_fee_pct: float = 0.0,
    sell_fee_pct: float = 0.0,
    buy_slippage_pct: float = 0.0,
    sell_slippage_pct: float = 0.0,
    transfer_fee_vs: float = 0.0,
    notional_vs: float = 1000.0,
    latency_risk_buffer_pct: float = 0.0,
) -> Dict[str, Any]:
    """Expose the arbitrage helper via MCP."""
    await ctx.info(f"Scanning arbitrage opportunities for {coin}/{vs}")
    return await _dispatch(
        "find_arbitrage",
        {
            "coin": coin,
            "vs": vs,
            "pages": pages,
            "min_trust": min_trust,
            "include_risky": include_risky,
            "min_volume": min_volume,
            "min_spread_pct": min_spread_pct,
            "top_n": top_n,
            "buy_fee_pct": buy_fee_pct,
            "sell_fee_pct": sell_fee_pct,
            "buy_slippage_pct": buy_slippage_pct,
            "sell_slippage_pct": sell_slippage_pct,
            "transfer_fee_vs": transfer_fee_vs,
            "notional_vs": notional_vs,
            "latency_risk_buffer_pct": latency_risk_buffer_pct,
        },
    )


# Alias used by fastmcp run/inspect auto-discovery
mcp = server


if __name__ == "__main__":
    # Allow running directly for smoke tests.
    asyncio.run(
        server.run_stdio()
    )
```

Key details:

- `FastMCP` automatically derives the JSON schema for each tool from the function signature and docstring.
- The helper `_dispatch` reuses Gordon Gekko's existing `GekkoAgent` to avoid duplicating validation logic.
- The `Context` parameter gives access to MCP logging so tool calls show progress inside clients.
- The module-level `mcp` alias lets `fastmcp run tools/mcp_server.py` locate the server object automatically.

## 4. Sanity-check the server locally

1. **Run the server over HTTP** (recommended for ChatGPT connectors):

   ```bash
   source .venv/bin/activate
   PYTHONPATH=src fastmcp run tools/mcp_server.py --transport http --host 127.0.0.1 --port 8765
   ```

   You should see the FastMCP banner confirming the server is listening at `http://127.0.0.1:8765/mcp/`.

2. **Inspect the tool manifest** from another terminal:

   ```bash
   source .venv/bin/activate
   fastmcp inspect http://127.0.0.1:8765
   ```

   The inspector prints the `list_tickers` and `find_arbitrage` schema exactly as exposed by Gordon Gekko. If inspection fails, double-check that the server is running and that `PYTHONPATH=src` was exported in the server process.

3. **Optional – run with stdin/stdout transport** for debugging:

   ```bash
   PYTHONPATH=src fastmcp run tools/mcp_server.py --transport stdio
   ```

   This matches the expectations of MCP-native CLIs and the provided `gekko.cli agent` command.

## 5. Generate a ChatGPT connector definition

ChatGPT’s development connectors expect an `mcp.json` manifest describing how to launch your server. FastMCP can generate one for you:

```bash
source .venv/bin/activate
fastmcp install mcp-json tools/mcp_server.py \
  --name "Gordon Gekko (local)" \
  --env PYTHONPATH=$(pwd)/src \
  > ./tools/gordon-gekko.mcp.json
```

The resulting file resembles:

```json
{
  "mcpServers": {
    "Gordon Gekko (local)": {
      "command": "/full/path/to/.venv/bin/python",
      "args": [
        "-m",
        "fastmcp",
        "run",
        "tools/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/full/path/to/gordon-gekko/src"
      },
      "transport": {
        "type": "stdio"
      }
    }
  }
}
```

Feel free to switch the transport to HTTP if you prefer, but stdio works well when ChatGPT spawns the process directly on your machine.

## 6. Enable ChatGPT connectors (development mode)

1. Open [chat.openai.com](https://chat.openai.com/) and sign in.
2. Navigate to **Settings → Connectors**.
3. Toggle **Development mode** on. (If you do not see the toggle, ask for access to connectors beta.)
4. In the Development section, choose **Add local connector** and upload the `tools/gordon-gekko.mcp.json` file created above.
5. ChatGPT will register the connector and show its status as *stopped* until you launch the server.

## 7. Launch and test the connector

1. Start the MCP server if it is not already running:

   ```bash
   source .venv/bin/activate
   PYTHONPATH=src fastmcp run tools/mcp_server.py --transport stdio
   ```

   Leave this process running; ChatGPT will connect to it on demand.

2. Return to ChatGPT, open a new conversation, and choose the **Connectors** tab.
3. Select **Gordon Gekko (local)**. ChatGPT will spawn the server using the manifest and list the available tools in the sidebar.
4. Send a prompt such as “*List the latest bitcoin tickers in USD*.” ChatGPT should call the `list_tickers` tool and display the response streamed from the MCP server.
5. Try “*Show arbitrage opportunities for ethereum over the last two pages*.” The conversation transcript will include the `find_arbitrage` invocation and results.

## 8. Troubleshooting tips

- **Module not found**: Ensure `PYTHONPATH` includes the repository’s `src/` directory in any process running `mcp_server.py`.
- **SSL errors / HTTP 429**: CoinGecko enforces rate limits. Wait a minute or reduce the `pages` parameter during testing.
- **ChatGPT cannot reach the server**: Verify that the manifest transport matches the server you launched (stdio vs HTTP). For HTTP transport, confirm that firewalls allow the chosen port.
- **Connector stuck in “Starting”**: Stop the server, remove the connector in ChatGPT, and import the manifest again. Inspect the `fastmcp run` output for tracebacks.

## 9. Next steps

- Add additional tools by extending `tools/mcp_server.py` and reloading the connector.
- Enable HTTPS or reverse proxies if you plan to expose the server beyond a development network.
- Use `fastmcp dev tools/mcp_server.py` to launch the MCP Inspector UI for interactive testing before involving ChatGPT.

With these steps you now have a locally hosted MCP server that surfaces Gordon Gekko’s crypto-market tooling and a reproducible way to wire it into ChatGPT connectors while developing on your own machine.
