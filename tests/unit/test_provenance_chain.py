"""Provenance-chain invariants: typed edges and logical idempotency."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.src.core.objects.store import ObjectStore
from backend.src.ingestion.pipeline import _add_edge


def test_logical_provenance_edge_is_idempotent():
    store = ObjectStore(tempfile.mkdtemp())
    with store._tx() as db:
        _add_edge(db, "claim", "clm_1", "source", "src_1", "derived_from")
        _add_edge(db, "claim", "clm_1", "source", "src_1", "derived_from")
        count = db.execute(
            "SELECT COUNT(*) FROM provenance_edges WHERE from_kind=? AND from_id=? "
            "AND to_kind=? AND to_id=? AND relation=?",
            ("claim", "clm_1", "source", "src_1", "derived_from"),
        ).fetchone()[0]
    assert count == 1
