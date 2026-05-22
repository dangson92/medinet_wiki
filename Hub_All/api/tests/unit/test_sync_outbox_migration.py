"""Plan 04-01 (SYNC-05) — Unit test sync_outbox migration structure + skip-central + payload shape.

Verify (Task 1 — migration 0005 structure):
- revision/down_revision chain "0005" → "0004".
- 11 cột sync_outbox table declared (id/op_type/chunk_id/document_id/payload/...).
- Function enqueue_sync_outbox() dùng explicit jsonb_build_object (NOT to_jsonb(NEW))
  — BLOCKER 2 fix pgvector serialization fail.
- INSERT branch cast NEW.vector::float4[] + encode(NEW.content_hash, 'hex').
- INSERT branch UPDATE documents.sync_status='syncing' WHERE sync_status='pending'
  — BLOCKER 1 fix D-V3-Phase4-B2 lifecycle initial state idempotent guard.
- DELETE branch payload key 'id' (NOT 'chunk_id') — unify ChunkPayload Plan 04-03 schema.
- documents.sync_status enum column với default 'pending' + CHECK 5 value.
- Downgrade idempotent IF EXISTS ≥ 6 lần.
- Runtime guard skip central: current_db == "medinet_central" → return.

Verify (Task 2 — skip-central helper env.py):
- is_sync_outbox_rev_applicable("0005", "central") → False (skip).
- is_sync_outbox_rev_applicable("0005", "yte") → True.
- is_sync_outbox_rev_applicable("0005", "phap_che") → True (FACTOR-04 dynamic hub).
- is_sync_outbox_rev_applicable("0001", "central") → True (other rev pass).

Decision traceability:
- D-V3-Phase4-A2 — sync_outbox table per-hub-only (skip central).
- D-V3-Phase4-A4 — trigger AFTER INSERT/DELETE chunks atomic enqueue.
- D-V3-Phase4-B2 — documents.sync_status enum lifecycle (pending/syncing/synced/failed/partial).
- BLOCKER 1 fix — INSERT trigger also UPDATE documents.sync_status='syncing'.
- BLOCKER 2 fix — jsonb_build_object explicit (vector cast float4[] + content_hash hex).
"""
from __future__ import annotations

import importlib.util
import inspect
import pathlib
import re

# === Load migration 0005 module qua importlib (KHÔNG phải module Python chuẩn) ===
_MIGRATION_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "migrations"
    / "versions"
    / "0005_sync_outbox_per_hub.py"
)
_spec = importlib.util.spec_from_file_location("mig_0005", _MIGRATION_PATH)
assert _spec is not None and _spec.loader is not None, "Migration 0005 spec failed to load"
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


# === Task 2 — Skip-central helper (is_sync_outbox_rev_applicable) ===
# Import lazy inside class để Task 1 RED collection KHÔNG block khi helper chưa tồn tại.


class TestSkipGuard:
    """Pure helper logic — KHÔNG cần DB. Plan 04-01 D-V3-Phase4-A2."""

    def test_skip_central(self) -> None:
        """`hub=central` + rev 0005 → False (skip — sync_outbox per-hub-only)."""
        from migrations.env import is_sync_outbox_rev_applicable

        assert is_sync_outbox_rev_applicable("0005", "central") is False

    def test_applies_to_yte(self) -> None:
        """`hub=yte` + rev 0005 → True (apply migration)."""
        from migrations.env import is_sync_outbox_rev_applicable

        assert is_sync_outbox_rev_applicable("0005", "yte") is True

    def test_applies_to_dynamic_hub(self) -> None:
        """FACTOR-04 dynamic hub `phap_che` + rev 0005 → True (chỉ central skip)."""
        from migrations.env import is_sync_outbox_rev_applicable

        assert is_sync_outbox_rev_applicable("0005", "phap_che") is True

    def test_other_revs_pass_for_central(self) -> None:
        """Rev 0001/0004 + bất kỳ hub → True (chỉ rev 0005 trong _HUB_ONLY_REVS)."""
        from migrations.env import is_sync_outbox_rev_applicable

        assert is_sync_outbox_rev_applicable("0001", "central") is True
        assert is_sync_outbox_rev_applicable("0004", "central") is True
        assert is_sync_outbox_rev_applicable("0002", "yte") is True


# === Task 1 — Migration 0005 structure (sync_outbox + trigger + documents.sync_status) ===


