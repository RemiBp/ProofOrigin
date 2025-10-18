"""Portable proof stack with transparency log and receipts.

Revision ID: 0003_portable_proof_stack
Revises: 0002_add_subscription_plan
Create Date: 2024-11-24 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

JSONType = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")

# revision identifiers, used by Alembic.
revision = "0003_portable_proof_stack"
down_revision = "0002_add_subscription_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover - migration script
    op.add_column(
        "proofs",
        sa.Column("normalized_hash", sa.String(length=128), nullable=True),
    )
    op.add_column("proofs", sa.Column("pipeline_version", sa.String(length=16), nullable=False, server_default="v2"))
    op.add_column(
        "proofs",
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "proofs",
        sa.Column("c2pa_manifest_ref", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "proofs",
        sa.Column("merkle_leaf", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "proofs",
        sa.Column("opentimestamps_receipt", JSONType, nullable=True),
    )
    op.add_column(
        "proofs",
        sa.Column("ledger_entry_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        op.f("ix_proofs_normalized_hash"), "proofs", ["normalized_hash"], unique=False
    )
    op.create_index(
        op.f("ix_proofs_ledger_entry_id"), "proofs", ["ledger_entry_id"], unique=False
    )

    op.add_column(
        "anchor_batches",
        sa.Column("opentimestamps_receipt", JSONType, nullable=True),
    )
    op.add_column(
        "anchor_batches",
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "anchor_batches",
        sa.Column("anchored_chain", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "transparency_log_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("proof_id", sa.UUID(), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("normalized_hash", sa.String(length=128), nullable=True),
        sa.Column("merkle_root", sa.String(length=256), nullable=False),
        sa.Column("merkle_leaf", sa.String(length=256), nullable=False),
        sa.Column("parent_hash", sa.String(length=256), nullable=True),
        sa.Column("entry_hash", sa.String(length=256), nullable=False),
        sa.Column("signature", sa.String(length=512), nullable=False),
        sa.Column("transparency_log", sa.String(length=64), nullable=False, server_default="primary"),
        sa.Column("anchored_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["proof_id"], ["proofs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sequence"),
        sa.UniqueConstraint("entry_hash"),
    )
    op.create_index(
        op.f("ix_transparency_log_entries_sequence"),
        "transparency_log_entries",
        ["sequence"],
        unique=True,
    )

    op.create_table(
        "chain_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proof_id", sa.UUID(), nullable=False),
        sa.Column("transparency_entry_id", sa.UUID(), nullable=True),
        sa.Column("chain", sa.String(length=64), nullable=False),
        sa.Column("transaction_hash", sa.String(length=256), nullable=True),
        sa.Column("receipt_payload", JSONType, nullable=True),
        sa.Column("anchored_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["proof_id"], ["proofs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint([
            "transparency_entry_id"
        ], ["transparency_log_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chain_receipts_proof_id"), "chain_receipts", ["proof_id"], unique=False
    )

    op.create_table(
        "asset_fingerprints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("proof_id", sa.UUID(), nullable=False),
        sa.Column("fingerprint_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=256), nullable=True),
        sa.Column("vector", JSONType, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["proof_id"], ["proofs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_asset_fingerprints_proof_id"),
        "asset_fingerprints",
        ["proof_id"],
        unique=False,
    )

    op.create_table(
        "usage_meters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("metered_action", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("window_end", sa.DateTime(), nullable=True),
        sa.Column("metadata", JSONType, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_usage_meters_user_id"), "usage_meters", ["user_id"], unique=False
    )

    op.create_foreign_key(
        "fk_proofs_ledger_entry_id",
        "proofs",
        "transparency_log_entries",
        ["ledger_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:  # pragma: no cover - migration script
    op.drop_constraint("fk_proofs_ledger_entry_id", "proofs", type_="foreignkey")
    op.drop_index(op.f("ix_usage_meters_user_id"), table_name="usage_meters")
    op.drop_table("usage_meters")
    op.drop_index(op.f("ix_asset_fingerprints_proof_id"), table_name="asset_fingerprints")
    op.drop_table("asset_fingerprints")
    op.drop_index(op.f("ix_chain_receipts_proof_id"), table_name="chain_receipts")
    op.drop_table("chain_receipts")
    op.drop_index(op.f("ix_transparency_log_entries_sequence"), table_name="transparency_log_entries")
    op.drop_table("transparency_log_entries")
    op.drop_column("anchor_batches", "anchored_chain")
    op.drop_column("anchor_batches", "batch_size")
    op.drop_column("anchor_batches", "opentimestamps_receipt")
    op.drop_index(op.f("ix_proofs_ledger_entry_id"), table_name="proofs")
    op.drop_index(op.f("ix_proofs_normalized_hash"), table_name="proofs")
    op.drop_column("proofs", "ledger_entry_id")
    op.drop_column("proofs", "opentimestamps_receipt")
    op.drop_column("proofs", "merkle_leaf")
    op.drop_column("proofs", "c2pa_manifest_ref")
    op.drop_column("proofs", "risk_score")
    op.drop_column("proofs", "pipeline_version")
    op.drop_column("proofs", "normalized_hash")
