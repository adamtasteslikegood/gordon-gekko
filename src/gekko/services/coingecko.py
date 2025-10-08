from typing import List, Dict, Any, Optional

import httpx


BASE_URL = "https://api.coingecko.com/api/v3"


async def get_simple_price(ids: List[str], vs_currencies: List[str]) -> Dict[str, Any]:
    params = {
        "ids": ",".join(ids),
        "vs_currencies": ",".join(vs_currencies),
    }
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
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

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        resp = await client.get(f"/coins/{coin_id}/tickers", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_supported_vs_currencies() -> List[str]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
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

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        resp = await client.get("/coins/markets", params=params)
        resp.raise_for_status()
        return resp.json()


async def get_exchanges_list(*, per_page: int = 250, page: int = 1) -> List[Dict[str, Any]]:
    params = {"per_page": per_page, "page": page}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        resp = await client.get("/exchanges", params=params)
        resp.raise_for_status()
        return resp.json()
