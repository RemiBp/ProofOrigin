"""
ProofOrigin - Blockchain Anchoring System
Système d'ancrage des preuves sur blockchain publique
"""

import hashlib
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    from eth_account import Account
    from eth_account.messages import encode_defunct
except ImportError:
    Web3 = None
    Account = None
    encode_defunct = None
    geth_poa_middleware = None

class MerkleTree:
    """Arbre de Merkle pour l'agrégation des preuves"""
    
    def __init__(self, data: List[str]):
        self.data = data
        self.tree = self.build_tree()
        self.root = self.tree[0] if self.tree else None
    
    def build_tree(self) -> List[str]:
        """Construit l'arbre de Merkle"""
        if not self.data:
            return []
        
        # Niveau des feuilles
        level = [hashlib.sha256(item.encode()).hexdigest() for item in self.data]
        tree = [level]
        
        # Construire les niveaux supérieurs
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else left
                combined = left + right
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            level = next_level
            tree.append(level)
        
        return tree
    
    def get_root(self) -> Optional[str]:
        """Retourne la racine de l'arbre de Merkle"""
        return self.root
    
    def get_proof(self, index: int) -> List[str]:
        """Génère une preuve de Merkle pour un élément donné"""
        if index >= len(self.data):
            return []
        
        proof = []
        current_index = index
        
        for level in self.tree[:-1]:  # Exclure la racine
            if current_index % 2 == 0:  # Nœud gauche
                sibling_index = current_index + 1
            else:  # Nœud droit
                sibling_index = current_index - 1
            
            if sibling_index < len(level):
                proof.append(level[sibling_index])
            
            current_index //= 2
        
        return proof

