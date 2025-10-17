#!/usr/bin/env python3
"""
ProofOrigin - Script de vérification indépendant
Vérifie l'authenticité d'un fichier à partir d'une preuve .proof

Usage:
    python verify_proof.py <fichier_original> <fichier_preuve.proof>

Exemple:
    python verify_proof.py document.pdf proof_1_document.pdf.proof
"""

import sys
import json
import hashlib
import time
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from base64 import b64decode

def compute_file_hash(filepath):
    """Calcule le hash SHA-256 d'un fichier"""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except FileNotFoundError:
        print(f"❌ Erreur: Le fichier '{filepath}' n'existe pas.")
        return None
    except Exception as e:
        print(f"❌ Erreur lors du calcul du hash: {e}")
        return None

def load_proof(proof_path):
    """Charge et valide un fichier de preuve"""
    try:
        with open(proof_path, 'r', encoding='utf-8') as f:
            proof_data = json.load(f)
        
        # Vérifier la structure de base
        required_fields = ['prooforigin_protocol', 'hash', 'signature', 'public_key', 'timestamp']
        for field in required_fields:
            if field not in proof_data:
                print(f"❌ Erreur: Champ manquant dans la preuve: {field}")
                return None
        
        # Vérifier la version du protocole
        if not proof_data['prooforigin_protocol'].startswith('POP'):
            print(f"⚠️  Avertissement: Version de protocole non reconnue: {proof_data['prooforigin_protocol']}")
        
        return proof_data
    except FileNotFoundError:
        print(f"❌ Erreur: Le fichier de preuve '{proof_path}' n'existe pas.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Erreur: Fichier de preuve invalide (JSON): {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur lors du chargement de la preuve: {e}")
        return None

def verify_signature(hash_value, signature_b64, public_key_pem):
    """Vérifie la signature RSA"""
    try:
        # Charger la clé publique
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        
        # Décoder la signature
        signature = b64decode(signature_b64)
        
        # Vérifier la signature
        public_key.verify(
            signature,
            bytes.fromhex(hash_value),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        print(f"❌ Erreur de vérification de signature: {e}")
        return False

def format_timestamp(timestamp):
    """Formate un timestamp Unix en date lisible"""
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        return "Date invalide"

def main():
    if len(sys.argv) != 3:
        print("Usage: python verify_proof.py <fichier_original> <fichier_preuve.proof>")
        print("\nExemple:")
        print("  python verify_proof.py document.pdf proof_1_document.pdf.proof")
        sys.exit(1)
    
    file_path = sys.argv[1]
    proof_path = sys.argv[2]
    
    print("🔐 ProofOrigin - Vérification d'authenticité")
    print("=" * 50)
    
    # 1. Charger la preuve
    print(f"📄 Chargement de la preuve: {proof_path}")
    proof_data = load_proof(proof_path)
    if not proof_data:
        sys.exit(1)
    
    print(f"✅ Preuve chargée (Protocole: {proof_data['prooforigin_protocol']})")
    
    # 2. Calculer le hash du fichier
    print(f"🔍 Calcul du hash du fichier: {file_path}")
    current_hash = compute_file_hash(file_path)
    if not current_hash:
        sys.exit(1)
    
    print(f"✅ Hash calculé: {current_hash[:16]}...{current_hash[-8:]}")
    
    # 3. Vérifier l'intégrité du hash
    stored_hash = proof_data['hash']['value']
    if current_hash != stored_hash:
        print(f"❌ ÉCHEC: Les hashes ne correspondent pas!")
        print(f"   Hash actuel:  {current_hash}")
        print(f"   Hash stocké:  {stored_hash}")
        print("\n💡 Cela signifie que le fichier a été modifié depuis son enregistrement.")
        sys.exit(1)
    
    print("✅ Intégrité du fichier vérifiée (hash identique)")
    
    # 4. Vérifier la signature
    print("🔐 Vérification de la signature cryptographique...")
    signature_valid = verify_signature(
        stored_hash,
        proof_data['signature']['value'],
        proof_data['public_key']
    )
    
    if not signature_valid:
        print("❌ ÉCHEC: La signature cryptographique est invalide!")
        print("💡 Cela peut indiquer une falsification de la preuve.")
        sys.exit(1)
    
    print("✅ Signature cryptographique vérifiée")
    
    # 5. Afficher les résultats
    print("\n" + "=" * 50)
    print("🎉 VÉRIFICATION RÉUSSIE - FICHIER AUTHENTIQUE")
    print("=" * 50)
    
    print(f"📁 Fichier: {proof_data['filename']}")
    print(f"🆔 ID de preuve: {proof_data['proof_id']}")
    print(f"🔒 Algorithme de hash: {proof_data['hash']['algorithm']}")
    print(f"✍️  Algorithme de signature: {proof_data['signature']['algorithm']}")
    print(f"📅 Enregistré le: {format_timestamp(proof_data['timestamp']['unix'])}")
    
    if 'exported_at' in proof_data:
        print(f"📤 Preuve exportée le: {format_timestamp(proof_data['exported_at']['unix'])}")
    
    print(f"\n🔗 URL de vérification: {proof_data.get('verification_url', 'N/A')}")
    
    print("\n✅ Ce fichier est authentique et n'a pas été modifié depuis son enregistrement.")
    print("✅ La preuve d'origine est cryptographiquement valide.")
    
    # 6. Vérifications supplémentaires
    print("\n🔍 Vérifications supplémentaires:")
    
    # Vérifier l'âge de la preuve
    proof_age_days = (time.time() - proof_data['timestamp']['unix']) / (24 * 3600)
    if proof_age_days < 1:
        print(f"   ⏰ Preuve récente (moins d'1 jour)")
    elif proof_age_days < 30:
        print(f"   ⏰ Preuve récente ({proof_age_days:.1f} jours)")
    elif proof_age_days < 365:
        print(f"   ⏰ Preuve ancienne ({proof_age_days:.1f} jours)")
    else:
        print(f"   ⏰ Preuve très ancienne ({proof_age_days:.1f} jours)")
    
    # Vérifier la cohérence des données
    if proof_data['filename'] in file_path:
        print("   📝 Nom de fichier cohérent")
    else:
        print("   ⚠️  Nom de fichier différent (peut être normal)")
    
    print("\n🎯 Résultat final: FICHIER AUTHENTIQUE ✅")

if __name__ == "__main__":
    main()
