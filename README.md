# ProofOrigin - Trust Layer for AI Content

> **L'infrastructure ouverte pour prouver, vérifier et tracer l'origine des contenus numériques et IA.**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1+-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Vision

Dans un monde où 90% du contenu sera bientôt généré par l'IA, ProofOrigin veut devenir la norme ouverte permettant à tout utilisateur, IA, média ou entreprise de dire :

> **"Voici la preuve que ce contenu vient bien de telle source, à telle date, sans manipulation."**

## ✨ Fonctionnalités

### 🔐 Authentification cryptographique
- **Hash SHA-256** : Empreinte unique et infalsifiable de chaque fichier
- **Signature RSA-2048** : Preuve d'authenticité cryptographiquement robuste
- **Horodatage précis** : Enregistrement permanent de la date d'origine

### 📊 Registre infalsifiable
- **Base de données append-only** : Aucune modification possible des preuves existantes
- **Interface web moderne** : Interface utilisateur intuitive et responsive
- **Export de preuves** : Format `.proof` portable et vérifiable

### 🔍 Vérification indépendante
- **Script de vérification** : Validation hors ligne des preuves
- **API REST** : Intégration facile dans d'autres systèmes
- **Protocole ouvert** : Standard ProofOrigin Protocol (POP v0.1)

## 🚀 Installation rapide

### Prérequis
- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)

### Installation
```bash
# Cloner le projet
git clone https://github.com/votre-username/prooforigin.git
cd prooforigin

# Créer un environnement virtuel
python -m venv venv

# Activer l'environnement virtuel
# Sur Windows:
venv\Scripts\activate
# Sur macOS/Linux:
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Générer les clés cryptographiques
python scripts/generate_keys.py

# Initialiser la base SQLite (optionnel, fait automatiquement au démarrage)
python - <<'PY'
from prooforigin.config import ProofOriginConfig
from prooforigin.database import init_db
cfg = ProofOriginConfig()
init_db(cfg.database)
print(f"Base initialisée: {cfg.database}")
PY

# Lancer l'application Flask
python -m prooforigin
```

L'application est disponible sur `http://localhost:5000` et charge automatiquement les templates depuis le package `prooforigin/`.

## 📖 Guide d'utilisation

### Interface Web

1. **Enregistrer un fichier** : Uploadez un fichier pour créer une preuve d'authenticité
2. **Vérifier un fichier** : Vérifiez l'authenticité d'un fichier dans le registre
3. **Consulter le registre** : Visualisez toutes les preuves enregistrées
4. **Exporter une preuve** : Téléchargez une preuve au format `.proof`

### API REST

#### Enregistrer un fichier
```bash
curl -X POST -F "file=@document.pdf" http://localhost:5000/api/register
```

#### Vérifier un fichier
```bash
curl -X POST -F "file=@document.pdf" http://localhost:5000/api/verify
```

#### Lister toutes les preuves
```bash
curl http://localhost:5000/api/proofs
```

#### Récupérer une preuve par ID
```bash
curl http://localhost:5000/api/proofs/1
```

### ⛓️ Ancrage blockchain

Le module `prooforigin.services.blockchain` agrège les preuves des dernières 24 heures, calcule une racine de Merkle et l'ancre sur une blockchain compatible EVM.

- **Mode connecté** : fournissez l'URL RPC et la clé privée via les variables d'environnement `WEB3_RPC_URL` et `WEB3_PRIVATE_KEY`, ou via les options `--rpc-url` et `--private-key` pour signer et émettre une transaction réelle (EIP-1559). La signature du message et le hash de transaction sont enregistrés dans la table `anchors`.
- **Mode simulation** : si les dépendances Web3 ne sont pas disponibles ou qu'aucune clé privée n'est fournie, le script reste fonctionnel en générant une transaction simulée tout en stockant la racine Merkle et une signature dérivée.

Exemple d'exécution quotidienne :

```bash
WEB3_RPC_URL="https://polygon-rpc.com" \
WEB3_PRIVATE_KEY="0x..." \
python -m prooforigin.services.blockchain --db instance/ledger.db
```

L'ancrage peut être planifié via cron (`run_daily_anchoring`) et piloté à la demande grâce à l'endpoint `/api/anchors/run` en POST. L'historique des ancrages reste disponible via `/api/anchors`.

### Vérification hors ligne

```bash
# Vérifier un fichier avec sa preuve
python scripts/verify_proof.py document.pdf proof_1_document.pdf.proof
```

## 🔧 Architecture technique

### Stack technologique
- **Backend** : Flask (Python)
- **Base de données** : SQLite
- **Cryptographie** : cryptography (RSA-2048, SHA-256)
- **Frontend** : HTML5, CSS3, JavaScript (vanilla)
- **API** : REST JSON

### 📁 Structure du projet

```
prooforigin/
├── prooforigin/               # Package principal (config, routes, services, templates)
│   ├── services/              # Modules métiers (blockchain, fuzzy matching)
│   ├── templates/             # Pages HTML (interface web)
│   ├── app.py                 # Factory Flask
│   └── ...
├── scripts/                   # Utilitaires CLI (génération de clés, vérification)
├── sdks/                      # SDK clients (Python & JavaScript)
├── keys/                      # Paires de clés RSA (générées côté déploiement)
├── instance/                  # Données runtime (base SQLite, exports temporaires)
├── Procfile                   # Lancement Heroku/Render (`python -m prooforigin`)
├── deploy.py                  # Script de déploiement automatisé
└── README.md
```

