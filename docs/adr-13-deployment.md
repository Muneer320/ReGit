# ADR-13: Deployment

- **Status: LOCKED** · Owner: Amrit

## Decision
**Local-first: one `uvicorn` process on localhost serving API+WS+static client; zero network required at demo time.** All JS vendored, embedding model pre-cached, fixtures in repo. Repo ships `requirements.txt` + `scripts/setup.sh` (venv, install, model download, `gr init`) so a fresh laptop can reproduce.

Fallback ladder (failure-playbook.md): deployment env fails → run from repo venv → API/CLI demo without frontend → deterministic offline scripts (op-log replay, fixture diffs).

## Why (runner-up: hosted deployment, e.g. Vercel/Railway)
Decisive tradeoff: hosted demos add DNS/build/secrets flakiness for zero judging points; the brief scores the engine, not ops. Also pycrdt rooms + single SQLite make multi-instance deployment actively wrong at this stage. Localhost is the honest, reliable choice; "how would you deploy for real" is a judge-Q&A answer (stateless API replicas + Redis-backed CRDT sync + Postgres+pgvector + S3 blob store), not a build item.

## Risks
Judge machine ≠ our machine → setup script + recorded backup demo video (H12). Port collision → pinned port 8377, env-overridable.

## Reversibility
N/A (operational).

## Consequences
`scripts/{setup.sh,run_dev.sh,reset_demo.sh}`; `demo-script.md` assumes localhost.
