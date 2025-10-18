"""Pydantic schemas for API requests and responses."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

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
    is_admin: bool
    created_at: datetime
    subscription_plan: str


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
    anchor_batch_id: uuid.UUID | None = None


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


class HashVerificationResponse(BaseModel):
    exists: bool
    proof_id: uuid.UUID | None = None
    created_at: datetime | None = None
    owner_id: uuid.UUID | None = None
    owner_email: str | None = None
    anchored: bool = False
    blockchain_tx: str | None = None


class PublicProofStatus(BaseModel):
    hash: str
    status: Literal["verified", "missing"]
    created_at: datetime | None
    owner: dict[str, Any] | None
    download_url: str | None
    blockchain_tx: str | None
    anchored: bool
    proof_id: uuid.UUID | None


class SimilarityRequest(BaseModel):
    text: str | None = None
    top_k: int = 5


class UsageResponse(BaseModel):
    proofs_generated: int
    verifications_performed: int
    remaining_credits: int
    last_payment: datetime | None
    next_anchor_batch: datetime | None = None
    plan: str
    rate_limit_per_minute: int
    monthly_quota: int


class ReportRequest(BaseModel):
    proof_id: uuid.UUID | None = None
    match_id: int | None = None
    notes: str | None = None
    external_links: list[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    evidence_pack: str | None = None


class BatchVerifyRequest(BaseModel):
    proof_ids: list[uuid.UUID]
    webhook_url: str | None = None


class BatchVerifyResponse(BaseModel):
    job_id: uuid.UUID
    status: str


class ApiKeyResponse(BaseModel):
    id: int
    key: str
    quota: int
    created_at: datetime
    last_used_at: datetime | None = None
    plan: str


class ProofSubmission(BaseModel):
    content: str | None = None
    text: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] | None = None
    key_password: str


class BatchProofItem(BaseModel):
    content: str | None = None
    text: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] | None = None


class BatchProofRequest(BaseModel):
    items: list[BatchProofItem]
    key_password: str


class BatchProofResult(BaseModel):
    success: bool
    proof: ProofResponse | None = None
    error: str | None = None


class BatchProofResponsePayload(BaseModel):
    results: list[BatchProofResult]


class AIProofRequest(BaseModel):
    model_name: str
    prompt: str | None = None
    content: str | None = None
    text: str | None = None
    metadata: dict[str, Any] | None = None
    key_password: str
    webhook_event: str | None = None


class StripeCheckoutResponse(BaseModel):
    checkout_url: str
    credits: int
    plan: str


class StripeCheckoutRequest(BaseModel):
    plan: Literal["free", "pro", "business"] = "pro"


class UploadKeyRequest(BaseModel):
    private_key: str


class RotateKeyRequest(BaseModel):
    password: str


class VerificationRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str


class LedgerEntryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    file_hash: str
    signature: str
    metadata: dict[str, Any] | None
    created_at: datetime
    anchored_at: datetime | None
    blockchain_tx: str | None
    anchor_signature: str | None
    anchor_batch_id: uuid.UUID | None = None
    matches: list[dict[str, Any]]
    alerts: list[dict[str, Any]]


class AdminUserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    credits: int
    is_verified: bool
    kyc_level: str
    created_at: datetime


class AdminProofSummary(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    file_name: str | None
    created_at: datetime
    anchored_at: datetime | None
    blockchain_tx: str | None
    suspicious_matches: int


class WebhookSubscriptionCreate(BaseModel):
    target_url: str
    event: str
    secret: str | None = None


class WebhookSubscriptionResponse(BaseModel):
    id: int
    target_url: str
    event: str
    created_at: datetime
    is_active: bool


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
    "HashVerificationResponse",
    "PublicProofStatus",
    "SimilarityRequest",
    "UsageResponse",
    "ReportRequest",
    "ReportResponse",
    "BatchVerifyRequest",
    "BatchVerifyResponse",
    "StripeCheckoutResponse",
    "UploadKeyRequest",
    "RotateKeyRequest",
    "VerificationRequest",
    "ResendVerificationRequest",
    "LedgerEntryResponse",
    "AdminUserSummary",
    "AdminProofSummary",
    "WebhookSubscriptionCreate",
    "WebhookSubscriptionResponse",
    "ApiKeyResponse",
    "ProofSubmission",
    "BatchProofItem",
    "BatchProofRequest",
    "BatchProofResult",
    "BatchProofResponsePayload",
    "AIProofRequest",
    "StripeCheckoutRequest",
]
