from datetime import datetime
from flask import Flask, request, render_template
import hashlib, time, sqlite3, os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric import utils as asym_utils
from cryptography.hazmat.backends import default_backend
from base64 import b64encode, b64decode
from flask import send_file
import json
from fuzzy_matching import FuzzyMatcher

app = Flask(__name__)
DB_FILE = "ledger.db"

# Custom Jinja2 filter for timestamp formatting
@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    """Convert timestamp to readable date format"""
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return "Date inconnue"

# Charger les clés RSA
with open("private.pem", "rb") as f:
    PRIVATE_KEY = serialization.load_pem_private_key(
        f.read(), password=None, backend=default_backend()
    )
with open("public.pem", "rb") as f:
    PUBLIC_KEY = f.read().decode()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Table principale des preuves
    c.execute("""
        CREATE TABLE IF NOT EXISTS proofs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash TEXT UNIQUE,
            filename TEXT,
            signature TEXT,
            public_key TEXT,
            timestamp REAL,
            phash TEXT,
            dhash TEXT,
            semantic_hash TEXT,
            content_type TEXT,
            file_size INTEGER,
            metadata TEXT
        )
    """)
    
    # Table des ancrages blockchain
    c.execute("""
        CREATE TABLE IF NOT EXISTS anchors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            merkle_root TEXT,
            proof_count INTEGER,
            transaction_hash TEXT,
            timestamp REAL,
            anchor_signature TEXT,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    """)

    # S'assurer que la colonne anchor_signature existe même sur une base plus ancienne
    c.execute("PRAGMA table_info(anchors)")
    anchor_columns = [row[1] for row in c.fetchall()]
    if 'anchor_signature' not in anchor_columns:
        c.execute("ALTER TABLE anchors ADD COLUMN anchor_signature TEXT")
    
    # Table des similarités détectées
    c.execute("""
        CREATE TABLE IF NOT EXISTS similarities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proof_id INTEGER,
            similar_proof_id INTEGER,
            similarity_score REAL,
            match_type TEXT,
            confidence TEXT,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (proof_id) REFERENCES proofs (id),
            FOREIGN KEY (similar_proof_id) REFERENCES proofs (id)
        )
    """)
    
    conn.commit()
    conn.close()

def compute_hash(file):
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: file.read(4096), b""):
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()