Toutes les routes, services et filtres Jinja2 sont désormais regroupés dans le package Python, ce qui facilite les tests automatisés et le déploiement.

### Structure des données

#### Format de preuve (.proof)
```json
{
  "prooforigin_protocol": "POP v0.1",
  "proof_id": 1,
  "filename": "document.pdf",
  "hash": {
    "algorithm": "SHA-256",
    "value": "a1b2c3d4e5f6..."
  },
  "signature": {
    "algorithm": "RSA-2048-PSS",
    "value": "base64_encoded_signature"
  },
  "public_key": "-----BEGIN PUBLIC KEY-----...",
  "timestamp": {
    "unix": 1703123456,
    "readable": "2023-12-21 10:30:56 UTC"
  },
  "verification_url": "https://prooforigin.example.com/verify",
  "exported_at": {
    "unix": 1703123500,
    "readable": "2023-12-21 10:31:40 UTC"
  }
}
```

### Sécurité

- **Clés RSA-2048** : Niveau de sécurité bancaire
- **Padding PSS** : Protection contre les attaques par timing
- **Hash SHA-256** : Standard cryptographique robuste
- **Base append-only** : Impossibilité de modifier les preuves existantes

## 🌐 Déploiement

### Déploiement local
```bash
python -m prooforigin
```

### Déploiement en production

#### Avec Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

#### Avec Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

#### Plateformes recommandées
- **Render** : Déploiement gratuit et simple
- **Railway** : Intégration Git automatique
- **Fly.io** : Performance globale
- **Heroku** : Écosystème mature

## 🔌 Intégration

### SDK Python (à venir)
```python
from prooforigin import ProofOrigin

client = ProofOrigin("https://api.prooforigin.com")
proof = client.register_file("document.pdf")
verification = client.verify_file("document.pdf")
```

### SDK JavaScript (à venir)
```javascript
import { ProofOrigin } from 'prooforigin-js';

const client = new ProofOrigin('https://api.prooforigin.com');
const proof = await client.registerFile('document.pdf');
const verification = await client.verifyFile('document.pdf');
```

## 📊 Cas d'usage

### Pour les créateurs de contenu
- **Protection de la propriété intellectuelle** : Preuve d'antériorité
- **Traçabilité des créations** : Historique complet des œuvres
- **Certification d'authenticité** : Validation par des tiers

### Pour les plateformes IA
- **Transparence des générations** : Marquer le contenu IA
- **Compliance réglementaire** : Respect des nouvelles lois
- **Confiance utilisateur** : Authentification des sources

### Pour les médias
- **Vérification des sources** : Authentification des documents
- **Lutte contre la désinformation** : Preuve d'intégrité
- **Archivage sécurisé** : Conservation des preuves

### Pour les entreprises
- **Audit trail** : Traçabilité des documents
- **Conformité RGPD** : Preuve de non-modification
- **Sécurité documentaire** : Protection contre la falsification

## 🛣️ Roadmap

### Phase 2 - Ledger visuel et export (✅ Terminé)
- [x] Interface web moderne et responsive
- [x] Page de liste des preuves
- [x] Export de preuves au format `.proof`
- [x] Script de vérification indépendant

### Phase 3 - Hébergement public & API (🔄 En cours)
- [ ] Déploiement sur infrastructure cloud
- [ ] Documentation API complète
- [ ] Page d'accueil publique
- [ ] HTTPS et sécurité renforcée

### Phase 4 - Standardisation (📋 Planifié)
- [ ] SDK Python officiel
- [ ] SDK JavaScript/Node.js
- [ ] Spécification POP v1.0
- [ ] Intégrations tierces

### Phase 5 - Écosystème (🔮 Futur)
- [ ] Blockchain integration
- [ ] Smart contracts
- [ ] Marketplace de vérification
- [ ] Certification tiers

## 🤝 Contribution

Les contributions sont les bienvenues ! Voici comment contribuer :

1. **Fork** le projet
2. **Créer** une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. **Commit** vos changements (`git commit -m 'Add some AmazingFeature'`)
4. **Push** vers la branche (`git push origin feature/AmazingFeature`)
5. **Ouvrir** une Pull Request

### Guidelines de contribution
- Code propre et commenté
- Tests unitaires pour les nouvelles fonctionnalités
- Documentation mise à jour
- Respect des standards de sécurité

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- **Cryptography** : Bibliothèque Python pour la cryptographie
- **Flask** : Framework web léger et puissant
- **SQLite** : Base de données embarquée fiable
- **Communauté open source** : Pour l'inspiration et les contributions

## 📞 Contact

- **Site web** : [prooforigin.com](https://prooforigin.com) (à venir)
- **Email** : contact@prooforigin.com
- **Twitter** : [@ProofOrigin](https://twitter.com/ProofOrigin)
- **GitHub** : [github.com/prooforigin](https://github.com/prooforigin)

---

**ProofOrigin** - *Building trust in the age of AI* 🤖✨
