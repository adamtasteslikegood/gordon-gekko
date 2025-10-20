import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, TextIO

from .services.coingecko import get_coin_tickers
from .services.arbitrage import normalize_tickers, compute_opportunities
from .agents.interactive import GekkoAgent
from .ai.responses import run_gpt5_agent_cli


def _print_table(rows: List[List[str]]):
    if not rows:
        print("(no results)")
        return
    widths = [max(len(str(cell)) for cell in col) for col in zip(*rows)]
    for i, row in enumerate(rows):
        line = "  ".join(str(cell).ljust(widths[idx]) for idx, cell in enumerate(row))
        print(line)
        if i == 0:
            print("  ".join("-" * w for w in widths))


async def _fetch_normalized_tickers(
    *,
    coin_id: str,
    vs_currency: str,
    pages: int,
    min_trust: str,
    exclude_risky: bool,
    min_volume: Optional[float],
):
    all_tickers: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        payload = await get_coin_tickers(coin_id=coin_id, page=page)
        all_tickers.extend(payload.get("tickers", []))
    normalized = normalize_tickers(
        all_tickers,
        vs_currency=vs_currency,
        min_trust=min_trust,
        exclude_risky=exclude_risky,
        min_volume=min_volume,
    )
    return normalized


async def run_tickers(args: argparse.Namespace):
    tickers = await _fetch_normalized_tickers(
        coin_id=args.coin,
        vs_currency=args.vs,
        pages=args.pages,
        min_trust=args.min_trust,
        exclude_risky=not args.include_risky,
        min_volume=args.min_volume,
    )
    if args.json:
        print(json.dumps({"count": len(tickers), "tickers": tickers}, indent=2))
        return
    rows = [["Exchange", "Pair", f"Price({args.vs})", "Trust", "Volume"]]
    for t in tickers:
        rows.append(
            [
                t.get("exchange") or "?",
                t.get("pair") or "?",
                f"{t.get('price'):.8f}" if isinstance(t.get("price"), (int, float)) else str(t.get("price")),
                t.get("trust_score") or "?",
                f"{t.get('volume_vs'):.2f}" if isinstance(t.get("volume_vs"), (int, float)) else "",
            ]
        )
    _print_table(rows)


