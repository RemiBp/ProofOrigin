"""Flask routes and API endpoints for ProofOrigin."""
from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from .crypto import (
    compute_hash_from_path,
    compute_hash_from_stream,
    load_public_key_pem,
    sign_hash,
)
from .database import connect
from .services.blockchain import BlockchainAnchor
from .services.fuzzy import FuzzyMatcher

bp = Blueprint("prooforigin", __name__)


@bp.app_template_filter("timestamp_to_date")
def timestamp_to_date(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Date inconnue"


def _matcher() -> FuzzyMatcher:
    matcher: FuzzyMatcher | None = current_app.extensions.get("fuzzy_matcher")
    if matcher is None:
        matcher = FuzzyMatcher(
            image_threshold=current_app.config["SIMILARITY_IMAGE_THRESHOLD"],
            text_match_threshold=current_app.config["SIMILARITY_TEXT_THRESHOLD"],
        )
        current_app.extensions["fuzzy_matcher"] = matcher
    return matcher


def _database_connection() -> sqlite3.Connection:
    return connect(current_app.config["DATABASE"])


def _load_public_key() -> str:
    return load_public_key_pem(current_app.config["PUBLIC_KEY_PATH"])


@bp.route("/", methods=["GET"])
def home() -> str:
    return render_template("index.html")


@bp.route("/register", methods=["POST"])
def register() -> tuple[str, int] | str:
    uploaded = request.files.get("file")
    if not uploaded:
        return render_template("result.html", message="❌ Aucun fichier reçu"), 400

    temp_dir = Path(current_app.config["TEMP_DIR"])
    temp_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp:
        uploaded.save(tmp.name)
        temp_path = Path(tmp.name)

    try:
        hash_value = compute_hash_from_path(str(temp_path))
        signature = sign_hash(hash_value, current_app.config["PRIVATE_KEY_PATH"])
        timestamp = time.time()

        matcher = _matcher()
        analysis = matcher.analyze_file(str(temp_path))
        file_size = temp_path.stat().st_size
        analysis_metadata = json.dumps(analysis, ensure_ascii=False)

        with _database_connection() as conn:
            cursor = conn.execute(
                "SELECT id, filename, phash, semantic_hash, metadata FROM proofs"
            )
            existing_proofs = []
            for row in cursor.fetchall():
                metadata = {}
                if row[4]:
                    try:
                        metadata = json.loads(row[4])
                    except json.JSONDecodeError:
                        metadata = {}
                existing_proofs.append(
                    {
                        "id": row[0],
                        "filename": row[1],
                        "phash": row[2],
                        "semantic_hash": row[3],
                        "raw_text": metadata.get("raw_text"),
                    }
                )

            similar_proofs = matcher.find_similar_content(analysis, existing_proofs)

            try:
                conn.execute(
                    """
                    INSERT INTO proofs (
                        hash, filename, signature, public_key, timestamp,
                        phash, dhash, semantic_hash, content_type, file_size, metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hash_value,
                        uploaded.filename,
                        signature,
                        _load_public_key(),
                        timestamp,
                        analysis.get("phash"),
                        analysis.get("dhash"),
                        analysis.get("semantic_hash"),
                        analysis.get("content_type"),
                        file_size,
                        analysis_metadata,
                    ),
                )
                proof_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                for similar in similar_proofs:
                    conn.execute(
                        """
                        INSERT INTO similarities (
                            proof_id, similar_proof_id, similarity_score, match_type, confidence
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            proof_id,
                            similar["proof_id"],
                            similar["similarity_score"],
                            similar["match_type"],
                            similar["confidence"],
                        ),
                    )

                conn.commit()

                message = (
                    f"✅ File '{uploaded.filename}' registered.<br>"
                    f"Hash: {hash_value}<br>Signature: {signature[:40]}..."
                )
                if similar_proofs:
                    message += "<br><br>🔍 Similar content detected:<br>"
                    for similar in similar_proofs[:3]:
                        message += (
                            "• {name} (similarity: {score:.2%})<br>"
                        ).format(
                            name=similar.get("filename") or "Unknown",
                            score=similar.get("similarity_score", 0.0),
                        )
            except sqlite3.IntegrityError:
                message = f"⚠️ File already exists in ledger.<br>Hash: {hash_value[:40]}..."

    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass

    return render_template("result.html", message=message)


@bp.route("/verify", methods=["POST"])
def verify() -> tuple[str, int] | str:
    uploaded = request.files.get("file")
    if not uploaded:
        return render_template("result.html", message="❌ Aucun fichier reçu"), 400

    hash_value = compute_hash_from_stream(uploaded.stream)

    with _database_connection() as conn:
        row = conn.execute(
            "SELECT filename, signature, public_key, timestamp FROM proofs WHERE hash=?",
            (hash_value,),
        ).fetchone()

    if row:
        message = (
            "✅ Verified! File: {filename}<br>Hash: {hash}<br>Timestamp: {timestamp}"
        ).format(
            filename=row[0],
            hash=hash_value[:40] + "...",
            timestamp=datetime.fromtimestamp(row[3]).strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        message = f"❌ Not found in ledger.<br>Hash: {hash_value[:40]}..."

    return render_template("result.html", message=message)


@bp.route("/list")
def list_proofs() -> str:
    with _database_connection() as conn:
        proofs = conn.execute(
            "SELECT id, filename, hash, timestamp FROM proofs ORDER BY id DESC"
        ).fetchall()

    return render_template("list.html", proofs=proofs)


@bp.route("/export/<int:proof_id>")
def export_proof(proof_id: int):
    with _database_connection() as conn:
        row = conn.execute(
            """
            SELECT filename, hash, signature, public_key, timestamp
            FROM proofs WHERE id=?
            """,
            (proof_id,),
        ).fetchone()

    if not row:
        return "Proof not found", 404

    proof_data = {
        "prooforigin_protocol": "POP v0.1",
        "proof_id": proof_id,
        "filename": row[0],
        "hash": {"algorithm": "SHA-256", "value": row[1]},
        "signature": {"algorithm": "RSA-2048-PSS", "value": row[2]},
        "public_key": row[3],
        "timestamp": {
            "unix": row[4],
            "readable": datetime.fromtimestamp(row[4]).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
        "verification_url": f"{request.host_url}verify",
        "exported_at": {
            "unix": time.time(),
            "readable": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
    }

    buffer = io.BytesIO()
    buffer.write(json.dumps(proof_data, indent=2, ensure_ascii=False).encode("utf-8"))
    buffer.seek(0)

    filename = f"proof_{proof_id}_{row[0]}.proof"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/json")


@bp.route("/api/register", methods=["POST"])
def api_register():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "No file provided"}), 400

    temp_dir = Path(current_app.config["TEMP_DIR"])
    temp_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp:
        uploaded.save(tmp.name)
        temp_path = Path(tmp.name)

    try:
        hash_value = compute_hash_from_path(str(temp_path))
        signature = sign_hash(hash_value, current_app.config["PRIVATE_KEY_PATH"])
        timestamp = time.time()

        matcher = _matcher()
        analysis = matcher.analyze_file(str(temp_path))
        file_size = temp_path.stat().st_size
        analysis_metadata = json.dumps(analysis, ensure_ascii=False)

        with _database_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO proofs (
                        hash, filename, signature, public_key, timestamp,
                        phash, dhash, semantic_hash, content_type, file_size, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hash_value,
                        uploaded.filename,
                        signature,
                        _load_public_key(),
                        timestamp,
                        analysis.get("phash"),
                        analysis.get("dhash"),
                        analysis.get("semantic_hash"),
                        analysis.get("content_type"),
                        file_size,
                        analysis_metadata,
                    ),
                )
                proof_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.commit()
            except sqlite3.IntegrityError:
                return jsonify({"error": "File already exists in ledger", "hash": hash_value}), 409
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass

    return jsonify(
        {
            "success": True,
            "proof_id": proof_id,
            "filename": uploaded.filename,
            "hash": hash_value,
            "signature": signature,
            "timestamp": timestamp,
            "export_url": f"{request.host_url}export/{proof_id}",
        }
    )


@bp.route("/api/verify", methods=["POST"])
def api_verify():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "No file provided"}), 400

    hash_value = compute_hash_from_stream(uploaded.stream)

    with _database_connection() as conn:
        row = conn.execute(
            "SELECT id, filename, signature, public_key, timestamp FROM proofs WHERE hash=?",
            (hash_value,),
        ).fetchone()

    if row:
        return jsonify(
            {
                "verified": True,
                "proof_id": row[0],
                "filename": row[1],
                "hash": hash_value,
                "signature": row[2],
                "timestamp": row[3],
                "export_url": f"{request.host_url}export/{row[0]}",
            }
        )

    return jsonify({"verified": False, "hash": hash_value, "message": "File not found in ledger"})


