# ReGit: the maintained demo

ReGit began as a team hackathon prototype for research-native versioning. The maintained local application has two connected layers: repositories organize raw files in immutable tree snapshots; research artifacts provide parsing, sentence/message diff, prose merge, explicit provenance and live editing.

Create a repository, add folders and upload sources. Each change creates a guarded snapshot. Branches share an initial tree and then evolve independently. Old commits retain their exact file bytes. A PDF/codebase/chat parser can extract structured representations while the repository still retains the original upload.

For collaboration, open the same text file in two sessions as userA/userB. A Yjs/pycrdt document synchronizes edits and presence. Its identities and pending draft survive restart. Commit from live saves an artifact version; publishing pins that version into the repository tree. A concurrent external branch advance is rejected rather than overwritten. Explicit shared reset provides recovery after the user reconciles pending edits.

The merge example creates real API artifacts/branches, not invented dashboard activity. Different edits to the same sentence surface conflict cards; an empty free resolution deletes the conflicting text. The final commit has two parents. Inspect formatting: paragraph layout preservation still has limits.

`claim:` lines are versioned statements with import/commit provenance. Keyword search returns cited text. Historical queries reconstruct a selected immutable revision, including text replaced in the current index. Optional vector dependencies are separate and unverified in the lightweight demo.

This is a local shared workspace. Identity switching is not authentication, and no public backend, tenant isolation, throughput benchmark or production guarantee is claimed. See [README](../README.md), [architecture](architecture.md), [data model](data-model.md) and [walkthrough](demo/demo-script.md).
