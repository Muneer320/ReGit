# ADR-13: Deployment

- **Status: LOCKED** · Owner: Amrit

## Decision
**Local-first: one `uvicorn` process on localhost serving API+WS+static client; zero network required at demo time.** All JS vendored, embedding model pre-cached, fixtures in repo. Repo deps come from `pyproject.toml` (uv-managed, `uv.lock`); `scripts/setup.sh` (uv sync, model download, `gr init`) reproduces on a fresh laptop.

Fallback ladder (demo-script.md §fallbacks): deployment env fails → run from repo venv → API/CLI demo without frontend → deterministic offline scripts (`scripts/reindex.py`, fixture diffs).

## Why (runner-up: hosted deployment, e.g. Vercel/Railway)
Decisive tradeoff: hosted demos add DNS/build/secrets flakiness for zero judging points; the brief scores the engine, not ops. Also pycrdt rooms + single SQLite make multi-instance deployment actively wrong at this stage. Localhost is the honest, reliable choice; "how would you deploy for real" is a judge-Q&A answer (stateless API replicas + Redis-backed CRDT sync + Postgres+pgvector + S3 blob store), not a build item.

## Risks
Judge machine ≠ our machine → setup script + recorded backup demo video (H12). Port collision → pinned port 8377, env-overridable.

## Reversibility
N/A (operational).

## Consequences
`scripts/{setup.sh,run_dev.sh,reset_demo.sh}`; `demo/demo-script.md` assumes localhost.
