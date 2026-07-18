from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quant_research_api.routers import auth, configs, registry, runs
from quant_research_api.settings import settings

app = FastAPI(
    title="quant-research-api",
    description="Multi-user API for the quant-research engine: accounts, saved configs, async runs.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(configs.router)
app.include_router(registry.router)
app.include_router(runs.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