async def run_arbitrage(args: argparse.Namespace):
    tickers = await _fetch_normalized_tickers(
        coin_id=args.coin,
        vs_currency=args.vs,
        pages=args.pages,
        min_trust=args.min_trust,
        exclude_risky=not args.include_risky,
        min_volume=args.min_volume,
    )
    opps = compute_opportunities(
        tickers,
        min_spread_pct=args.min_spread_pct,
        top_n=args.top_n,
        buy_fee_pct=args.buy_fee_pct,
        sell_fee_pct=args.sell_fee_pct,
        buy_slippage_pct=args.buy_slippage_pct,
        sell_slippage_pct=args.sell_slippage_pct,
        transfer_fee_vs=args.transfer_fee_vs,
        notional_vs=args.notional_vs,
        latency_risk_buffer_pct=args.latency_risk_buffer_pct,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "coin": args.coin,
                    "vs": args.vs,
                    "params": {
                        "min_spread_pct": args.min_spread_pct,
                        "top_n": args.top_n,
                        "fees": {
                            "buy_fee_pct": args.buy_fee_pct,
                            "sell_fee_pct": args.sell_fee_pct,
                            "buy_slippage_pct": args.buy_slippage_pct,
                            "sell_slippage_pct": args.sell_slippage_pct,
                            "transfer_fee_vs": args.transfer_fee_vs,
                            "notional_vs": args.notional_vs,
                            "latency_risk_buffer_pct": args.latency_risk_buffer_pct,
                        },
                    },
                    "opportunities": opps,
                },
                indent=2,
            )
        )
        return
    rows = [
        [
            "BuyEx",
            "Buy",
            "SellEx",
            "Sell",
            "Raw%",
            "Net%",
            f"EstProfit({args.vs})",
        ]
    ]
    for o in opps:
        rows.append(
            [
                o["buy"]["exchange"],
                f"{o['buy']['price']:.8f}",
                o["sell"]["exchange"],
                f"{o['sell']['price']:.8f}",
                f"{o['raw_spread_pct']:.3f}",
                f"{o['net_spread_pct']:.3f}",
                f"{o['est_net_profit_vs']:.2f}",
            ]
        )
    _print_table(rows)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gekko",
        description="Gordon Gekko — CLI for market data and arbitrage scouting",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # Shared options helper
    def add_shared(sp):
        sp.add_argument("--coin", required=True, help="CoinGecko coin id, e.g., bitcoin")
        sp.add_argument("--vs", default="usd", help="Target vs-currency (usd, btc, eth, etc.)")
        sp.add_argument("--pages", type=int, default=2, help="Pages to fetch (1-5)")
        sp.add_argument(
            "--min-trust",
            default="yellow",
            choices=["red", "yellow", "green"],
            help="Minimum trust score",
        )
        sp.add_argument("--include-risky", action="store_true", help="Include stale/anomalous tickers")
        sp.add_argument("--min-volume", type=float, default=None, help="Minimum 24h volume in vs-currency")
        sp.add_argument("--json", action="store_true", help="Output JSON instead of table")

    sp_tickers = sub.add_parser("tickers", help="List normalized per-exchange prices for a coin")
    add_shared(sp_tickers)
    sp_tickers.set_defaults(func=run_tickers)

    sp_arb = sub.add_parser("arbitrage", help="Compute cross-exchange spreads for a coin")
    add_shared(sp_arb)
    sp_arb.add_argument("--min-spread-pct", type=float, default=1.0, help="Minimum spread percentage")
    sp_arb.add_argument("--top-n", type=int, default=10, help="Max number of rows")
    sp_arb.add_argument("--buy-fee-pct", type=float, default=0.0)
    sp_arb.add_argument("--sell-fee-pct", type=float, default=0.0)
    sp_arb.add_argument("--buy-slippage-pct", type=float, default=0.0)
    sp_arb.add_argument("--sell-slippage-pct", type=float, default=0.0)
    sp_arb.add_argument("--transfer-fee-vs", type=float, default=0.0, help="Flat transfer fee in vs-currency")
    sp_arb.add_argument("--notional-vs", type=float, default=1000.0, help="Trade size to estimate P&L")
    sp_arb.add_argument("--latency-risk-buffer-pct", type=float, default=0.0)
    sp_arb.set_defaults(func=run_arbitrage)

    sp_interactive = sub.add_parser("interactive", help="Interactive menu-driven mode")

    async def _run_interactive(_: argparse.Namespace):
        await run_interactive()

    sp_interactive.set_defaults(func=_run_interactive)

    sp_agent = sub.add_parser(
        "agent",
        help="JSON-over-stdin interface for GPT integrations",
    )

    async def _run_agent(_: argparse.Namespace):
        await run_agent()

    sp_agent.set_defaults(func=_run_agent)

    sp_gpt = sub.add_parser(
        "gpt5-agent",
        help="Interactive GPT-5 session powered by the OpenAI Responses API",
    )
    sp_gpt.add_argument(
        "--model",
        default="gpt-5.1-mini",
        help="OpenAI Responses model to use (default: gpt-5.1-mini)",
    )
    sp_gpt.add_argument(
        "--system-prompt",
        default=None,
        help="Override the default system instructions for GPT-5",
    )

    async def _run_gpt(args: argparse.Namespace):
        await run_gpt_cli(model=args.model, system_prompt=args.system_prompt)

    sp_gpt.set_defaults(func=_run_gpt)

    return p


def main():
    # Allow running without installing by including ./src on sys.path via PYTHONPATH
    if "PYTHONPATH" not in os.environ:
        # Nothing to do; instructions will mention PYTHONPATH=src
        pass
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(args.func(args))


