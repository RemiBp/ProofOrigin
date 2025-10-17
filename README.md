# ProofOrigin – Trust Layer for AI & Creative Assets

ProofOrigin fournit une chaîne complète pour prouver l'origine de contenus numériques : authentification cryptographique, registres append-only, recherche de similarités et intégrations facturation/monitoring. Le backend repose désormais sur **FastAPI + SQLAlchemy**, avec une génération de clés **Ed25519** chiffrées (AES-256 + Argon2id + master key serveur) et une interface web légère prête pour les tests utilisateurs.

## ✨ Fonctionnalités clés

| Domaine | Capacités |
| --- | --- |
| 🔐 **Sécurité & identité** | Enregistrement utilisateur avec Argon2id, génération de paires Ed25519 chiffrées, rotation de clé, JWT court + refresh token, artefacts `.proof` exportables. |
| 📄 **Gestion de preuves** | Endpoint multipart `generate_proof`, signature Ed25519, stockage hash SHA-256, génération automatique d'artefacts, journalisation d'usage et décrément des crédits. |
| 🔍 **Similarité & indexation** | pHash/dHash basés sur `imagehash`, embeddings SBERT (`sentence-transformers`) pour le texte, moteur hybride (cosine + Hamming), API `search-similar` et stockage des matches. |
| 💳 **Facturation** | Intégration Stripe (ou simulation si clé absente), suivi des crédits, endpoint `usage` pour la consommation, modèle de crédits extensible. |
| ⛓️ **Ancrage blockchain** | Service `schedule_anchor` qui signe les preuves (simulation ou envoi Web3) et renseigne transaction + horodatage. |
| 🛠️ **Ops & monitoring** | Endpoint `/healthz`, journalisation JSON (`structlog`), scripts CLI, export `.proof`, tableau de bord web minimaliste (inscription → génération → vérification). |

## 🚀 Démarrage rapide

### Prérequis
- Python 3.10+
- `pip`
- (Optionnel) accès à un nœud Web3 et compte Stripe

### Installation locale
```bash
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate sous Windows
pip install --upgrade pip
pip install -r requirements.txt

# Lancer le backend FastAPI + initialisation DB
python app.py  # ou uvicorn prooforigin.app:app --reload
```
Le serveur écoute sur `http://localhost:8000`. L'API interactive est disponible via Swagger (`/docs`) et Redoc (`/redoc`).

### Variables d'environnement principales
| Variable | Rôle |
| --- | --- |
| `PROOFORIGIN_DATABASE` | URL SQLAlchemy (SQLite par défaut dans `instance/ledger.db`). |
| `PROOFORIGIN_PRIVATE_KEY_MASTER_KEY` | Master key 32 bytes utilisée pour chiffrer les clés privées (obligatoire en prod). |
| `PROOFORIGIN_ACCESS_TOKEN_EXPIRE_MINUTES` | Durée de vie des tokens d'accès. |
| `PROOFORIGIN_STRIPE_API_KEY` / `PROOFORIGIN_STRIPE_PRICE_ID` | Active le mode facturation Stripe. |
| `WEB3_RPC_URL` / `WEB3_PRIVATE_KEY` / `PROOFORIGIN_BLOCKCHAIN_ENABLED` | Active l'ancrage réel sur une blockchain compatible EVM. |
| `PROOFORIGIN_SENTENCE_TRANSFORMER_MODEL` | Modèle SBERT à charger (par défaut `all-MiniLM-L6-v2`). |

> ⚠️ En production, configurez absolument `PROOFORIGIN_PRIVATE_KEY_MASTER_KEY`, un SGBD externe (PostgreSQL) et un gestionnaire de secrets (Vault, AWS KMS...).

## 🧭 Parcours utilisateur

1. **Inscription** – `POST /api/v1/register` → génération de la paire Ed25519 chiffrée + crédit initial.
2. **Connexion** – `POST /api/v1/login` (OAuth2 password) → réception `access_token` + `refresh_token`.
3. **Génération de preuve** – `POST /api/v1/generate_proof` (multipart `file`, `metadata`, `key_password`). Retour JSON + artefact `.proof` stocké côté serveur.
4. **Vérification** – `POST /api/v1/verify_proof` (JSON) ou `/api/v1/verify_proof/file` (multipart) → statut signature + ancrage.
5. **Listing & détails** – `GET /api/v1/user/proofs` (pagination) & `GET /api/v1/proofs/{id}`.
6. **Similarité** – `POST /api/v1/search-similar` (texte ou fichier) → top matches & métriques.
7. **Quotas & facturation** – `GET /api/v1/usage`, `POST /api/v1/buy-credits` (Stripe ou mode démo).
8. **Alertes & rapports** – `POST /api/v1/report`, `POST /api/v1/batch-verify` (jobs asynchrones + webhook).

