from fastapi import FastAPI

from .routers import health, market
from .routers import arbitrage


def create_app() -> FastAPI:
    app = FastAPI(title="Gordon Gekko API", version="0.1.0")

    app.include_router(health.router, tags=["health"])
    app.include_router(market.router, prefix="/market", tags=["market"])
    app.include_router(arbitrage.router, prefix="/arbitrage", tags=["arbitrage"])

    return app


app = create_app()
