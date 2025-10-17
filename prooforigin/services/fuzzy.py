"""Utility classes implementing simplified fuzzy matching for ProofOrigin."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional

class PerceptualHasher:
    """Générateur d'empreintes perceptuelles pour images (version simplifiée)"""
    
    def __init__(self):
        pass
    
    def compute_phash(self, image_path: str) -> Optional[str]:
        """
        Calcule un hash perceptuel simplifié basé sur les métadonnées du fichier
        Version simplifiée sans OpenCV
        """
        try:
            if not os.path.exists(image_path):
                return None
            
            # Utiliser les métadonnées du fichier pour créer un hash perceptuel
            stat = os.stat(image_path)
            file_size = stat.st_size
            modified_time = stat.st_mtime
            
            # Créer un hash basé sur la taille et le nom du fichier
            content = f"{file_size}:{modified_time}:{os.path.basename(image_path)}"
            hash_value = hashlib.sha256(content.encode()).hexdigest()
            
            return hash_value[:16]  # Retourner les 16 premiers caractères
            
        except Exception as e:
            print(f"Erreur lors du calcul du pHash: {e}")
            return None
    
    def compute_dhash(self, image_path: str) -> Optional[str]:
        """
        Calcule un hash de différence simplifié
        Version simplifiée sans OpenCV
        """
        try:
            if not os.path.exists(image_path):
                return None
            
            # Utiliser les premiers et derniers bytes du fichier
            with open(image_path, 'rb') as f:
                first_bytes = f.read(1024)
                f.seek(-1024, 2)  # Aller à la fin
                last_bytes = f.read(1024)
            
            # Créer un hash basé sur la différence
            content = f"{first_bytes.hex()}:{last_bytes.hex()}"
            hash_value = hashlib.sha256(content.encode()).hexdigest()
            
            return hash_value[:16]  # Retourner les 16 premiers caractères
            
        except Exception as e:
            print(f"Erreur lors du calcul du dHash: {e}")
            return None
    
    def hamming_distance(self, hash1: str, hash2: str) -> int:
        """Calcule la distance de Hamming entre deux hashes"""
        if len(hash1) != len(hash2):
            return float('inf')
        
        # Convertir en binaire
        bin1 = bin(int(hash1, 16))[2:].zfill(64)
        bin2 = bin(int(hash2, 16))[2:].zfill(64)
        
        return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))
    
    def similarity_score(self, hash1: str, hash2: str) -> float:
        """
        Calcule un score de similarité entre 0 et 1
        1 = identique, 0 = complètement différent
        """
        distance = self.hamming_distance(hash1, hash2)
        max_distance = 64  # Pour un hash de 64 bits
        return 1 - (distance / max_distance)