Toutes les routes nécessitent HTTPS + `Authorization: Bearer` sauf inscription/connexion/vérification publique.

## 🧾 Artefact `.proof`
Le fichier JSON exporté (et enregistré à côté du fichier original) suit le schéma :
```json
{
  "prooforigin_protocol": "POP-1.0",
  "proof_id": "UUID",
  "hash": {"algorithm": "SHA-256", "value": "..."},
  "signature": {"algorithm": "Ed25519", "value": "base64"},
  "public_key": {
    "public_key_pem": "-----BEGIN PUBLIC KEY...",
    "public_key_raw": "base64"
  },
  "timestamp": "2024-05-07T12:34:56.789Z",
  "metadata": {...}
}
```
Le script `scripts/verify_proof.py` permet une validation hors ligne complète (hash + signature Ed25519).

## 🧠 Similarité & Indexation
- **Images** : pHash/dHash via `imagehash` + vecteur binaire (utilisé pour la similarité Hamming).
- **Texte** : embeddings SBERT (`sentence-transformers`) et similarité cosinus.
- **Pipeline** : lors de la génération d'une preuve, le moteur `SimilarityEngine` calcule les empreintes et alimente la table `similarity_matches`. L'API `search-similar` permet des requêtes ad-hoc.
- **Vector DB** : la structure SQL (table `proofs` avec colonnes `image_embedding`/`text_embedding`) est prête pour l'intégration FAISS/Milvus ultérieure.

## 🔐 Gestion des clés
- **Génération** : Ed25519 (libs `cryptography`).
- **Chiffrement** : AES-256-GCM avec clé dérivée Argon2id (paramètres configurables) + master key serveur.
- **Rotation** : endpoint `POST /api/v1/upload-key` (nécessite authentification + mot de passe).
- **JWT** : signé HS256 avec TTL court (configurable) + refresh token 14 jours.

## 💳 Facturation & quotas
- Chaque utilisateur dispose d'un compteur de crédits (`users.credits`).
- Le `generate_proof` décrémente 1 crédit et journalise l'action (`usage_logs`).
- `POST /api/v1/buy-credits` : crée une session Stripe (si clé configurée) ou crédite automatiquement en mode démo.
- `GET /api/v1/usage` : expose preuves générées, vérifications et dernier paiement.

## ⛓️ Blockchain
- `schedule_anchor(proof_id)` (tâche de fond) signe la preuve et tente une transaction Web3.
- Si Web3 indisponible, un hash simulé est stocké (`simulated://...`).
- Les colonnes `blockchain_tx`, `anchor_signature`, `anchored_at` sont alimentées et visibles via l'API.

## 🖥️ UI & UX
- Accueil (`/`) : inscription, connexion, génération de preuves et vérification rapide (JS vanilla + fetch).
- Tableau de bord (`/dashboard`) : tableau des 25 dernières preuves (requires token stocké en localStorage).
- Les appels front consomment l'API officielle, garantissant la parité web/mobile.

## 🧰 Scripts & outils
- `scripts/verify_proof.py` : vérification hors ligne d'un fichier + artefact `.proof` (Ed25519).
- `scripts/generate_keys.py` : (à adapter) génération de master key ou clés serveur.
- `deploy.py` : automatisation déploiement (à mettre à jour selon l'infra cible).

## 🗂️ Structure du projet
```
ProofOrigin/
├── app.py                         # Entrée uvicorn
├── prooforigin/
│   ├── api/                       # FastAPI, routers, schémas
│   │   ├── main.py
│   │   ├── schemas.py
│   │   └── routers/{auth,billing,proofs}.py
│   ├── core/                      # Config, ORM, sécurité, logging
│   │   ├── settings.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── security.py
│   ├── services/                  # Blockchain, similarité, etc.
│   ├── templates/                 # Interface web (Jinja2)
│   └── web/router.py              # Routes web
├── scripts/                       # CLI et outils
├── sdks/                          # SDKs clients (inchangés)
├── instance/                      # DB, artefacts, stockages
└── requirements.txt
```

## ✅ Tests rapides
```bash
# Sanity check : compilation et typage de base
python -m py_compile $(git ls-files '*.py')

# Lancer l'app en mode développement
uvicorn prooforigin.app:app --reload
```

## 🔒 Bonnes pratiques avant prod
- Utiliser PostgreSQL + migrations (Alembic) au lieu de SQLite.
- Brancher un service KMS/Vault pour la master key.
- Activer un vrai moteur ANN (FAISS/Milvus) et une file de tâches (Celery/RQ) pour l'ancrage et la recherche batch.
- Configurer Stripe live + Webhooks pour créditer après paiement confirmé.
- Ajouter un rate limiting distribué (Redis + `slowapi`) et une observabilité (Prometheus, Grafana, Sentry).

## 📄 Licence
Projet distribué sous licence MIT.
