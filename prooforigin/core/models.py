"""SQLAlchemy ORM models for ProofOrigin."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


JSONType = JSONB().with_variant(JSON(), "sqlite")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None]
    siret: Mapped[str | None]
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_private_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    private_key_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    private_key_salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kyc_level: Mapped[str] = mapped_column(String(32), default="unverified")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_token: Mapped[str | None]
    verification_sent_at: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    credits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    proofs: Mapped[list["Proof"]] = relationship(back_populates="user", cascade="all,delete")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all,delete")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user", cascade="all,delete")
    reports: Mapped[list["Report"]] = relationship(back_populates="user", cascade="all,delete")


class Proof(Base):
    __tablename__ = "proofs"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    file_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    file_name: Mapped[str | None]
    mime_type: Mapped[str | None]
    file_size: Mapped[int | None]
    phash: Mapped[str | None]
    dhash: Mapped[str | None]
    text_embedding: Mapped[list[float] | None] = mapped_column(JSONType)
    image_embedding: Mapped[list[float] | None] = mapped_column(JSONType)
    anchored_at: Mapped[datetime | None]
    blockchain_tx: Mapped[str | None]
    anchor_signature: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="proofs")
    files: Mapped[list["ProofFile"]] = relationship(back_populates="proof", cascade="all,delete")
    matches: Mapped[list["SimilarityMatch"]] = relationship(
        back_populates="proof", cascade="all,delete", foreign_keys="SimilarityMatch.proof_id"
    )
    alerts: Mapped[list["Alert"]] = relationship(back_populates="proof", cascade="all,delete")
    anchor_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("anchor_batches.id"), nullable=True, index=True
    )
    anchor_batch: Mapped["AnchorBatch" | None] = relationship(back_populates="proofs")
    relations: Mapped[list["ProofRelation"]] = relationship(
        back_populates="source_proof", cascade="all,delete", foreign_keys="ProofRelation.source_proof_id"
    )


class ProofFile(Base):
    __tablename__ = "proof_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proof_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proofs.id"), nullable=False)
    filename: Mapped[str]
    mime: Mapped[str | None]
    size: Mapped[int | None]
    storage_ref: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    proof: Mapped["Proof"] = relationship(back_populates="files")


class SimilarityMatch(Base):
    __tablename__ = "similarity_matches"
    __table_args__ = (UniqueConstraint("proof_id", "matched_proof_id", name="uniq_match"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proof_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proofs.id"), nullable=False)
    matched_proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proofs.id"))
    score: Mapped[float] = mapped_column()
    match_type: Mapped[str] = mapped_column(String(32))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    proof: Mapped["Proof"] = relationship(
        back_populates="matches", foreign_keys=[proof_id], viewonly=False
    )
    matched_proof: Mapped["Proof"] = relationship(
        foreign_keys=[matched_proof_id], viewonly=True
    )
    relation: Mapped["ProofRelation" | None] = relationship(back_populates="match", uselist=False)


class SimilarityIndex(Base):
    __tablename__ = "similarity_index"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proof_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proofs.id"), nullable=False, index=True)
    vector: Mapped[list[float]] = mapped_column(JSONType, nullable=False)
    vector_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    proof: Mapped["Proof"] = relationship()


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    quota: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="api_keys")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    stripe_charge: Mapped[str] = mapped_column(String(255), unique=True)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    checkout_session: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(back_populates="payments")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proof_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proofs.id"), nullable=False)
    match_proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proofs.id"))
    score: Mapped[float] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    proof: Mapped["Proof"] = relationship(back_populates="alerts", foreign_keys=[proof_id])
    match_proof: Mapped["Proof"] = relationship(foreign_keys=[match_proof_id], viewonly=True)
    

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proofs.id"))
    match_id: Mapped[int | None] = mapped_column(ForeignKey("similarity_matches.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="reports")
    proof: Mapped["Proof"] = relationship()
    match: Mapped["SimilarityMatch"] = relationship()


class ProofRelation(Base):
    __tablename__ = "proof_relations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_proof_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proofs.id"), nullable=False)
    related_proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proofs.id"))
    similarity_match_id: Mapped[int | None] = mapped_column(ForeignKey("similarity_matches.id"))
    relation_type: Mapped[str] = mapped_column(String(32), default="suspected_copy")
    score: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source_proof: Mapped["Proof"] = relationship(
        back_populates="relations", foreign_keys=[source_proof_id]
    )
    related_proof: Mapped["Proof"] = relationship(foreign_keys=[related_proof_id], viewonly=True)
    match: Mapped["SimilarityMatch"] = relationship(back_populates="relation")


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    webhook_url: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None]
    total_items: Mapped[int | None]
    processed_items: Mapped[int | None]
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    user: Mapped["User"] = relationship()


class AnchorBatch(Base):
    __tablename__ = "anchor_batches"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    merkle_root: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    transaction_hash: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    anchored_at: Mapped[datetime | None]

    proofs: Mapped[list["Proof"]] = relationship(back_populates="anchor_batch")


class KeyRevocation(Base):
    __tablename__ = "key_revocations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    old_public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


__all__ = [
    "User",
    "Proof",
    "ProofFile",
    "SimilarityMatch",
    "SimilarityIndex",
    "ApiKey",
    "Payment",
    "UsageLog",
    "Alert",
    "Report",
    "BatchJob",
    "ProofRelation",
    "AnchorBatch",
    "KeyRevocation",
]