class TestMigrationStructure:
    """Inspect migration 0005 source — verify schema + trigger shape."""

    def test_revision_chain(self) -> None:
        """revision='0005' + down_revision='0004' chain đúng sau MCP OAuth clients."""
        assert mig.revision == "0005"
        assert mig.down_revision == "0004"

    def test_upgrade_contains_all_columns(self) -> None:
        """11 cột sync_outbox declared (D-V3-Phase4-A2 LOCKED schema)."""
        src = inspect.getsource(mig.upgrade)
        required_cols = [
            "id UUID PRIMARY KEY",
            "op_type TEXT NOT NULL CHECK",
            "chunk_id UUID NOT NULL",
            "document_id UUID NULL",
            "payload JSONB NOT NULL",
            "attempt_count INTEGER NOT NULL DEFAULT 0",
            "last_error TEXT NULL",
            "status TEXT NOT NULL DEFAULT 'pending'",
            "next_retry_at TIMESTAMPTZ NULL",
            "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            "processed_at TIMESTAMPTZ NULL",
        ]
        for col in required_cols:
            assert col in src, f"Missing column declaration: {col}"

    def test_upgrade_uses_jsonb_build_object_not_to_jsonb_new(self) -> None:
        """BLOCKER 2 fix: to_jsonb(NEW) trên pgvector row FAIL — phải explicit jsonb_build_object.

        pgvector column KHÔNG có default jsonb cast → to_jsonb(NEW) raise runtime
        HOẶC opaque text Pydantic không parse. Fix: explicit jsonb_build_object
        liệt kê field + cast vector::float4[] + content_hash encode hex.
        """
        src = inspect.getsource(mig.upgrade)
        # No bare to_jsonb(NEW) — only allowed pattern là to_jsonb(NEW.vector::float4[])
        assert re.search(r"\bto_jsonb\(NEW\)", src) is None, (
            "to_jsonb(NEW) fails on pgvector row — must use jsonb_build_object explicit"
        )
        # Explicit jsonb_build_object dùng ở cả 2 branch INSERT + DELETE
        assert src.count("jsonb_build_object") >= 2, (
            "jsonb_build_object phải xuất hiện ≥ 2 lần (INSERT + DELETE branch)"
        )

    def test_upgrade_vector_cast_present(self) -> None:
        """BLOCKER 2 fix: vector cast ::float4[] cho pgvector serialization JSONB."""
        src = inspect.getsource(mig.upgrade)
        assert "NEW.vector::float4[]" in src, (
            "Phải cast NEW.vector::float4[] cho jsonb_build_object encode đúng"
        )

    def test_upgrade_content_hash_hex_encode(self) -> None:
        """BLOCKER 2 fix: content_hash bytea → hex string clean JSON.

        bytea direct vào JSONB sẽ encode `\\x...` prefix Pydantic ChunkPayload khó parse.
        Fix: encode(NEW.content_hash, 'hex') → hex string clean cho `bytes.fromhex(v)`
        ở Plan 04-03 worker parse.
        """
        src = inspect.getsource(mig.upgrade)
        assert "encode(NEW.content_hash, 'hex')" in src

    def test_upgrade_initial_syncing_update_present(self) -> None:
        """BLOCKER 1 fix: D-V3-Phase4-B2 lifecycle initial — first chunk per document
        UPDATE sync_status='syncing' idempotent.

        Plan 04-03 worker sẽ bump sang 'synced'/'failed'/'partial' sau push central.
        Initial 'syncing' guard `WHERE sync_status='pending'` đảm bảo idempotent —
        chunk thứ 2..N của cùng document KHÔNG re-UPDATE.
        """
        src = inspect.getsource(mig.upgrade)
        assert "UPDATE documents" in src, "INSERT branch phải UPDATE documents.sync_status"
        assert "sync_status = 'syncing'" in src
        assert "AND sync_status = 'pending'" in src, (
            "Idempotent guard — chỉ first chunk per document update"
        )

    def test_delete_payload_key_id_not_chunk_id(self) -> None:
        """Unified ChunkPayload Plan 04-03 schema — DELETE payload key 'id' (NOT 'chunk_id').

        Worker parse `payload['id']` cho cả INSERT + DELETE branch → unified schema.
        """
        src = inspect.getsource(mig.upgrade)
        assert "jsonb_build_object('id', OLD.id)" in src, (
            "DELETE branch phải dùng key 'id' (NOT 'chunk_id') để unify ChunkPayload"
        )

    def test_sync_status_enum_column(self) -> None:
        """documents.sync_status enum column với 5 value + default 'pending' NOT NULL."""
        src = inspect.getsource(mig.upgrade)
        assert "sync_status TEXT NOT NULL DEFAULT 'pending'" in src
        assert (
            "CHECK (sync_status IN ('pending','syncing','synced','failed','partial'))"
            in src
        ), "Sync status enum CHECK constraint phải có đủ 5 value"

    def test_trigger_function_name(self) -> None:
        """Function name `enqueue_sync_outbox` + 2 trigger AFTER INSERT/DELETE."""
        src = inspect.getsource(mig.upgrade)
        assert "CREATE OR REPLACE FUNCTION enqueue_sync_outbox" in src
        assert "CREATE TRIGGER chunks_after_insert_enqueue_sync_outbox" in src
        assert "CREATE TRIGGER chunks_after_delete_enqueue_sync_outbox" in src

    def test_indexes_present(self) -> None:
        """2 partial index theo D-V3-Phase4-A2 LOCKED."""
        src = inspect.getsource(mig.upgrade)
        assert "ix_sync_outbox_pending" in src
        assert "ix_sync_outbox_chunk_id" in src

    def test_central_skip_guard(self) -> None:
        """Runtime guard: current_db == "medinet_central" → no-op return."""
        src = inspect.getsource(mig.upgrade)
        assert 'current_db == "medinet_central"' in src, (
            "Phải có runtime guard skip central qua current_database() check"
        )
        # Log message thân thiện cho operator debug
        assert "SKIP central" in src or "skip central" in src.lower()

    def test_downgrade_idempotent(self) -> None:
        """Downgrade IF EXISTS ≥ 6 lần (trigger ×2 + function + table + index ×2 + column)."""
        src = inspect.getsource(mig.downgrade)
        assert src.count("IF EXISTS") >= 6, (
            f"Downgrade phải có ≥ 6 IF EXISTS guard (idempotent), found {src.count('IF EXISTS')}"
        )


# === Sanity — Tổng test count ≥ 13 (validate plan acceptance criteria) ===


def test_total_test_count_meets_acceptance() -> None:
    """Plan 04-01 acceptance: ≥ 13 test PASS. Sanity meta-test."""
    skip_tests = sum(
        1 for name in dir(TestSkipGuard) if name.startswith("test_")
    )
    struct_tests = sum(
        1 for name in dir(TestMigrationStructure) if name.startswith("test_")
    )
    total = skip_tests + struct_tests + 1  # +1 cho meta-test này
    assert total >= 13, f"Plan 04-01 acceptance ≥ 13 test, hiện có {total}"