async def serve_agent(
    *,
    agent: GekkoAgent | None = None,
    input_stream: TextIO,
    output_stream: TextIO,
) -> None:
    logger = logging.getLogger("gekko.agent.cli")
    agent = agent or GekkoAgent()

    def _emit(payload: Dict[str, Any]) -> None:
        output_stream.write(json.dumps(payload) + "\n")
        output_stream.flush()

    _emit({"status": "ready", "tools": agent.available_tools()})

    while True:
        line = await asyncio.to_thread(input_stream.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to decode agent request: %s", exc)
            _emit(
                {
                    "status": "error",
                    "error": {
                        "type": "invalid_json",
                        "message": str(exc),
                    },
                }
            )
            continue

        request_id = request.get("request_id")
        tool_name = request.get("tool")
        arguments = request.get("arguments") or {}

        if not tool_name:
            _emit(
                {
                    "request_id": request_id,
                    "status": "error",
                    "error": {
                        "type": "missing_tool",
                        "message": "Field 'tool' is required.",
                    },
                }
            )
            continue

        if not isinstance(arguments, dict):
            _emit(
                {
                    "request_id": request_id,
                    "tool": tool_name,
                    "status": "error",
                    "error": {
                        "type": "invalid_arguments",
                        "message": "Field 'arguments' must be an object.",
                    },
                }
            )
            continue

        try:
            response = await agent.dispatch(tool_name, arguments)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unhandled dispatch error for tool %s", tool_name)
            _emit(
                {
                    "request_id": request_id,
                    "tool": tool_name,
                    "status": "error",
                    "error": {
                        "type": "dispatch_error",
                        "message": str(exc),
                    },
                }
            )
            continue

        envelope = {"request_id": request_id, "tool": tool_name, **response}
        _emit(envelope)


async def run_agent() -> None:
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO)
    await serve_agent(agent=None, input_stream=sys.stdin, output_stream=sys.stdout)


async def run_gpt_cli(*, model: str, system_prompt: str | None) -> None:
    if "OPENAI_API_KEY" not in os.environ:
        print(
            "OPENAI_API_KEY environment variable is required for gpt5-agent.",
            file=sys.stderr,
        )
        return

    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO)

    prompt = system_prompt if system_prompt is not None else None

    try:
        await run_gpt5_agent_cli(model=model, system_prompt=prompt)
    except Exception as exc:  # pragma: no cover - defensive logging
        logging.getLogger("gekko.cli").exception("Failed to start GPT-5 agent")
        print(f"Failed to start GPT-5 agent: {exc}", file=sys.stderr)


# -------- Interactive mode --------

