# ADR-07: Backend stack

- **Status: LOCKED** · Owner: Muneer (core) + AI (scaffolding)

## Decision
**Python 3.11 + FastAPI + uvicorn, one process serving REST + WebSocket + static client.** Versioning core is stdlib-first (`hashlib`, `sqlite3`, `zlib`). Deps (all pip wheels, install at H0): `fastapi uvicorn pycrdt pycrdt-websocket chromadb sentence-transformers pypdf tree-sitter tree-sitter-python pytest httpx websockets`.

## Why (runner-up: all-TypeScript/Node)
Decisive tradeoff: 3 of 4 pillars skew Python (PDF extraction, chat-export parsing ergonomics, sentence-transformers embeddings); the DAG core is stdlib-only (zero dependency risk at the critical hour); pycrdt removes Node's only real advantage (native CRDT). FastAPI gives async WS + REST in one process with near-zero boilerplate — AI agents generate route scaffolding from api-contract.md mechanically.

## Alternatives rejected
- Flask: sync-first, WS via bolt-ons; worse async story for CRDT rooms.
- Django: ORM + admin we don't need; slows the first commit.
- Rust/Go core: unbeatable performance, catastrophic velocity for this team in 13h.

## Risks
Chroma/onnxruntime install weight → isolated requirements, install at H0, FTS5-only fallback keeps retrieval demoable. GIL limits concurrent CPU work — irrelevant at demo scale.

## Reversibility
High: core engines are pure functions importable without the web layer; the server is a thin shell.

## Consequences
`backend/src/api/main.py` wires routers per api-contract.md; `uvicorn` single worker (shared in-memory CRDT registry — do NOT scale workers at demo).
