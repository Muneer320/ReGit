# ReGit

[![Checks and local demo](https://github.com/Muneer320/ReGit/actions/workflows/ci.yml/badge.svg)](https://github.com/Muneer320/ReGit/actions/workflows/ci.yml)

ReGit is a local research workspace with versioned repositories, typed source artifacts and collaborative prose editing. It began at Gradient Rush Hackathon in 2026, built by **Muneer Alam and Amrit Kang**.

The maintained demo runs on your machine: one Python process serves the React interface, HTTP API and WebSockets. It uses local SQLite and content-addressed files. The workspace starts empty; examples are created only when you choose **Load merge example**.

## Run the local demo

Install Docker with Compose, then run from the repository root:

```sh
docker compose -p regit-demo up --build --wait --wait-timeout 180
```

Open [http://127.0.0.1:8377](http://127.0.0.1:8377). No account, API key, embedding model or external database is required. Only the loopback web port is exposed. Stop with `docker compose -p regit-demo stop`; use the same project name next time to retain its named volume.

This is a **shared local prototype**. User A/B select editing identities, not authenticated accounts. The old hosted frontend has no verified public backend; use the local setup for the working demo. Public hosting, access control and production readiness are outside the verified scope.

## Try it

1. Create a repository. Add a nested folder such as `notes/experiments`, open it and upload Markdown, text, code, ordinary JSON or a binary file. Auto treats ordinary JSON/code as text; choose an explicit format for chat exports, PDFs or a codebase ZIP.
2. Select a text file, edit it, enter a commit message and **Commit file changes**. Reload to check persistence. Create a branch, edit independently and switch back to confirm isolation.
3. Choose an earlier **Revision** and download its original bytes. Folder/file deletion creates a new snapshot; it does not erase earlier revisions. ZIPs remain downloadable files and are also parsed as codebase artifacts; they are not automatically expanded into repository folders.
4. For a text file, open **Live collaboration** in two separate browser sessions. Select userB in the second session. Edits and presence synchronize. **Commit from live** saves an artifact version; **Publish live file version** pins it into the repository snapshot.
5. Click **Load merge example**, open `lr-stability.md` under Research artifacts, choose **Merge prose**, compare the branches and resolve a conflict. History shows the two-parent result. Search returns actual indexed text and source/commit citations.

The [walkthrough](docs/demo/demo-script.md) includes the automated smoke and restart checks.

## What is versioned

Repository commits contain immutable tree manifests with folders, exact raw file hashes and pinned research-artifact commits. Only branch refs move. Mutations compare the expected repository head; a stale writer receives a conflict instead of overwriting another change. Failed upload batches roll back their metadata/ref changes.

Markdown/text artifacts support sentence diff, three-way prose merge, live drafts and explicit `claim:` provenance. Chat supports message diff through the API. PDF/codebase artifacts retain parsed representations and retrieval chunks; their merge/diff UI is not advertised as implemented. There is no repository-wide tree merge. Re-uploading a source creates a new parsed source/artifact while old repository snapshots remain accessible.

Draft edits are persisted with their CRDT identities, including uncommitted changes. A live commit refuses to overwrite a branch changed outside its draft. After reconciling/copying any pending edits, **Reset draft to latest commit** explicitly replaces the shared draft for all collaborators.

Prose merging can still alter paragraph layout; inspect the preview before accepting. A free-text conflict resolution may be empty to delete the conflicting text. Claims are explicit sentinel statements, not inferred scientific truth; claims-at-commit returns statements from that commit's ancestry.

## Search and limits

Keyword search with citations is the default. Historical queries reconstruct the selected immutable artifact revision, so text replaced in the current index remains searchable. Historical retrieval is keyword-only. Optional Chroma/embedding dependencies require `uv sync --locked --extra vector`, a downloaded model and `GR_ENABLE_VECTORS=1`; that optional path is not included in the verified lightweight demo.

Repository uploads allow up to 50 files, 16 MiB per file and 64 MiB per batch. Raw files remain downloadable even when parsing extracts a different representation. Text editing is available for text/Markdown, not arbitrary binary data. Run one server worker per data directory; simultaneous server processes must not share it. Files and commits are retained for history, so deletion is not a secure-erasure feature.

## Native development

Use Python 3.11+ (3.13 in CI/Docker), uv and Node.js 24:

```sh
python scripts/setup.py
uv run --locked uvicorn backend.src.api.main:app --host 127.0.0.1 --port 8377
```

Setup installs locked dependencies, builds the frontend and initializes the store. It downloads no embedding model by default. `GR_API_DATA_DIR` selects the data directory (default `data/`). For frontend hot reload, run `npm --prefix frontend run dev` separately; Vite uses port 5175 and proxies to the API on 8377.

## Checks

```sh
uv run --locked pytest -m "not vector" -q --timeout=60
uv run --locked ruff check backend tests --select F821,F822,F823,E9
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

With Compose running:

```sh
docker compose -p regit-demo exec -T regit /app/.venv/bin/python /app/scripts/smoke_demo.py --live --state-out /data/.smoke-state.json
node frontend/smoke.mjs
docker compose -p regit-demo restart regit
docker compose -p regit-demo up --wait --wait-timeout 180
docker compose -p regit-demo exec -T regit /app/.venv/bin/python /app/scripts/smoke_demo.py --live --verify-state /data/.smoke-state.json
```

The browser check requires frontend npm dependencies and an installed Chrome; set `CHROME_BIN` if needed. It opens two isolated sessions against the local server. Smoke checks create synthetic repositories/artifacts and retain their records for restart verification. CI runs Python tests on Linux/Windows, frontend tests/lint/build, Docker API/WebSocket checks, the real browser flow and restart persistence. Some frontend lint warnings remain; no hand-written test-count badge or throughput guarantee is used.

## Documentation and contributors

- [Current architecture](docs/architecture.md), [data model](docs/data-model.md), [API guide](docs/specs/api-contract.md)
- [Project explanation](docs/EXPLAINER.md), [demo walkthrough](docs/demo/demo-script.md), [demo questions](docs/demo/judge-qa.md)
- [Documentation index](docs/README.md) separates maintained guides from historical design notes.

Built collaboratively by [Muneer Alam](https://github.com/Muneer320) and [Amrit Kang](https://github.com/amritkang165). Original contributions and history are preserved. Licensed under [MIT](LICENSE).
