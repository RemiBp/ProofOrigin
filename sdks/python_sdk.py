"""
ProofOrigin SDK - Python
SDK officiel pour l'intégration avec l'API ProofOrigin
"""

import requests
import json
import hashlib
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import os

class ProofOriginClient:
    """Client Python pour l'API ProofOrigin"""
    
    def __init__(self, api_url: str = "https://api.prooforigin.com", api_key: str = None):
        """
        Initialise le client ProofOrigin
        
        Args:
            api_url: URL de l'API ProofOrigin
            api_key: Clé API (optionnelle pour l'usage basique)
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})
    
    def register_file(self, file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enregistre un fichier et crée une preuve d'authenticité
        
        Args:
            file_path: Chemin vers le fichier à enregistrer
            metadata: Métadonnées optionnelles
            
        Returns:
            Dict contenant les informations de la preuve créée
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                
                data = {}
                if metadata:
                    data['metadata'] = json.dumps(metadata)
                
                response = self.session.post(
                    f"{self.api_url}/api/register",
                    files=files,
                    data=data
                )
                
                response.raise_for_status()
                return response.json()
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur lors de l'enregistrement: {e}")
    
    def verify_file(self, file_path: str) -> Dict[str, Any]:
        """
        Vérifie l'authenticité d'un fichier
        
        Args:
            file_path: Chemin vers le fichier à vérifier
            
        Returns:
            Dict contenant les résultats de la vérification
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                
                response = self.session.post(
                    f"{self.api_url}/api/verify",
                    files=files
                )
                
                response.raise_for_status()
                return response.json()
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur lors de la vérification: {e}")
    
    def get_proof(self, proof_id: int) -> Dict[str, Any]:
        """
        Récupère les détails d'une preuve
        
        Args:
            proof_id: ID de la preuve
            
        Returns:
            Dict contenant les détails de la preuve
        """
        try:
            response = self.session.get(f"{self.api_url}/api/proofs/{proof_id}")
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur lors de la récupération: {e}")
    
    def list_proofs(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Liste les preuves disponibles
        
        Args:
            limit: Nombre maximum de preuves à retourner
            offset: Décalage pour la pagination
            
        Returns:
            Dict contenant la liste des preuves
        """
        try:
            params = {'limit': limit, 'offset': offset}
            response = self.session.get(f"{self.api_url}/api/proofs", params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur lors de la récupération: {e}")
    
    def export_proof(self, proof_id: int, output_path: str = None) -> str:
        """
        Exporte une preuve au format .proof
        
        Args:
            proof_id: ID de la preuve à exporter
            output_path: Chemin de sortie (optionnel)
            
        Returns:
            Chemin vers le fichier .proof créé
        """
        try:
            response = self.session.get(f"{self.api_url}/export/{proof_id}")
            response.raise_for_status()
            
            if not output_path:
                # Générer un nom de fichier automatique
                content_disposition = response.headers.get('content-disposition', '')
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('"')
                else:
                    filename = f"proof_{proof_id}.proof"
                output_path = filename
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return output_path
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erreur lors de l'export: {e}")
    
    def verify_proof_file(self, file_path: str, proof_path: str) -> Dict[str, Any]:
        """
        Vérifie un fichier avec sa preuve .proof
        
        Args:
            file_path: Chemin vers le fichier original
            proof_path: Chemin vers le fichier .proof
            
        Returns:
            Dict contenant les résultats de la vérification
        """
        try:
            # Charger la preuve
            with open(proof_path, 'r', encoding='utf-8') as f:
                proof_data = json.load(f)
            
            # Calculer le hash du fichier
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Vérifier l'intégrité
            stored_hash = proof_data['hash']['value']
            integrity_ok = file_hash == stored_hash
            
            return {
                'verified': integrity_ok,
                'file_hash': file_hash,
                'stored_hash': stored_hash,
                'proof_data': proof_data,
                'timestamp': proof_data.get('timestamp', {}).get('readable', 'Unknown')
            }
            
        except Exception as e:
            raise Exception(f"Erreur lors de la vérification: {e}")

# Fonctions utilitaires pour une utilisation simple
def register_file(file_path: str, api_url: str = "https://api.prooforigin.com") -> Dict[str, Any]:
    """
    Fonction simple pour enregistrer un fichier
    
    Args:
        file_path: Chemin vers le fichier
        api_url: URL de l'API
        
    Returns:
        Dict contenant les informations de la preuve
    """
    client = ProofOriginClient(api_url)
    return client.register_file(file_path)

def verify_file(file_path: str, api_url: str = "https://api.prooforigin.com") -> Dict[str, Any]:
    """
    Fonction simple pour vérifier un fichier
    
    Args:
        file_path: Chemin vers le fichier
        api_url: URL de l'API
        
    Returns:
        Dict contenant les résultats de la vérification
    """
    client = ProofOriginClient(api_url)
    return client.verify_file(file_path)

# Exemple d'utilisation
if __name__ == "__main__":
    # Exemple d'utilisation du SDK
    client = ProofOriginClient("http://localhost:5000")  # Pour les tests locaux
    
    try:
        # Enregistrer un fichier
        print("📝 Enregistrement d'un fichier...")
        result = client.register_file("example.txt")
        print(f"✅ Preuve créée: {result}")
        
        # Vérifier le fichier
        print("\n🔍 Vérification du fichier...")
        verification = client.verify_file("example.txt")
        print(f"✅ Vérification: {verification}")
        
        # Lister les preuves
        print("\n📋 Liste des preuves...")
        proofs = client.list_proofs()
        print(f"✅ {proofs['count']} preuves trouvées")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
