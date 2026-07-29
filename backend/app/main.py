from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.schemas.operations import HealthResponse

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(httpx.HTTPError)
async def upstream_exception_handler(request: Request, exc: httpx.HTTPError):
    return JSONResponse(
        status_code=502,
        content={"detail": {"code": "UPSTREAM_ERROR", "message": "Upstream provider request failed."}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Keep upstream payloads and credentials out of responses.
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "INTERNAL_ERROR", "message": "Unexpected server error."}},
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    async with AsyncSessionLocal() as session:
        await session.execute(text("select 1"))
    return HealthResponse(status="ok", database="ok", app=settings.app_name)
