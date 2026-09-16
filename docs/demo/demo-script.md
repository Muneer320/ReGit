# Reproducible local demo

Start `docker compose -p regit-demo up --build --wait --wait-timeout 180` at the root and open http://127.0.0.1:8377.

1. Create a repository named Research notes. Create `notes/experiments`, open both folder levels, and upload a small Markdown file plus ordinary JSON or an image. Raw files remain downloadable; ordinary JSON uses text parsing in Auto mode.
2. Edit the Markdown file and commit. Reload, create an experiment branch, edit again and switch back to main. Pick an older Revision and verify its download differs from the current version.
3. Open Live collaboration on the text file in two isolated browser sessions; choose userB in the second session. Type on both sides and check presence. Commit from live, then Publish live file version. Reload to see the repository's pinned text. Draft reset affects all collaborators and requires an explicit confirmation.
4. Return to the workspace and Load merge example. Open lr-stability.md, choose Merge prose, compare main/research-branch and resolve the conflict. View history: the result has two parents. Search for a term in the imported notes. Activity contains actual commits.

Automate API/WebSocket checks with `docker compose -p regit-demo exec -T regit /app/.venv/bin/python /app/scripts/smoke_demo.py --live --state-out /data/.smoke-state.json`. With frontend npm dependencies and Chrome installed, run `node frontend/smoke.mjs` for the real two-browser flow. `CHROME_BIN` overrides executable discovery.

Restart the container (`docker compose -p regit-demo restart regit`), wait for health (`docker compose -p regit-demo up --wait --wait-timeout 180`) and verify with `docker compose -p regit-demo exec -T regit /app/.venv/bin/python /app/scripts/smoke_demo.py --live --verify-state /data/.smoke-state.json`. This checks historical/raw/branch file bytes and recovers/commits a previously uncommitted live draft.

All smoke records are synthetic and retained for restart verification. Stop the stack with `docker compose -p regit-demo stop`; preserve the named volume/project name. The old hosted frontend is not the integrated backend demo. No video is required to run these checks.
