"""Ingestion pipeline — parse -> canonical payload -> rows -> blobs -> root commit.

Implements the universal pipeline (ingestion-spec.md):
  upload -> adapter.parse -> canonical payload -> ResearchSource row + Artifact
  row + imported_as edge -> blobs (content-addressed) -> root commit -> claim
  rows (from `claim:` sentinels) + provenance edges.

Root commits are performed by ObjectStore.commit (versioning engine). Because
the commit engine is implemented, the full pipeline is live today. Parsing
failures raise ParseError (-> HTTP 422).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC

from ..core import ids as ids_mod
from .parsers import ParsedUnit, parse


@dataclass
class ArtifactOutcome:
    artifact_id: str
    kind: str
    title: str
    root_hash: str          # blob id (md/txt/chat/pdf) or tree id (codebase)
    commit_id: str | None = None
    claims: list[str] = field(default_factory=list)   # `claim:` sentinels
    warnings: list[str] = field(default_factory=list)


@dataclass
class IngestOutcome:
    source_id: str
    artifacts: list[ArtifactOutcome] = field(default_factory=list)

    @property
    def artifact_ids(self) -> list[str]:
        return [a.artifact_id for a in self.artifacts]

    @property
    def warnings(self) -> list[str]:
        out: list[str] = []
        for a in self.artifacts:
            out.extend(a.warnings)
        return out


def ingest(store, kind: str, filename: str, data: bytes, uploader: str) -> IngestOutcome:
    """Parse + persist source/artifact/edge rows + write content blobs."""
    units: list[ParsedUnit] = parse(kind, filename, data)

    # Source row + artifact rows + imported_as edge written atomically.
    with store._tx() as db:
        src_id = ids_mod.new_id("src_")
        db.execute(
            "INSERT INTO sources(id, type, original_filename, imported_at, uploader) "
            "VALUES (?,?,?,?,?)",
            (src_id, kind.lower(), filename, _now(), uploader),
        )
        outcome = IngestOutcome(source_id=src_id)
        for unit in units:
            root_hash = _store_unit(store, unit)
            art_id = ids_mod.new_id("art_")
            db.execute(
                "INSERT INTO artifacts(id, kind, title, source_id, created_at) VALUES (?,?,?,?,?)",
                (art_id, unit.kind, unit.title, src_id, _now()),
            )
            _add_edge(db, "source", src_id, "artifact", art_id, "imported_as")
            outcome.artifacts.append(
                ArtifactOutcome(
                    artifact_id=art_id, kind=unit.kind, title=unit.title,
                    root_hash=root_hash, claims=list(unit.claims),
                    warnings=list(unit.warnings),
                )
            )
    return outcome


def commit_roots(store, outcome: IngestOutcome, author: str, message: str = "root import") -> None:
    """Create the root commit per artifact and write claim/provenance rows.

    Bakes the commit id onto each ArtifactOutcome. Claim `claim:` sentinels
    collected during parsing become Claim rows stated by the root commit
    (provenance-spec.md); has_version edge artifact -> commit is written.
    """
    for art in outcome.artifacts:
        cid = store.commit(
            [], art.root_hash, art.artifact_id, message, author, kind=art.kind
        )
        art.commit_id = cid
        store.db.execute(
            "INSERT OR IGNORE INTO provenance_edges(id, from_kind, from_id, to_kind, to_id, relation, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (ids_mod.new_id("pe_"), "artifact", art.artifact_id, "version", cid,
             "has_version", _now()),
        )
        store.db.commit()
        if art.claims:
            write_claims(store, art.artifact_id, cid, art.claims, outcome.source_id)


def write_claims(store, artifact_id: str, commit_id: str, claims: list[str], source_id: str | None) -> None:
    """Claim `claim:` sentinel rows + states/derived_from edges."""
    for text in claims:
        clm_id = ids_mod.new_id("clm_")
        with store._tx() as db:
            db.execute(
                "INSERT INTO claims(id, text, artifact_id, commit_id, sid, created_at) VALUES (?,?,?,?,?,?)",
                (clm_id, text, artifact_id, commit_id, None, _now()),
            )
            _add_edge(db, "commit", commit_id, "claim", clm_id, "states")
            if source_id:
                _add_edge(db, "claim", clm_id, "source", source_id, "derived_from")


def _store_unit(store, unit: ParsedUnit) -> str:
    """Write the unit's content-addressed blobs; return the root hash."""
    if unit.kind == "codebase":
        for f in unit.files:
            store.put_blob(f.kind, f.data)
        return store.put_blob(unit.kind_tag, unit.storage_bytes)
    return store.put_blob(unit.kind_tag, unit.storage_bytes)


def _add_edge(db, from_kind, from_id, to_kind, to_id, relation) -> str:
    pe_id = ids_mod.new_id("pe_")
    db.execute(
        "INSERT OR IGNORE INTO provenance_edges(id, from_kind, from_id, to_kind, to_id, relation, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (pe_id, from_kind, from_id, to_kind, to_id, relation, _now()),
    )
    return pe_id


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()