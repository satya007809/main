"""Bharati Investigation Desk API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import db as dbmod
from .config import get_settings
from .jobs.queue import WorkerThread
from .playbooks.store import seed_defaults
from .routers import agent, auth, cases, connectors, reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
API_PREFIX = "/api/v1"


def init_db(create_tables: bool = False) -> None:
    if create_tables:
        dbmod.Base.metadata.create_all(dbmod.engine)
    s = dbmod.SessionLocal()
    try:
        seed_defaults(s)
    finally:
        s.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.environment == "production":
        if s.jwt_secret.startswith("dev-") or not s.data_encryption_key:
            raise RuntimeError("Set BID_JWT_SECRET and BID_DATA_ENCRYPTION_KEY for production")
    init_db(create_tables=s.environment != "production")  # production uses Alembic migrations
    worker = None
    if s.run_worker_in_process:
        worker = WorkerThread()
        worker.start()
    yield
    if worker:
        worker.stop_event.set()


def create_app() -> FastAPI:
    app = FastAPI(title="Bharati Investigation Desk API", version="1.0.0", lifespan=lifespan,
                  docs_url="/docs" if get_settings().environment != "production" else None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return resp

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # pragma: no cover
        logging.getLogger("api").exception("unhandled error")
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    @app.get("/health")
    def health():
        return {"ok": True}

    for r in (auth.router, connectors.router, cases.router, reports.router, agent.router):
        app.include_router(r, prefix=API_PREFIX)
    return app


app = create_app()
