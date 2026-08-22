"""FastAPI app shell — routers are generated from api-contract.md at H6.

Scaffold: health endpoint only; everything else lands per 12h-execution-plan.
"""
from fastapi import FastAPI

app = FastAPI(title="git-for-research", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
