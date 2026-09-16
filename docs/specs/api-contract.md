# Current API guide

The native base is `http://127.0.0.1:8377/api`. Errors use `{error: {code, message}}`. `X-User` selects a demo editing identity and grants no authentication. The same process serves WebSockets and the built frontend.

| Method | Route | Behavior |
|---|---|---|
| GET | `/health`, `/activity` | Readiness/version and actual recent commits |
| GET / POST | `/repositories` | List / create a repository (`name`) |
| GET | `/repositories/{id}?branch=main&commit=…` | Latest or historical tree |
| GET | `/repositories/{id}/history?branch=main` | Repository commit history |
| POST | `/repositories/{id}/branches` | `name`, `from_commit` |
| POST | `/repositories/{id}/folders` | Version a nested folder |
| POST | `/repositories/{id}/files` | Multipart `files`, `path`, `branch`, `base_commit`, `message`, optional `file_type` |
| GET / PATCH | `/repositories/{id}/file` | Exact raw download (`path`, optional branch/commit/download) / edit text |
| DELETE | `/repositories/{id}/entry` | Version a file or recursive folder deletion |
| POST | `/repositories/{id}/file/live` | Prepare the file's branch-specific live artifact |
| POST | `/repositories/{id}/file/publish` | Pin its saved live version in a repository snapshot |
| DELETE | `/repositories/{id}` | Tombstone repository |
| GET / POST | `/artifacts` | Actual typed artifacts / create an artifact |
| GET / DELETE | `/artifacts/{id}` | Read / tombstone artifact |
| POST | `/artifacts/{id}/commit` | `branch`, `content`, `message`, optional `base_commit` |
| GET | `/artifacts/{id}/history` | Artifact history |
| GET / POST | `/branches` | List (`artifact_id`) / create artifact branch |
| POST | `/checkout` | `artifact_id`, branch or commit; rejects foreign commits |
| GET | `/diff?artifact_id=…&from=…&to=…` | Prose sentence / chat message diff |
| POST | `/merge` | Prose `artifact_id`, `ours_branch`, `theirs_branch` |
| POST | `/merge/{id}/resolve` | Per-conflict ours/theirs/free resolutions; empty free text deletes |
| POST | `/ingest` | Explicit typed research-source imports |
| POST | `/search` | `query`, optional k/branch/as_of_commit/artifact_kind; k capped at 100 |
| GET | `/provenance/at/{commit}/claims` | Ancestral explicit statements |
| GET | `/provenance/claim/{id}`, `/provenance/artifact/{id}/sources` | Claim chain / source origins |

Repository folder/edit/delete/publication bodies use `path`, `branch`, `base_commit`, `message`; text edits also supply `content`. Stale heads return 409. Upload batches are atomic at the metadata/tree boundary. Limits are 50 files, 16 MiB each, 64 MiB total for repository uploads.

WebSocket `/api/collaborate/{artifact_id}?branch=…&user=…` accepts existing prose artifacts/branches. Binary frames use Yjs sync/awareness. JSON controls include `commit_request` with message, `presence_ping` and explicit `reset_request`; responses include committed/reset/error. One server worker is required.

See [the runnable smoke script](../../scripts/smoke_demo.py) for exact HTTP and real WebSocket examples. The older ADR/spec files describe original design goals; this guide and the current implementation define the maintained demo scope.
