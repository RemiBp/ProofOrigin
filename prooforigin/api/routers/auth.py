"""Authentication API routes."""
from __future__ import annotations

import base64
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from prooforigin.api import schemas
from prooforigin.api.dependencies.database import get_db
from prooforigin.core import models
from prooforigin.core.security import (
    create_access_token,
    create_refresh_token,
    encrypt_private_key,
    generate_ed25519_keypair,
    hash_password,
    verify_password,
)
from prooforigin.core.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=schemas.UserProfile, status_code=status.HTTP_201_CREATED)
def register_user(payload: schemas.RegisterRequest, db: Session = Depends(get_db)) -> schemas.UserProfile:
    if db.query(models.User).filter(models.User.email == payload.email.lower()).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    private_key, public_key = generate_ed25519_keypair()
    encrypted_private_key, nonce, salt = encrypt_private_key(private_key, payload.password)

    user = models.User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        siret=payload.siret,
        public_key=public_key,
        encrypted_private_key=encrypted_private_key,
        private_key_nonce=nonce,
        private_key_salt=salt,
        credits=settings.default_credit_pack,
        verification_token=secrets.token_urlsafe(32),
        verification_sent_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return schemas.UserProfile(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        siret=user.siret,
        kyc_level=user.kyc_level,
        credits=user.credits,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.post("/login", response_model=schemas.TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> schemas.TokenResponse:
    user = db.query(models.User).filter(models.User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    access_token = create_access_token({"sub": str(user.id), "scope": "user"})
    refresh_token = create_refresh_token({"sub": str(user.id), "scope": "user"})
    expires_in = settings.access_token_expire_minutes * 60

    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/token/refresh", response_model=schemas.TokenResponse)
def refresh_token(payload: schemas.RefreshRequest, db: Session = Depends(get_db)) -> schemas.TokenResponse:
    from prooforigin.core.security import decode_token

    try:
        decoded = decode_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from None

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = db.get(models.User, decoded.get("sub"))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    access_token = create_access_token({"sub": str(user.id), "scope": "user"})
    refresh_token = create_refresh_token({"sub": str(user.id), "scope": "user"})

    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/upload-key", status_code=status.HTTP_204_NO_CONTENT)
def upload_key(
    payload: schemas.UploadKeyRequest,
    password_form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> None:
    """Allow a user to rotate their key pair by supplying a new private key."""
    user = db.query(models.User).filter(models.User.email == password_form.username.lower()).first()
    if not user or not verify_password(password_form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    try:
        raw_private = base64.b64decode(payload.private_key)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key encoding") from exc

    encrypted_private_key, nonce, salt = encrypt_private_key(raw_private, password_form.password)
    user.encrypted_private_key = encrypted_private_key
    user.private_key_nonce = nonce
    user.private_key_salt = salt
    db.add(user)
    db.commit()