class TextSimilarity:
    """Analyseur de similarité pour le contenu textuel (version simplifiée)"""
    
    def __init__(self):
        pass
    
    def compute_semantic_hash(self, text: str) -> Optional[str]:
        """
        Calcule un hash sémantique simplifié du texte
        Version simplifiée sans sentence-transformers
        """
        try:
            # Nettoyer le texte
            cleaned_text = self.clean_text(text)
            
            # Créer un hash basé sur les mots les plus fréquents
            words = cleaned_text.split()
            if not words:
                return None
            
            # Prendre les 10 mots les plus longs (généralement plus significatifs)
            significant_words = sorted(set(words), key=len, reverse=True)[:10]
            content = ' '.join(significant_words)
            
            # Générer le hash
            semantic_hash = hashlib.sha256(content.encode()).hexdigest()
            
            return semantic_hash[:16]  # Retourner les 16 premiers caractères
            
        except Exception as e:
            print(f"Erreur lors du calcul du hash sémantique: {e}")
            return None
    
    def clean_text(self, text: str) -> str:
        """Nettoie le texte pour l'analyse"""
        # Supprimer les caractères spéciaux, normaliser les espaces
        cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def compute_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calcule la similarité simplifiée entre deux textes
        Basée sur la similarité des mots communs
        """
        try:
            # Nettoyer les textes
            clean1 = self.clean_text(text1)
            clean2 = self.clean_text(text2)
            
            # Diviser en mots
            words1 = set(clean1.split())
            words2 = set(clean2.split())
            
            if not words1 or not words2:
                return 0.0
            
            # Calculer la similarité Jaccard
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            similarity = intersection / union if union > 0 else 0.0
            
            return float(similarity)
            
        except Exception as e:
            print(f"Erreur lors du calcul de similarité: {e}")
            return 0.0

class FuzzyMatcher:
    """Matcher principal pour la reconnaissance de contenu similaire."""

    def __init__(self, image_threshold: float = 0.8, text_match_threshold: float = 1.0):
        self.image_hasher = PerceptualHasher()
        self.text_analyzer = TextSimilarity()
        self.image_threshold = image_threshold
        self.text_match_threshold = text_match_threshold
    
    def analyze_file(self, file_path: str, file_type: str = None) -> Dict[str, Any]:
        """
        Analyse un fichier et génère toutes les empreintes possibles
        """
        result = {
            'file_path': os.path.basename(file_path),
            'file_type': file_type,
            'sha256': None,
            'phash': None,
            'dhash': None,
            'semantic_hash': None,
            'content_type': None
        }
        
        try:
            # Hash SHA-256 standard
            with open(file_path, 'rb') as f:
                content = f.read()
                result['sha256'] = hashlib.sha256(content).hexdigest()
            
            # Détecter le type de contenu
            if file_type is None:
                file_type = self.detect_file_type(file_path)
            result['file_type'] = file_type
            
            # Analyse selon le type
            if file_type in ['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                result['phash'] = self.image_hasher.compute_phash(file_path)
                result['dhash'] = self.image_hasher.compute_dhash(file_path)
                result['content_type'] = 'image'
                
            elif file_type in ['txt', 'md', 'json', 'xml', 'html', 'css', 'js', 'py', 'java', 'cpp', 'c']:
                # Pour les fichiers texte
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                        result['semantic_hash'] = self.text_analyzer.compute_semantic_hash(text_content)
                        result['content_type'] = 'text'
                        result['raw_text'] = text_content[:5000]
                except UnicodeDecodeError:
                    result['content_type'] = 'binary'
            
            else:
                result['content_type'] = 'binary'
                
        except Exception as e:
            print(f"Erreur lors de l'analyse du fichier: {e}")
        
        return result
    
    def detect_file_type(self, file_path: str) -> str:
        """Détecte le type de fichier basé sur l'extension"""
        import os
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'svg']
        text_extensions = ['txt', 'md', 'json', 'xml', 'html', 'css', 'js', 'py', 'java', 'cpp', 'c', 'h']
        
        if ext in image_extensions:
            return 'image'
        elif ext in text_extensions:
            return 'text'
        else:
            return ext
    
    def find_similar_content(self, file_analysis: Dict[str, Any], existing_proofs: List[Dict]) -> List[Dict[str, Any]]:
        """
        Trouve du contenu similaire dans les preuves existantes
        """
        similar_proofs = []
        
        for proof in existing_proofs:
            similarity_data = {
                'proof_id': proof.get('id'),
                'filename': proof.get('filename'),
                'similarity_score': 0.0,
                'match_type': None,
                'confidence': 'low'
            }
            
            # Comparaison d'images
            if (file_analysis['content_type'] == 'image' and 
                proof.get('phash') and file_analysis.get('phash')):
                
                phash_similarity = self.image_hasher.similarity_score(
                    file_analysis['phash'], proof['phash']
                )
                
                if phash_similarity >= self.image_threshold:  # Seuil de similarité
                    similarity_data['similarity_score'] = phash_similarity
                    similarity_data['match_type'] = 'perceptual_hash'
                    similarity_data['confidence'] = 'high' if phash_similarity > (self.image_threshold + 0.1) else 'medium'
                    similar_proofs.append(similarity_data)

            # Comparaison de texte
            elif (file_analysis['content_type'] == 'text' and
                  proof.get('semantic_hash') and file_analysis.get('semantic_hash')):

                # Pour l'instant, on compare les hashes sémantiques
                # Dans une version avancée, on pourrait comparer directement les embeddings
                if file_analysis['semantic_hash'] == proof['semantic_hash']:
                    similarity_data['similarity_score'] = 1.0
                    similarity_data['match_type'] = 'semantic_hash'
                    similarity_data['confidence'] = 'high'
                    similar_proofs.append(similarity_data)
                else:
                    similarity = self.text_analyzer.compute_text_similarity(
                        file_analysis.get('raw_text', ''),
                        proof.get('raw_text', '')
                    ) if file_analysis.get('raw_text') and proof.get('raw_text') else 0.0

                    if similarity >= self.text_match_threshold:
                        similarity_data['similarity_score'] = similarity
                        similarity_data['match_type'] = 'text_similarity'
                        similarity_data['confidence'] = 'medium'
                        similar_proofs.append(similarity_data)
        
        # Trier par score de similarité
        similar_proofs.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar_proofs

# Fonction utilitaire pour l'intégration
def analyze_file_for_proof(file_path: str) -> Dict[str, Any]:
    """Fonction simple pour analyser un fichier et générer toutes les empreintes"""
    matcher = FuzzyMatcher()
    return matcher.analyze_file(file_path)

if __name__ == "__main__":
    # Test simple
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        analysis = analyze_file_for_proof(file_path)
        print(json.dumps(analysis, indent=2))
    else:
        print("Usage: python -m prooforigin.services.fuzzy <file_path>")
