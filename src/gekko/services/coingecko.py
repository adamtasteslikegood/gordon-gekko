import os
from typing import List, Dict, Any, Optional

import httpx
import logging


BASE_URL = "https://api.coingecko.com/api/v3"
API_KEY_ENV_VAR = "CG_API_KEY"
API_KEY_HEADER = "x-cg-demo-api-key"
logger = logging.getLogger("gekko.services.coingecko")
_COIN_ID_CACHE: Dict[str, str] = {}


def _auth_headers() -> Dict[str, str]:
    """
    Return CoinGecko demo API auth headers when `CG_API_KEY` is present.
    """
    api_key = os.getenv(API_KEY_ENV_VAR)
    if not api_key:
        return {}
    return {API_KEY_HEADER: api_key}


def _create_client(timeout: int | float) -> httpx.AsyncClient:
    headers = _auth_headers()
    return httpx.AsyncClient(base_url=BASE_URL, timeout=timeout, headers=headers or None)


async def get_simple_price(ids: List[str], vs_currencies: List[str]) -> Dict[str, Any]:
    params = {
        "ids": ",".join(ids),
        "vs_currencies": ",".join(vs_currencies),
    }
    async with _create_client(timeout=10) as client:
        resp = await client.get("/simple/price", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_coin_tickers(
    *,
    coin_id: str,
    page: int = 1,
    order: str = "trust_score_desc",
    exchange_ids: Optional[str] = None,
    include_exchange_logo: Optional[bool] = None,
    depth: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Fetch tickers for a coin across exchanges.
    Docs: https://www.coingecko.com/api/documentations/v3#/coins/get_coins__id__tickers
    """
    params: Dict[str, Any] = {
        "page": page,
        "order": order,
    }
    if exchange_ids:
        params["exchange_ids"] = exchange_ids
    if include_exchange_logo is not None:
        params["include_exchange_logo"] = str(bool(include_exchange_logo)).lower()
    if depth is not None:
        params["depth"] = str(bool(depth)).lower()

    async with _create_client(timeout=15) as client:
        resp = await client.get(f"/coins/{coin_id}/tickers", params=params)
        resp.raise_for_status()
        return resp.json()


def _select_coin_entry(normalized: str, coins: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    for coin in coins:
        coin_id = coin.get("id")
        if isinstance(coin_id, str) and coin_id.lower() == normalized:
            return coin

    for coin in coins:
        symbol = coin.get("symbol")
        if isinstance(symbol, str) and symbol.lower() == normalized:
            return coin

    for coin in coins:
        name = coin.get("name")
        if isinstance(name, str) and normalized in name.lower():
            return coin

    return None


async def resolve_coin_id(candidate: str) -> str:
    """
    Resolve user-supplied coin identifiers (tickers, names, or slugs)
    to a canonical CoinGecko coin id.
    """

    cleaned = (candidate or "").strip()
    if not cleaned:
        raise ValueError("Coin identifier is required.")

    key = cleaned.lower()
    cached = _COIN_ID_CACHE.get(key)
    if cached:
        return cached

    coins: List[Dict[str, Any]] = []
    try:
        async with _create_client(timeout=10) as client:
            resp = await client.get("/search", params={"query": cleaned})
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("coins")
            if isinstance(data, list):
                coins = data
    except httpx.HTTPError as exc:
        logger.debug("Coin search failed for %s: %s", cleaned, exc)

    match = _select_coin_entry(key, coins)
    if match:
        coin_id = match.get("id")
        if isinstance(coin_id, str):
            _COIN_ID_CACHE[key] = coin_id
            _COIN_ID_CACHE.setdefault(coin_id.lower(), coin_id)
            symbol = match.get("symbol")
            if isinstance(symbol, str):
                _COIN_ID_CACHE.setdefault(symbol.lower(), coin_id)
            return coin_id

    fallback = key.replace(" ", "-")
    _COIN_ID_CACHE[key] = fallback
    return fallback


async def get_supported_vs_currencies() -> List[str]:
    async with _create_client(timeout=10) as client:
        resp = await client.get("/simple/supported_vs_currencies")
        resp.raise_for_status()
        return resp.json()


async def get_coins_markets(
    *,
    vs_currency: str,
    ids: Optional[List[str]] = None,
    per_page: int = 50,
    page: int = 1,
    price_change_percentage: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "vs_currency": vs_currency,
        "per_page": per_page,
        "page": page,
    }
    if ids:
        params["ids"] = ",".join(ids)
    if price_change_percentage:
        params["price_change_percentage"] = price_change_percentage

    async with _create_client(timeout=15) as client:
        resp = await client.get("/coins/markets", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_exchanges_list(*, per_page: int = 250, page: int = 1) -> List[Dict[str, Any]]:
    params = {"per_page": per_page, "page": page}
    async with _create_client(timeout=15) as client:
        resp = await client.get("/exchanges", params=params)
        resp.raise_for_status()
        return resp.json()
