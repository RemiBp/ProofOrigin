"""Integration checks for key public API surfaces."""

from __future__ import annotations

import json
import os
import sys
import types
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Provide lightweight shims for optional dependencies so imports always work.

if "reportlab" not in sys.modules:  # pragma: no cover - optional runtime dep
    fake_reportlab = types.ModuleType("reportlab")
    fake_reportlab_lib = types.ModuleType("reportlab.lib")
    fake_colors = types.ModuleType("reportlab.lib.colors")
    fake_colors.HexColor = lambda value: value
    fake_colors.black = "#000000"
    fake_pagesizes = types.ModuleType("reportlab.lib.pagesizes")
    fake_pagesizes.A4 = (595.27, 841.89)
    fake_units = types.ModuleType("reportlab.lib.units")
    fake_units.mm = 1

    class DummyCanvas:
        def __init__(self, buffer, pagesize=None):
            self._buffer = buffer

        def setTitle(self, *args, **kwargs):
            pass

        def setFillColor(self, *args, **kwargs):
            pass

        def setFont(self, *args, **kwargs):
            pass

        def drawString(self, *args, **kwargs):
            pass

        def drawRightString(self, *args, **kwargs):
            pass

        def showPage(self):
            pass

        def save(self):
            if hasattr(self._buffer, "write"):
                self._buffer.write(b"stub-certificate")

    fake_pdfgen = types.ModuleType("reportlab.pdfgen")
    fake_pdfgen_canvas = types.ModuleType("reportlab.pdfgen.canvas")
    fake_pdfgen_canvas.Canvas = DummyCanvas

    fake_reportlab.lib = fake_reportlab_lib
    fake_reportlab_lib.colors = fake_colors
    fake_reportlab_lib.pagesizes = fake_pagesizes
    fake_reportlab_lib.units = fake_units
    fake_pdfgen.canvas = fake_pdfgen_canvas

    sys.modules.setdefault("reportlab", fake_reportlab)
    sys.modules.setdefault("reportlab.lib", fake_reportlab_lib)
    sys.modules.setdefault("reportlab.lib.colors", fake_colors)
    sys.modules.setdefault("reportlab.lib.pagesizes", fake_pagesizes)
    sys.modules.setdefault("reportlab.lib.units", fake_units)
    sys.modules.setdefault("reportlab.pdfgen", fake_pdfgen)
    sys.modules.setdefault("reportlab.pdfgen.canvas", fake_pdfgen_canvas)

if "faiss" not in sys.modules:  # pragma: no cover - optional runtime dep
    class _DummyIndex:
        def __init__(self, dimension: int):
            self.dimension = dimension
            self.ntotal = 0

        def reset(self) -> None:
            self.ntotal = 0

        def add(self, vectors) -> None:
            self.ntotal += len(list(vectors))

        def search(self, vec, top_k: int):
            distances = np.zeros((1, top_k), dtype=np.float32)
            indices = -np.ones((1, top_k), dtype=int)
            return distances, indices

    import importlib.machinery

    fake_faiss = types.ModuleType("faiss")
    fake_faiss.METRIC_INNER_PRODUCT = 0
    fake_faiss.METRIC_L2 = 1
    fake_faiss.IndexFlatIP = lambda dim: _DummyIndex(dim)
    fake_faiss.IndexFlatL2 = lambda dim: _DummyIndex(dim)
    fake_faiss.read_index = lambda path: _DummyIndex(0)
    fake_faiss.__spec__ = importlib.machinery.ModuleSpec("faiss", loader=None)
    sys.modules.setdefault("faiss", fake_faiss)


# ---------------------------------------------------------------------------
# Import application modules after shims are in place.

from prooforigin.api.dependencies.database import get_db
from prooforigin.api.main import create_app
from prooforigin.api.routers import public_api, public_verify
from prooforigin.core import models
from prooforigin.core.database import Base
from prooforigin.core.settings import get_settings
from prooforigin.services.proofs import ProofRegistrationService
from prooforigin.services.storage import get_storage_service
from prooforigin.services.ledger import TransparencyLedger


@pytest.fixture(scope="module")
def app_context(tmp_path_factory: pytest.TempPathFactory):
    """Create an isolated app, database, and storage sandbox."""

    data_dir = tmp_path_factory.mktemp("data")
    db_path = data_dir / "public-api.db"
    storage_dir = tmp_path_factory.mktemp("storage")

    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    Base.metadata.create_all(bind=engine)

    os.environ.setdefault("PROOFORIGIN_ENABLE_FAISS", "0")
    os.environ.setdefault("PROOFORIGIN_BLOCKCHAIN_ENABLED", "false")
    os.environ.setdefault("PROOFORIGIN_MULTI_ANCHOR_TARGETS", "[]")
    os.environ["PROOFORIGIN_STORAGE_LOCAL_PATH"] = str(storage_dir)

    get_settings.cache_clear()

    # Reset singleton services so they pick up the fresh settings.
    import prooforigin.services.storage as storage_module

    storage_module._storage_service = None
    public_api.registration_service = ProofRegistrationService(get_settings())
    public_verify.storage_service = get_storage_service()
    public_verify.ledger_service = TransparencyLedger(get_settings())

    original_queue_event = public_verify.queue_event
    public_verify.queue_event = lambda *args, **kwargs: None

    app = create_app()

    def override_get_db():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    context = {
        "app": app,
        "SessionLocal": testing_session,
        "storage_dir": storage_dir,
        "restore_queue_event": original_queue_event,
    }
    yield context

    app.dependency_overrides.clear()
    public_verify.queue_event = original_queue_event


