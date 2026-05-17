"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import duckdb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import analyze, products, score
from data.db import connect, init_schema

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    con = connect(read_only=False)
    init_schema(con)
    app.state.db = con
    try:
        yield
    finally:
        con.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="NutriCart",
        version=VERSION,
        lifespan=lifespan,
        description="Hebrew shopping-list health scorer & alternatives API.",
    )

    cors_origins = os.environ.get("NUTRICART_CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(analyze.router)
    app.include_router(products.router)
    app.include_router(score.router)

    @app.get("/healthz")
    def healthz() -> dict:
        try:
            row = app.state.db.execute("SELECT count(*) FROM products").fetchone()
            return {"ok": True, "products": int(row[0])}
        except duckdb.CatalogException:
            return {"ok": True, "products": 0, "note": "schema empty"}

    @app.get("/version")
    def version() -> dict:
        return {"version": VERSION}

    return app


app = create_app()
