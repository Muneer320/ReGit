# Demo questions

**What is real?** Local repository snapshots, nested files, branch isolation/history, exact downloads, typed parsing, prose diff/merge, chat message diff, two-session live edits/presence, persisted pending drafts, explicit claims and keyword retrieval. Examples create real data through the API.

**What is the research artifact/repository distinction?** A repository tree pins raw files and artifact commits. A parsed artifact can have its own branches and live drafts. Publishing a saved live file explicitly updates the repository snapshot.

**What are the limits?** Shared local prototype, no authenticated accounts or tenant boundary, one worker, no tree/codebase merge, no verified public backend or throughput promise. Prose merge can alter paragraph layout. Optional vectors are not part of the verified lightweight demo.

**Does a restart lose a draft?** Full CRDT state and identities are persisted; the smoke check restarts the process and then commits the pending draft. Saved files/history use the same retained volume.

**Are claims inferred facts?** No. Only explicit `claim:` sentinels are captured; provenance records what a commit stated and which imported source it came from.

**Where is validation?** The CI badge links actual Linux/Windows backend, frontend and Docker/browser/restart checks. Run commands are in the README and demo script.