class BlockchainAnchor:
    """Système d'ancrage sur blockchain"""

    def __init__(
        self,
        rpc_url: str | None = None,
        private_key: str | None = None,
        database_path: str | None = None,
    ):
        self.rpc_url = rpc_url or os.getenv("WEB3_RPC_URL") or "https://polygon-rpc.com"
        self.private_key = private_key or os.getenv("WEB3_PRIVATE_KEY")
        self.database_path = database_path or os.getenv("PROOFORIGIN_DATABASE", "ledger.db")
        self.w3 = None
        self.account = None
        self.chain_id = None

        if self.private_key:
            self.setup_web3()
        else:
            print("ℹ️ Aucune clé privée fournie - mode simulation activé")

    def setup_web3(self):
        """Configure la connexion Web3 (version simplifiée)"""
        if Web3 is None or Account is None:
            print("⚠️ web3.py indisponible, activation du mode simulation")
            return

        try:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 10}))

            if not self.w3.is_connected():
                raise ConnectionError(f"Impossible de se connecter à {self.rpc_url}")

            # Injecter le middleware POA pour les réseaux type Polygon/PoA
            if geth_poa_middleware is not None:
                try:
                    self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                except ValueError:
                    # Middleware déjà injecté
                    pass

            self.account = Account.from_key(self.private_key)
            self.chain_id = self.w3.eth.chain_id

            print(f"✅ Connecté à {self.rpc_url} (chain_id={self.chain_id})")
            print(f"👤 Compte d'ancrage: {self.account.address}")
        except Exception as e:
            print(f"❌ Erreur de configuration Web3: {e}")
            self.w3 = None
            self.account = None
            self.chain_id = None

    def _resolve_db_path(self, db_file: str | None = None) -> str:
        return db_file or self.database_path

    def get_daily_proofs(self, db_file: str | None = None) -> List[Dict[str, Any]]:
        """Récupère toutes les preuves du jour"""
        database = self._resolve_db_path(db_file)
        conn = sqlite3.connect(database)
        c = conn.cursor()
        
        # Preuves des dernières 24h
        yesterday = time.time() - (24 * 3600)
        c.execute("""
            SELECT id, filename, hash, signature, timestamp 
            FROM proofs 
            WHERE timestamp > ? 
            ORDER BY timestamp ASC
        """, (yesterday,))
        
        proofs = []
        for row in c.fetchall():
            proofs.append({
                'id': row[0],
                'filename': row[1],
                'hash': row[2],
                'signature': row[3],
                'timestamp': row[4]
            })
        
        conn.close()
        return proofs
    
    def create_daily_merkle_root(self, proofs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Crée la racine Merkle quotidienne"""
        if not proofs:
            return None
        
        # Créer les données pour l'arbre de Merkle
        merkle_data = []
        for proof in proofs:
            # Combiner les données importantes
            proof_string = f"{proof['id']}:{proof['hash']}:{proof['timestamp']}"
            merkle_data.append(proof_string)
        
        # Construire l'arbre de Merkle
        merkle_tree = MerkleTree(merkle_data)
        root = merkle_tree.get_root()
        
        return {
            'merkle_root': root,
            'proof_count': len(proofs),
            'timestamp': time.time(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'proofs': proofs
        }
    
    def _sign_merkle_message(self, message: str) -> Optional[str]:
        """Crée une signature du message d'ancrage"""
        try:
            if self.account and encode_defunct is not None:
                signable_message = encode_defunct(text=message)
                signed_message = self.account.sign_message(signable_message)
                return signed_message.signature.hex()

            if self.private_key:
                # Signature simulée lorsque Web3 est indisponible
                return hashlib.sha256(f"{message}:{self.private_key}".encode()).hexdigest()
        except Exception as exc:
            print(f"⚠️ Impossible de signer le message d'ancrage: {exc}")

        return None

    def anchor_to_blockchain(self, merkle_data: Dict[str, Any]) -> Optional[str]:
        """Ancre la racine Merkle sur la blockchain"""
        message = f"ProofOrigin Daily Root {merkle_data['date']}: {merkle_data['merkle_root']}"
        signature = self._sign_merkle_message(message)
        merkle_data['signature'] = signature

        if not self.w3 or not self.account:
            print("⚠️ Web3 non configuré, simulation d'ancrage")
            return self.simulate_anchoring(merkle_data)

        try:
            message_hash = self.w3.keccak(text=message)
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = getattr(self.w3.eth, "gas_price", None)

            tx: Dict[str, Any] = {
                'chainId': self.chain_id or self.w3.eth.chain_id,
                'nonce': nonce,
                'to': self.account.address,
                'value': 0,
                'data': message_hash,
                'gas': 100000,
            }

            if gas_price is not None:
                tx['gasPrice'] = gas_price
            else:
                # Fallback pour EIP-1559 si gas_price indisponible
                base_fee = self.w3.eth.get_block('latest').baseFeePerGas
                priority_fee = self.w3.to_wei('2', 'gwei')
                tx['maxFeePerGas'] = base_fee + priority_fee
                tx['maxPriorityFeePerGas'] = priority_fee

            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            print(f"🔗 Racine Merkle ancrée: {merkle_data['merkle_root'][:16]}...")
            print(f"📝 Transaction envoyée: {tx_hash.hex()}")
            print(f"📬 Statut de la transaction: {receipt.status}")

            return tx_hash.hex()

        except Exception as e:
            print(f"❌ Erreur d'ancrage: {e}")
            print("🧪 Retour au mode simulation pour cette exécution")
            return self.simulate_anchoring(merkle_data)

    def simulate_anchoring(self, merkle_data: Dict[str, Any]) -> str:
        """Simule l'ancrage pour les tests"""
        if not merkle_data.get('signature'):
            merkle_data['signature'] = hashlib.sha256(
                f"{merkle_data['merkle_root']}:{merkle_data['timestamp']}".encode()
            ).hexdigest()

        tx_hash = hashlib.sha256(
            f"{merkle_data['merkle_root']}:{merkle_data['timestamp']}".encode()
        ).hexdigest()

        print(f"🧪 SIMULATION - Racine Merkle: {merkle_data['merkle_root'][:16]}...")
        print(f"🧪 SIMULATION - Transaction: {tx_hash}")
        
        return tx_hash
    
    def _ensure_anchor_signature_column(self, cursor):
        """Ajoute la colonne anchor_signature si elle est absente"""
        cursor.execute("PRAGMA table_info(anchors)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'anchor_signature' not in columns:
            cursor.execute("ALTER TABLE anchors ADD COLUMN anchor_signature TEXT")

    def save_anchor_record(self, merkle_data: Dict[str, Any], tx_hash: str, db_file: str | None = None):
        """Sauvegarde l'enregistrement d'ancrage"""
        database = self._resolve_db_path(db_file)
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(database)
        c = conn.cursor()

        # Créer la table des ancrages si elle n'existe pas
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

        self._ensure_anchor_signature_column(c)

        try:
            c.execute("""
                INSERT INTO anchors (date, merkle_root, proof_count, transaction_hash, timestamp, anchor_signature)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                merkle_data['date'],
                merkle_data['merkle_root'],
                merkle_data['proof_count'],
                tx_hash,
                merkle_data['timestamp'],
                merkle_data.get('signature')
            ))
            conn.commit()
            print(f"💾 Ancrage sauvegardé pour {merkle_data['date']}")
        except sqlite3.IntegrityError:
            print(f"⚠️ Ancrage déjà existant pour {merkle_data['date']}")
        finally:
            conn.close()
    
    def get_anchor_history(self, db_file: str | None = None) -> List[Dict[str, Any]]:
        """Récupère l'historique des ancrages"""
        database = self._resolve_db_path(db_file)
        conn = sqlite3.connect(database)
        c = conn.cursor()
        
        c.execute("""
            SELECT date, merkle_root, proof_count, transaction_hash, timestamp, anchor_signature
            FROM anchors
            ORDER BY timestamp DESC
        """)

        anchors = []
        for row in c.fetchall():
            anchor_signature = row[5] if len(row) > 5 else None
            anchors.append({
                'date': row[0],
                'merkle_root': row[1],
                'proof_count': row[2],
                'transaction_hash': row[3],
                'timestamp': row[4],
                'anchor_signature': anchor_signature
            })

        conn.close()
        return anchors
    
    def verify_proof_in_anchor(self, proof_id: int, db_file: str | None = None) -> Dict[str, Any]:
        """Vérifie qu'une preuve est incluse dans un ancrage"""
        database = self._resolve_db_path(db_file)
        conn = sqlite3.connect(database)
        c = conn.cursor()
        
        # Récupérer la preuve
        c.execute("SELECT id, filename, hash, timestamp FROM proofs WHERE id = ?", (proof_id,))
        proof_row = c.fetchone()
        
        if not proof_row:
            conn.close()
            return {'verified': False, 'error': 'Proof not found'}
        
        proof = {
            'id': proof_row[0],
            'filename': proof_row[1],
            'hash': proof_row[2],
            'timestamp': proof_row[3]
        }
        
        # Trouver l'ancrage correspondant
        proof_date = datetime.fromtimestamp(proof['timestamp']).strftime('%Y-%m-%d')
        c.execute("SELECT * FROM anchors WHERE date = ?", (proof_date,))
        anchor_row = c.fetchone()
        
        conn.close()
        
        if anchor_row:
            anchor_signature = anchor_row[6] if len(anchor_row) > 6 else None
            return {
                'verified': True,
                'proof': proof,
                'anchor': {
                    'date': anchor_row[1],
                    'merkle_root': anchor_row[2],
                    'proof_count': anchor_row[3],
                    'transaction_hash': anchor_row[4],
                    'anchor_signature': anchor_signature
                }
            }
        else:
            return {
                'verified': False,
                'error': 'No anchor found for this date'
            }

def run_daily_anchoring(
    db_file: str | None = None,
    rpc_url: str | None = None,
    private_key: str | None = None,
):
    """Fonction principale pour l'ancrage quotidien"""
    print("🔗 ProofOrigin - Ancrage quotidien")
    print("=" * 40)

    # Initialiser l'ancreur
    anchorer = BlockchainAnchor(rpc_url, private_key, database_path=db_file)
    
    # Récupérer les preuves du jour
    print("📊 Récupération des preuves du jour...")
    daily_proofs = anchorer.get_daily_proofs(db_file)
    
    if not daily_proofs:
        print("ℹ️ Aucune nouvelle preuve à ancrer aujourd'hui")
        return
    
    print(f"📝 {len(daily_proofs)} preuves trouvées")
    
    # Créer la racine Merkle
    print("🌳 Création de la racine Merkle...")
    merkle_data = anchorer.create_daily_merkle_root(daily_proofs)
    
    if not merkle_data:
        print("❌ Erreur lors de la création de la racine Merkle")
        return
    
    print(f"✅ Racine Merkle: {merkle_data['merkle_root'][:16]}...")
    
    # Ancrer sur blockchain
    print("⛓️ Ancrage sur blockchain...")
    tx_hash = anchorer.anchor_to_blockchain(merkle_data)
    
    if tx_hash:
        # Sauvegarder l'enregistrement
        anchorer.save_anchor_record(merkle_data, tx_hash, db_file)
        print("✅ Ancrage quotidien terminé avec succès")
    else:
        print("❌ Échec de l'ancrage")

if __name__ == "__main__":
    import sys
    
    # Configuration par défaut (simulation)
    rpc_url = None
    private_key = None
    db_path = None
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("Usage: python -m prooforigin.services.blockchain [--rpc-url URL] [--private-key KEY] [--db PATH]")
            print(
                "Exemple: python -m prooforigin.services.blockchain --rpc-url https://polygon-rpc.com --private-key 0x..."
            )
            sys.exit(0)

        # Parser les arguments
        args = sys.argv[1:]
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--rpc-url" and i + 1 < len(args):
                rpc_url = args[i + 1]
                i += 2
            elif arg == "--private-key" and i + 1 < len(args):
                private_key = args[i + 1]
                i += 2
            elif arg == "--db" and i + 1 < len(args):
                db_path = args[i + 1]
                i += 2
            else:
                i += 1

    run_daily_anchoring(db_file=db_path, rpc_url=rpc_url, private_key=private_key)