@bp.route("/api/proofs")
def api_list_proofs():
    try:
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "Invalid pagination parameters"}), 400

    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    with _database_connection() as conn:
        proofs = conn.execute(
            """
            SELECT id, filename, hash, timestamp, content_type, file_size
            FROM proofs
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        total = conn.execute("SELECT COUNT(*) FROM proofs").fetchone()[0]

    return jsonify(
        {
            "proofs": [
                {
                    "id": row[0],
                    "filename": row[1],
                    "hash": row[2],
                    "timestamp": row[3],
                    "content_type": row[4],
                    "file_size": row[5],
                    "export_url": f"{request.host_url}export/{row[0]}",
                }
                for row in proofs
            ],
            "count": len(proofs),
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@bp.route("/api/proofs/<int:proof_id>")
def api_get_proof_detail(proof_id: int):
    with _database_connection() as conn:
        row = conn.execute(
            """
            SELECT id, filename, hash, signature, public_key, timestamp, content_type, file_size, metadata
            FROM proofs
            WHERE id = ?
            """,
            (proof_id,),
        ).fetchone()

    if not row:
        return jsonify({"error": "Proof not found"}), 404

    metadata = None
    if row[8]:
        try:
            metadata = json.loads(row[8])
        except json.JSONDecodeError:
            metadata = row[8]

    return jsonify(
        {
            "id": row[0],
            "filename": row[1],
            "hash": row[2],
            "signature": row[3],
            "public_key": row[4],
            "timestamp": row[5],
            "content_type": row[6],
            "file_size": row[7],
            "metadata": metadata,
            "export_url": f"{request.host_url}export/{row[0]}",
        }
    )


@bp.route("/api/similar/<int:proof_id>")
def api_get_similar(proof_id: int):
    with _database_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.similarity_score, s.match_type, s.confidence, p.filename, p.id
            FROM similarities s
            JOIN proofs p ON s.similar_proof_id = p.id
            WHERE s.proof_id = ?
            ORDER BY s.similarity_score DESC
            """,
            (proof_id,),
        ).fetchall()

    return jsonify(
        {
            "proof_id": proof_id,
            "similar_proofs": [
                {
                    "similar_proof_id": row[4],
                    "filename": row[3],
                    "similarity_score": row[0],
                    "match_type": row[1],
                    "confidence": row[2],
                }
                for row in rows
            ],
            "count": len(rows),
        }
    )