@pytest.fixture(scope="module")
def client(app_context) -> TestClient:
    return TestClient(app_context["app"])


@pytest.fixture(scope="module")
def auth_context(app_context) -> Dict[str, object]:
    session_maker = app_context["SessionLocal"]
    session = session_maker()

    from prooforigin.core.security import (
        encrypt_private_key,
        generate_ed25519_keypair,
        hash_password,
    )

    private_key, public_key = generate_ed25519_keypair()
    encrypted_private_key, nonce, salt = encrypt_private_key(private_key, "passphrase")

    user = models.User(
        email="integration@example.com",
        password_hash=hash_password("passphrase"),
        display_name="Integration Tester",
        public_key=public_key,
        encrypted_private_key=encrypted_private_key,
        private_key_nonce=nonce,
        private_key_salt=salt,
        credits=10,
        subscription_plan="pro",
    )
    session.add(user)
    session.flush()

    api_key = models.ApiKey(user_id=user.id, key="test-api-key", quota=10)
    session.add(api_key)
    session.commit()
    session.close()

    return {
        "user_id": user.id,
        "headers": {"X-API-Key": "test-api-key"},
        "password": "passphrase",
    }


@pytest.fixture(scope="module")
def registered_proof(app_context, auth_context) -> Dict[str, object]:
    session_maker = app_context["SessionLocal"]
    storage_dir: Path = app_context["storage_dir"]
    session = session_maker()

    proof_id = uuid.uuid4()
    file_hash = "b3a9f0c1e4" * 6
    manifest_payload = {
        "@context": [
            "https://schema.c2pa.org/1.3.0/context.json",
            "https://prooforigin.io/ns/proof.json",
        ],
        "proof": {"id": str(proof_id), "hash": file_hash},
    }
    manifest_path = storage_dir / f"{proof_id}.c2pa.json"
    manifest_path.write_text(json.dumps(manifest_payload))

    proof = models.Proof(
        id=proof_id,
        user_id=auth_context["user_id"],
        file_hash=file_hash,
        normalized_hash=file_hash,
        signature="c2lnbmF0dXJl",
        metadata_json={"title": "Integration Proof"},
        file_name="origin.txt",
        mime_type="text/plain",
        file_size=24,
        pipeline_version="v2",
        risk_score=0,
        created_at=datetime.utcnow(),
        c2pa_manifest_ref=str(manifest_path),
    )
    session.add(proof)
    session.commit()
    session.close()

    return {"id": str(proof_id), "file_hash": file_hash, "manifest": manifest_payload}


def test_list_proofs_includes_registered_entry(
    client: TestClient, auth_context: Dict[str, object], registered_proof: Dict[str, object]
) -> None:
    response = client.get("/api/v1/proofs", headers=auth_context["headers"])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["id"] == registered_proof["id"] for item in payload["items"])


def test_anchor_endpoint_returns_current_state(
    client: TestClient, auth_context: Dict[str, object], registered_proof: Dict[str, object]
) -> None:
    response = client.post(
        f"/api/v1/anchor/{registered_proof['id']}", headers=auth_context["headers"]
    )
    assert response.status_code == 200, response.text
    anchored = response.json()
    assert anchored["id"] == registered_proof["id"]
    assert anchored["blockchain_tx"] is None


def test_similarity_endpoint_returns_stubbed_match(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    auth_context: Dict[str, object],
    registered_proof: Dict[str, object],
) -> None:
    monkeypatch.setattr(
        public_api.similarity_engine,
        "compute_text_embedding",
        lambda text: [0.1, 0.2, 0.3],
    )

    monkeypatch.setattr(
        public_api.similarity_engine,
        "query_vector_store",
        lambda vector_type, vector, top_k=5: [uuid.UUID(registered_proof["id"])],
    )

    response = client.post(
        "/api/v1/similarity",
        json={"text": "futuristic"},
        headers=auth_context["headers"],
    )
    assert response.status_code == 200, response.text
    results = response.json()
    assert any(item["id"] == registered_proof["id"] for item in results)


def test_manifest_route_serves_embedded_payload(
    client: TestClient, registered_proof: Dict[str, object]
) -> None:
    response = client.get(f"/verify/{registered_proof['file_hash']}/manifest")
    assert response.status_code == 200, response.text
    manifest = response.json()
    assert manifest["proof"]["id"] == registered_proof["id"]