def compute_hash_from_path(file_path):
    """Calcule le hash SHA-256 d'un fichier depuis son chemin"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def sign_hash(hash_value):
    signature = PRIVATE_KEY.sign(
        bytes.fromhex(hash_value),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )
    return b64encode(signature).decode()

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    file = request.files.get("file")
    if not file:
        return "No file", 400

    # Sauvegarder temporairement le fichier pour l'analyse
    temp_path = f"temp_{int(time.time())}_{file.filename}"
    file.save(temp_path)
    
    try:
        # Calculer le hash principal
        hash_value = compute_hash_from_path(temp_path)
        signature = sign_hash(hash_value)
        timestamp = time.time()
        
        # Analyser le fichier avec fuzzy matching
        matcher = FuzzyMatcher()
        analysis = matcher.analyze_file(temp_path)
        
        # Récupérer la taille du fichier
        file_size = os.path.getsize(temp_path)
        
        # Vérifier les similarités
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Récupérer les preuves existantes pour la comparaison
        c.execute("SELECT id, filename, phash, semantic_hash FROM proofs")
        existing_proofs = [
            {
                'id': row[0],
                'filename': row[1],
                'phash': row[2],
                'semantic_hash': row[3]
            }
            for row in c.fetchall()
        ]
        
        similar_proofs = matcher.find_similar_content(analysis, existing_proofs)
        
        try:
            # Insérer la nouvelle preuve
            c.execute("""
                INSERT INTO proofs (hash, filename, signature, public_key, timestamp, 
                                  phash, dhash, semantic_hash, content_type, file_size, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hash_value, file.filename, signature, PUBLIC_KEY, timestamp,
                analysis.get('phash'), analysis.get('dhash'), analysis.get('semantic_hash'),
                analysis.get('content_type'), file_size, json.dumps(analysis)
            ))
            
            proof_id = c.lastrowid
            conn.commit()
            
            # Enregistrer les similarités détectées
            for similar in similar_proofs:
                c.execute("""
                    INSERT INTO similarities (proof_id, similar_proof_id, similarity_score, match_type, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (proof_id, similar['proof_id'], similar['similarity_score'], 
                      similar['match_type'], similar['confidence']))
            
            conn.commit()
            
            # Message de succès avec informations sur les similarités
            msg = f"✅ File '{file.filename}' registered.<br>Hash: {hash_value}<br>Signature: {signature[:40]}..."
            if similar_proofs:
                msg += f"<br><br>🔍 Similar content detected:<br>"
                for similar in similar_proofs[:3]:  # Afficher les 3 premiers
                    msg += f"• {similar['filename']} (similarity: {similar['similarity_score']:.2%})<br>"
            
        except sqlite3.IntegrityError:
            msg = f"⚠️ File already exists in ledger.<br>Hash: {hash_value[:40]}..."
        
        conn.close()
        
    finally:
        # Nettoyer le fichier temporaire
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return render_template("result.html", message=msg)

@app.route("/verify", methods=["POST"])
def verify():
    file = request.files.get("file")
    if not file:
        return "No file", 400

    hash_value = compute_hash(file)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT filename, signature, public_key, timestamp FROM proofs WHERE hash=?", (hash_value,))
    row = c.fetchone()
    conn.close()

    if row:
        msg = f"✅ Verified! File: {row[0]}<br>Hash: {hash_value[:40]}...<br>Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(row[3]))}"
    else:
        msg = f"❌ Not found in ledger.<br>Hash: {hash_value[:40]}..."

    return render_template("result.html", message=msg)

@app.route("/list")
def list_proofs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, filename, hash, timestamp FROM proofs ORDER BY id DESC")
    proofs = c.fetchall()
    conn.close()
    return render_template("list.html", proofs=proofs)

@app.route("/export/<int:proof_id>")
def export_proof(proof_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT filename, hash, signature, public_key, timestamp FROM proofs WHERE id=?", (proof_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Proof not found", 404

    # Create comprehensive proof data
    proof_data = {
        "prooforigin_protocol": "POP v0.1",
        "proof_id": proof_id,
        "filename": row[0],
        "hash": {
            "algorithm": "SHA-256",
            "value": row[1]
        },
        "signature": {
            "algorithm": "RSA-2048-PSS",
            "value": row[2]
        },
        "public_key": row[3],
        "timestamp": {
            "unix": row[4],
            "readable": datetime.fromtimestamp(row[4]).strftime('%Y-%m-%d %H:%M:%S UTC')
        },
        "verification_url": f"{request.host_url}verify",
        "exported_at": {
            "unix": time.time(),
            "readable": datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
    }

    filename = f"proof_{proof_id}_{row[0]}.proof"
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(proof_data, f, indent=2, ensure_ascii=False)

    return send_file(filename, as_attachment=True, download_name=filename)

# API Endpoints
@app.route("/api/register", methods=["POST"])
def api_register():
    """API endpoint for file registration"""
    file = request.files.get("file")
    if not file:
        return {"error": "No file provided"}, 400

    hash_value = compute_hash(file)
    signature = sign_hash(hash_value)
    timestamp = time.time()

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO proofs (hash, filename, signature, public_key, timestamp) VALUES (?, ?, ?, ?, ?)",
            (hash_value, file.filename, signature, PUBLIC_KEY, timestamp)
        )
        conn.commit()
        proof_id = c.lastrowid
        
        return {
            "success": True,
            "proof_id": proof_id,
            "filename": file.filename,
            "hash": hash_value,
            "signature": signature,
            "timestamp": timestamp,
            "export_url": f"{request.host_url}export/{proof_id}"
        }
    except sqlite3.IntegrityError:
        return {"error": "File already exists in ledger", "hash": hash_value}, 409
    finally:
        conn.close()

@app.route("/api/verify", methods=["POST"])
def api_verify():
    """API endpoint for file verification"""
    file = request.files.get("file")
    if not file:
        return {"error": "No file provided"}, 400

    hash_value = compute_hash(file)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, filename, signature, public_key, timestamp FROM proofs WHERE hash=?", (hash_value,))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "verified": True,
            "proof_id": row[0],
            "filename": row[1],
            "hash": hash_value,
            "signature": row[2],
            "timestamp": row[3],
            "export_url": f"{request.host_url}export/{row[0]}"
        }
    else:
        return {
            "verified": False,
            "hash": hash_value,
            "message": "File not found in ledger"
        }

@app.route("/api/proofs")
def api_list_proofs():
    """API endpoint to list all proofs"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, filename, hash, timestamp, content_type, file_size FROM proofs ORDER BY id DESC")
    proofs = c.fetchall()
    conn.close()

    return {
        "proofs": [
            {
                "id": p[0],
                "filename": p[1],
                "hash": p[2],
                "timestamp": p[3],
                "content_type": p[4],
                "file_size": p[5],
                "export_url": f"{request.host_url}export/{p[0]}"
            }
            for p in proofs
        ],
        "count": len(proofs)
    }

@app.route("/api/similar/<int:proof_id>")
def api_get_similar(proof_id):
    """API endpoint to get similar content for a proof"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        SELECT s.similarity_score, s.match_type, s.confidence, p.filename, p.id
        FROM similarities s
        JOIN proofs p ON s.similar_proof_id = p.id
        WHERE s.proof_id = ?
        ORDER BY s.similarity_score DESC
    """, (proof_id,))
    
    similar_proofs = c.fetchall()
    conn.close()
    
    return {
        "proof_id": proof_id,
        "similar_proofs": [
            {
                "similar_proof_id": p[4],
                "filename": p[3],
                "similarity_score": p[0],
                "match_type": p[1],
                "confidence": p[2]
            }
            for p in similar_proofs
        ],
        "count": len(similar_proofs)
    }

@app.route("/api/anchors")
def api_list_anchors():
    """API endpoint to list blockchain anchors"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT date, merkle_root, proof_count, transaction_hash, timestamp, anchor_signature
        FROM anchors
        ORDER BY timestamp DESC
    """)
    anchors = c.fetchall()
    conn.close()
    
    return {
        "anchors": [
            {
                "date": a[0],
                "merkle_root": a[1],
                "proof_count": a[2],
                "transaction_hash": a[3],
                "timestamp": a[4],
                "anchor_signature": a[5] if len(a) > 5 else None
            }
            for a in anchors
        ],
        "count": len(anchors)
    }

@app.route("/api/verify-anchor/<int:proof_id>")
def api_verify_anchor(proof_id):
    """API endpoint to verify if a proof is anchored on blockchain"""
    from blockchain_anchor import BlockchainAnchor
    
    anchorer = BlockchainAnchor()
    result = anchorer.verify_proof_in_anchor(proof_id, DB_FILE)
    
    return result

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
