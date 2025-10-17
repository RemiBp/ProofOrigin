"""Pydantic schemas for API requests and responses."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    siret: str | None = None


class UserProfile(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    siret: str | None = None
    kyc_level: str
    credits: int
    is_verified: bool
    created_at: datetime


class ProofMetadata(BaseModel):
    title: str
    description: str | None = None
    license: str | None = None
    tags: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class ProofResponse(BaseModel):
    id: uuid.UUID
    file_hash: str
    signature: str
    metadata: dict[str, Any] | None
    anchored_at: datetime | None
    blockchain_tx: str | None
    created_at: datetime
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    matches: list[dict[str, Any]] = Field(default_factory=list)
    proof_artifact: dict[str, Any] | None = None


class ProofListResponse(BaseModel):
    items: list[ProofResponse]
    total: int
    page: int
    page_size: int


class VerifyRequest(BaseModel):
    proof_id: Optional[uuid.UUID] = None
    signature: Optional[str] = None
    public_key: Optional[str] = None


class VerifyResult(BaseModel):
    valid_signature: bool
    original_hash: str
    anchored: bool
    blockchain_tx: str | None
    author_id: uuid.UUID
    timestamp: datetime


class SimilarityRequest(BaseModel):
    text: str | None = None
    top_k: int = 5


class UsageResponse(BaseModel):
    proofs_generated: int
    verifications_performed: int
    remaining_credits: int
    last_payment: datetime | None


class ReportRequest(BaseModel):
    proof_id: uuid.UUID | None = None
    match_id: int | None = None
    notes: str | None = None
    external_links: list[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    id: int
    status: str
    created_at: datetime


class BatchVerifyRequest(BaseModel):
    proof_ids: list[uuid.UUID]
    webhook_url: str | None = None


class BatchVerifyResponse(BaseModel):
    job_id: uuid.UUID
    status: str


class StripeCheckoutResponse(BaseModel):
    checkout_url: str
    credits: int


class UploadKeyRequest(BaseModel):
    private_key: str


__all__ = [
    "TokenResponse",
    "RefreshRequest",
    "RegisterRequest",
    "UserProfile",
    "ProofMetadata",
    "ProofResponse",
    "ProofListResponse",
    "VerifyRequest",
    "VerifyResult",
    "SimilarityRequest",
    "UsageResponse",
    "ReportRequest",
    "ReportResponse",
    "BatchVerifyRequest",
    "BatchVerifyResponse",
    "StripeCheckoutResponse",
    "UploadKeyRequest",
]