async def run_interactive():
    state: Dict[str, Any] = {
        "coin": "bitcoin",
        "vs": "usd",
        "pages": 2,
        "min_trust": "yellow",
        "include_risky": False,
        "min_volume": None,
        "json": False,
        # Arbitrage tuning
        "min_spread_pct": 1.0,
        "top_n": 10,
        "buy_fee_pct": 0.0,
        "sell_fee_pct": 0.0,
        "buy_slippage_pct": 0.0,
        "sell_slippage_pct": 0.0,
        "transfer_fee_vs": 0.0,
        "notional_vs": 1000.0,
        "latency_risk_buffer_pct": 0.0,
    }

    def _hdr():
        print("\n=== Gordon Gekko — Interactive ===")
        print(
            f"coin={state['coin']} vs={state['vs']} pages={state['pages']} trust>={state['min_trust']} "
            f"risky={'on' if state['include_risky'] else 'off'} min_vol={state['min_volume']} json={'on' if state['json'] else 'off'}"
        )
        print(
            f"fees: buy={state['buy_fee_pct']}% sell={state['sell_fee_pct']}% slip={state['buy_slippage_pct']}/{state['sell_slippage_pct']}% "
            f"flat={state['transfer_fee_vs']} notional={state['notional_vs']} latency_buf={state['latency_risk_buffer_pct']}%"
        )

    def _input(prompt: str, default: Optional[str] = None) -> str:
        suffix = f" [{default}]" if default is not None else ""
        val = input(f"{prompt}{suffix}: ").strip()
        return val if val else (default if default is not None else "")

    while True:
        _hdr()
        print("\nMain menu:")
        print("  1) Show tickers")
        print("  2) Find arbitrage")
        print("  3) Edit basic settings")
        print("  4) Edit costs/advanced")
        print("  5) Toggle JSON/table output")
        print("  q) Quit")
        choice = _input("Select").lower()
        if choice in {"q", "quit", "exit"}:
            print("Bye.")
            return
        elif choice == "5":
            state["json"] = not state["json"]
            continue
        elif choice == "3":
            state["coin"] = _input("Coin id", state["coin"]) or state["coin"]
            state["vs"] = _input("Vs currency", state["vs"]) or state["vs"]
            try:
                state["pages"] = int(_input("Pages (1-5)", str(state["pages"])))
            except Exception:
                pass
            mt = _input("Min trust (red/yellow/green)", state["min_trust"]).lower()
            if mt in {"red", "yellow", "green"}:
                state["min_trust"] = mt
            ir = _input("Include risky? (y/n)", "n" if not state["include_risky"] else "y").lower()
            state["include_risky"] = ir.startswith("y")
            mv = _input("Min volume in vs (blank to unset)", "" if state["min_volume"] is None else str(state["min_volume"]))
            state["min_volume"] = None if mv == "" else float(mv)
            continue
        elif choice == "4":
            try:
                state["min_spread_pct"] = float(_input("Min spread %", str(state["min_spread_pct"])))
                state["top_n"] = int(_input("Top N", str(state["top_n"])))
                state["buy_fee_pct"] = float(_input("Buy fee %", str(state["buy_fee_pct"])))
                state["sell_fee_pct"] = float(_input("Sell fee %", str(state["sell_fee_pct"])))
                state["buy_slippage_pct"] = float(_input("Buy slippage %", str(state["buy_slippage_pct"])))
                state["sell_slippage_pct"] = float(_input("Sell slippage %", str(state["sell_slippage_pct"])))
                state["transfer_fee_vs"] = float(_input("Flat transfer fee (vs)", str(state["transfer_fee_vs"])))
                state["notional_vs"] = float(_input("Notional (vs)", str(state["notional_vs"])))
                state["latency_risk_buffer_pct"] = float(_input("Latency buffer %", str(state["latency_risk_buffer_pct"])))
            except Exception:
                print("Some inputs invalid; kept previous values.")
            continue
        elif choice == "1":
            tickers = await _fetch_normalized_tickers(
                coin_id=state["coin"],
                vs_currency=state["vs"],
                pages=max(1, min(5, int(state["pages"]))),
                min_trust=state["min_trust"],
                exclude_risky=not state["include_risky"],
                min_volume=state["min_volume"],
            )
            if state["json"]:
                print(json.dumps({"count": len(tickers), "tickers": tickers}, indent=2))
            else:
                rows = [["Exchange", "Pair", f"Price({state['vs']})", "Trust", "Volume"]]
                for t in tickers:
                    rows.append(
                        [
                            t.get("exchange") or "?",
                            t.get("pair") or "?",
                            f"{t.get('price'):.8f}" if isinstance(t.get("price"), (int, float)) else str(t.get("price")),
                            t.get("trust_score") or "?",
                            f"{t.get('volume_vs'):.2f}" if isinstance(t.get("volume_vs"), (int, float)) else "",
                        ]
                    )
                _print_table(rows)
            input("\nPress Enter to continue...")
            continue
        elif choice == "2":
            tickers = await _fetch_normalized_tickers(
                coin_id=state["coin"],
                vs_currency=state["vs"],
                pages=max(1, min(5, int(state["pages"]))),
                min_trust=state["min_trust"],
                exclude_risky=not state["include_risky"],
                min_volume=state["min_volume"],
            )
            opps = compute_opportunities(
                tickers,
                min_spread_pct=state["min_spread_pct"],
                top_n=state["top_n"],
                buy_fee_pct=state["buy_fee_pct"],
                sell_fee_pct=state["sell_fee_pct"],
                buy_slippage_pct=state["buy_slippage_pct"],
                sell_slippage_pct=state["sell_slippage_pct"],
                transfer_fee_vs=state["transfer_fee_vs"],
                notional_vs=state["notional_vs"],
                latency_risk_buffer_pct=state["latency_risk_buffer_pct"],
            )
            if state["json"]:
                print(json.dumps({"opportunities": opps}, indent=2))
            else:
                rows = [["BuyEx", "Buy", "SellEx", "Sell", "Raw%", "Net%", f"EstProfit({state['vs']})"]]
                for o in opps:
                    rows.append(
                        [
                            o["buy"]["exchange"],
                            f"{o['buy']['price']:.8f}",
                            o["sell"]["exchange"],
                            f"{o['sell']['price']:.8f}",
                            f"{o['raw_spread_pct']:.3f}",
                            f"{o['net_spread_pct']:.3f}",
                            f"{o['est_net_profit_vs']:.2f}",
                        ]
                    )
                _print_table(rows)
            input("\nPress Enter to continue...")
            continue
        else:
            print("Unknown choice. Try again.")
            continue


if __name__ == "__main__":
    main()
