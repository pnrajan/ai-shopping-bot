"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ai_shopping_bot import __version__
from ai_shopping_bot.api.security import RateLimiter, make_guard
from ai_shopping_bot.api.tracking_routes import build_tracking_router
from ai_shopping_bot.api.wiring import Services, build_services
from ai_shopping_bot.contracts.chat import ChatRequest, ChatResponse
from ai_shopping_bot.contracts.context import LLMBudgetExceeded
from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.contracts.understanding import QueryUnderstanding
from ai_shopping_bot.llm.client import LLMError
from ai_shopping_bot.logging import get_logger, log_event
from ai_shopping_bot.settings import Settings, get_settings

log = get_logger("api")


def _lifespan(settings: Settings, services: Services | None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = services or build_services(settings)
        log_event(
            log,
            "startup",
            llm=settings.llm,
            catalog=settings.catalog,
            store=settings.session_store,
            tracking=settings.tracking,
        )
        monitor = app.state.services.monitor
        if monitor:
            monitor.start()
        yield
        if monitor:
            monitor.stop()

    return lifespan


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    limiter = RateLimiter(settings.rate_limit_per_minute)
    guard = make_guard(settings, limiter)

    app = FastAPI(
        title="AI Shopping Bot API",
        version=__version__,
        description="Chat endpoint for a personal shopping assistant.",
        lifespan=_lifespan(settings, services),
    )

    def svc(request: Request) -> Services:
        return request.app.state.services

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.post("/chat", response_model=ChatResponse, dependencies=[Depends(guard)], tags=["chat"])
    def chat(body: ChatRequest, s: Services = Depends(svc)) -> ChatResponse:
        try:
            response = s.pipeline.run(body)
        except LLMBudgetExceeded as e:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
        except LLMError as e:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
        s.tracer.record(response)
        return response

    @app.get(
        "/products/search",
        response_model=list[Product],
        dependencies=[Depends(guard)],
        tags=["products"],
    )
    def products_search(q: str, limit: int = 10, s: Services = Depends(svc)) -> list[Product]:
        qu = QueryUnderstanding(query=q, canonical_query=q, search_queries=[q])
        products, _ = s.search.search(qu, limit=max(1, min(limit, 50)))
        return products

    app.include_router(build_tracking_router(settings, guard, svc))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, _exc: Exception) -> JSONResponse:
        log.exception("unhandled", extra={"fields": {"path": request.url.path}})
        return JSONResponse(status_code=500, content={"success": False, "error": "internal error"})

    logging.getLogger("ai_shopping_bot").setLevel(logging.INFO)
    return app