@bp.route("/api/anchors")
def api_list_anchors():
    with _database_connection() as conn:
        anchors = conn.execute(
            """
            SELECT date, merkle_root, proof_count, transaction_hash, timestamp, anchor_signature
            FROM anchors
            ORDER BY timestamp DESC
            """
        ).fetchall()

    return jsonify(
        {
            "anchors": [
                {
                    "date": row[0],
                    "merkle_root": row[1],
                    "proof_count": row[2],
                    "transaction_hash": row[3],
                    "timestamp": row[4],
                    "anchor_signature": row[5],
                }
                for row in anchors
            ],
            "count": len(anchors),
        }
    )


@bp.route("/api/verify-anchor/<int:proof_id>")
def api_verify_anchor(proof_id: int):
    anchorer = BlockchainAnchor(
        rpc_url=current_app.config["BLOCKCHAIN_RPC_URL"],
        private_key=current_app.config.get("BLOCKCHAIN_PRIVATE_KEY"),
        database_path=current_app.config["DATABASE"],
    )
    result = anchorer.verify_proof_in_anchor(proof_id)
    return jsonify(result)


@bp.route("/api/anchors/run", methods=["POST"])
def api_run_anchor():
    anchorer = BlockchainAnchor(
        rpc_url=current_app.config["BLOCKCHAIN_RPC_URL"],
        private_key=current_app.config.get("BLOCKCHAIN_PRIVATE_KEY"),
        database_path=current_app.config["DATABASE"],
    )

    daily_proofs = anchorer.get_daily_proofs()
    if not daily_proofs:
        return jsonify({"anchored": False, "message": "No proofs to anchor today"})

    merkle_data = anchorer.create_daily_merkle_root(daily_proofs)
    if not merkle_data:
        return jsonify({"anchored": False, "message": "Unable to build Merkle root"}), 500

    tx_hash = anchorer.anchor_to_blockchain(merkle_data)
    anchorer.save_anchor_record(merkle_data, tx_hash)

    return jsonify(
        {
            "anchored": True,
            "transaction_hash": tx_hash,
            "merkle_root": merkle_data["merkle_root"],
            "proof_count": merkle_data["proof_count"],
            "anchor_signature": merkle_data.get("signature"),
        }
    )


__all__ = ["bp"]
