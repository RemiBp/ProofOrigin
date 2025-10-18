# ProofOrigin – Trust Layer for AI & Creative Assets

ProofOrigin fournit une chaîne complète pour prouver l'origine de contenus numériques : authentification cryptographique, registres append-only, recherche de similarités et intégrations facturation/monitoring. Le backend repose désormais sur **FastAPI + SQLAlchemy**, avec une génération de clés **Ed25519** chiffrées (AES-256 + Argon2id + master key serveur) et une interface web légère prête pour les tests utilisateurs.

## ✨ Fonctionnalités clés

| Domaine | Capacités |
| --- | --- |
| 🔐 **Sécurité & identité** | Argon2id + Ed25519 chiffrée (AES-256-GCM) avec master key fournie par Vault/KMS, rotation (`/rotate-key`), device binding créateur, JWT courts + refresh, artefacts `.proof` versionnés. |
| 📄 **Gestion de preuves** | Pipeline déterministe (strip EXIF, re-encode, resize) avant hash, manifeste C2PA généré automatiquement, signature Ed25519, stockage normalized hash + `.proof`, journalisation d'usage. |
| 🔍 **Similarité & indexation** | Double index pHash/Hamming + embeddings CLIP & SBERT, calcul des risques (absence C2PA, forte similarité), API `similarity` et alertes automatiques. |
| 💳 **Facturation** | Intégration Stripe (ou simulation), enregistrement des paiements/checkout sessions, suivi des crédits, endpoint `usage` avec prochaine fenêtre d'ancrage. |
| ⛓️ **Ancrage blockchain** | Multi-ancrage Polygon + OpenTimestamps, batching Merkle signé, enregistrement des reçus exportables (`chain_receipts`). |
| 🧭 **Ledger & admin** | Transparency log append-only (signature Ed25519), endpoint `/api/v1/proofs/{id}/ledger`, evidence packs, risk scoring. |
| 🛠️ **Ops & monitoring** | Endpoint `/healthz`, journalisation JSON (`structlog`), secrets via Vault/KMS, planification Merkle, usage metering. |
| 🖥️ **Frontend Next.js** | Landing futuriste, upload Next.js connecté à l’API v1, page `/verify/:hash` bilingue avec vérification hors-ligne, dashboard usage & pricing premium. |

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
alembic upgrade head
python app.py  # ou uvicorn prooforigin.app:app --reload
```
Le serveur écoute sur `http://localhost:8000`. L'API interactive est disponible via Swagger (`/docs`) et Redoc (`/redoc`).

### Stack Docker (dev)
```bash
docker compose up --build
```
Cette commande démarre l'API FastAPI, un worker Celery, PostgreSQL, Redis et MinIO (object storage compatible S3). La bucket `prooforigin` est créée automatiquement pour stocker les artefacts.

### Déploiement sur Render

Le fichier [`render.yaml`](./render.yaml) décrit une architecture complète pour Render :

- **`prooforigin-api`** : service web Docker exposant l'API FastAPI.
- **`prooforigin-frontend`** : service Next.js (Node) servant le dashboard public et la landing page immersive.
- **`prooforigin-worker`** : worker Celery pour les tâches asynchrones (similarité, ancrage blockchain, webhooks).
- **`prooforigin-scheduler`** : planificateur Celery Beat pour déclencher les batches d'ancrage.
- **`prooforigin-redis`** : cache partagé pour la file, le rate limiting et le monitoring.
- **`prooforigin-db`** : base PostgreSQL managée.

Déploiement type :

1. Importer le dépôt dans Render puis lancer `render blueprint deploy` (ou déployer via l'interface graphique).
2. Renseigner les secrets (`PROOFORIGIN_PRIVATE_KEY_MASTER_KEY`, credentials S3, clés Stripe/Web3, Sentry...).
3. Configurer l'object storage (`PROOFORIGIN_STORAGE_BACKEND=s3`) et les variables associées.
4. Ajuster les plans Render (`starter`/`standard`/`pro`) selon la charge attendue et activer l'auto-deploy.

> ℹ️ Le blueprint active Prometheus sur l'API, alimente Celery/SlowAPI avec Redis et laisse les options sensibles (`sync: false`) à renseigner via le dashboard Render.

### Variables d'environnement principales
| Variable | Rôle |
| --- | --- |
| `PROOFORIGIN_DATABASE_URL` | URL SQLAlchemy (SQLite par défaut dans `instance/ledger.db`). |
| `PROOFORIGIN_PRIVATE_KEY_MASTER_KEY` | Master key 32 bytes utilisée pour chiffrer les clés privées (obligatoire en prod). |
| `PROOFORIGIN_ACCESS_TOKEN_EXPIRE_MINUTES` | Durée de vie des tokens d'accès. |
| `PROOFORIGIN_STRIPE_API_KEY` / `PROOFORIGIN_STRIPE_PRICE_ID` | Active le mode facturation Stripe. |
| `PROOFORIGIN_STRIPE_PRICE_PRO` / `PROOFORIGIN_STRIPE_PRICE_BUSINESS` | Identifiants Stripe Checkout pour les plans Pro et Business (fallback simulé si absent). |
| `WEB3_RPC_URL` / `WEB3_PRIVATE_KEY` / `PROOFORIGIN_BLOCKCHAIN_ENABLED` | Active l'ancrage réel sur une blockchain compatible EVM. |
| `CONTRACT_ADDRESS` / `CONTRACT_ABI` | Adresse + ABI JSON du contrat `ProofOriginRegistry` déployé sur Polygon. |
| `WEB3_CHAIN_ID` | Force le `chainId` (137 = Polygon mainnet, 80002 = Amoy testnet). |
| `PROOFORIGIN_SENTENCE_TRANSFORMER_MODEL` | Modèle SBERT à charger (par défaut `all-MiniLM-L6-v2`). |
| `PROOFORIGIN_STORAGE_BACKEND` | `local` (par défaut) ou `s3` pour externaliser les fichiers. |
| `PROOFORIGIN_STORAGE_S3_*` | Endpoint, bucket, clés d'accès/secret et région pour l'object storage. |
| `PROOFORIGIN_REDIS_URL` / `PROOFORIGIN_RATE_LIMIT_STORAGE_URL` | Backend Redis utilisé pour Celery + rate limiting. |
| `PROOFORIGIN_TASK_QUEUE_BACKEND` | `inline` ou `celery` selon la présence d'un worker. |
| `PROOFORIGIN_SENTRY_DSN` | Active la télémétrie Sentry si fourni. |

> ⚠️ En production, configurez absolument `PROOFORIGIN_PRIVATE_KEY_MASTER_KEY`, un SGBD externe (PostgreSQL) et un gestionnaire de secrets (Vault, AWS KMS...).

## 🧭 Parcours utilisateur

1. **Inscription** – `POST /api/v1/auth/register` → génération de la paire Ed25519 chiffrée + crédit initial.
2. **Vérification e-mail** – `POST /api/v1/verify-email` (token reçu par mail simulé) ou `POST /api/v1/request-verification` pour renvoyer le lien.
3. **Connexion** – `POST /api/v1/auth/login` (OAuth2 password) → réception `access_token` + `refresh_token`.
4. **Rotation/gestion de clé** – `POST /api/v1/rotate-key` ou `/api/v1/upload-key` pour remplacer la clé privée (revocation loggée).
5. **Génération de preuve** – `POST /api/v1/proof` (texte ou fichier via base64) produit hash normalisé + manifeste C2PA + artefact `.proof`.
6. **Vérification** – `GET /verify/{hash}` (page publique + PDF + manifest JSON + script zéro-trust) ou `GET /api/v1/verify/{hash}` côté API.
7. **Listing & détails** – `GET /api/v1/proofs` (pagination) & `GET /api/v1/proofs/{id}`/`GET /api/v1/proofs/{id}/ledger` pour la transparence log & reçus multi-chaînes.
8. **Similarité** – `POST /api/v1/similarity` (texte) ou planification batch → scoring de risque et alertes automatiques.
9. **Quotas & facturation** – `GET /api/v1/usage`, `POST /api/v1/buy-credits` (Stripe ou mode démo).
10. **Alertes & rapports** – `POST /api/v1/report` (génère un evidence pack zip), `POST /api/v1/batch-verify` (jobs asynchrones + webhook).
11. **Administration** – `/api/v1/admin/users` & `/api/v1/admin/proofs` pour la modération et la supervision.

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
- **Images** : pHash/dHash via `imagehash` + embeddings CLIP (`sentence-transformers/clip-ViT-B-32`) pour une recherche perceptuelle et sémantique.
- **Texte** : embeddings SBERT (`sentence-transformers`) et similarité cosinus.
- **Pipeline** : lors de la génération d'une preuve, `SimilarityEngine` calcule les empreintes, alimente `similarity_index`, crée les `similarity_matches`, relations (`proof_relations`) et alertes si score ≥ 0.8.
- **Vector DB** : stockage JSON des embeddings (clip/text/phash) dans `similarity_index`, compatible avec une migration FAISS/Milvus ultérieure.

## 🔐 Gestion des clés
- **Génération** : Ed25519 (libs `cryptography`).
- **Chiffrement** : AES-256-GCM avec clé dérivée Argon2id (paramètres configurables) + master key serveur.
- **Rotation** : endpoints `POST /api/v1/rotate-key` (génération serveur + révocation enregistrée) ou `POST /api/v1/upload-key` (clé fournie par l'utilisateur).
- **Vérification e-mail / KYC light** : `POST /api/v1/verify-email` + `POST /api/v1/request-verification` pour valider les comptes avant usage avancé.
- **JWT** : signé HS256 avec TTL court (configurable) + refresh token 14 jours.

## 💳 Facturation & quotas
- Chaque utilisateur dispose d'un compteur de crédits (`users.credits`).
- Le `generate_proof` décrémente 1 crédit et journalise l'action (`usage_logs`).
- `POST /api/v1/buy-credits` : crée une session Stripe (si clé configurée) ou crédite automatiquement en mode démo.
- `GET /api/v1/usage` : expose preuves générées, vérifications et dernier paiement.

## ⛓️ Blockchain
- `PolygonAnchor` (service Python) appelle `recordProof(bytes32)` sur le contrat [`contracts/ProofOriginRegistry.sol`](./contracts/ProofOriginRegistry.sol) et stocke le `transaction_hash` dans `proofs.blockchain_tx`.
- Les preuves sont ancrées en temps réel lors du `POST /api/v1/register`; en absence de configuration Web3, un fallback batch Merkle + OpenTimestamps est planifié (Celery) pour conserver une preuve temporelle.
- La page `/verify/<hash>` et le dashboard exposent un lien PolygonScan (`https://polygonscan.com/tx/<transaction_hash>`). Les colonnes `blockchain_tx`, `anchor_signature`, `anchored_at`, `anchor_batch_id` restent accessibles via `/ledger/{id}`.

## 🖥️ UI & UX
- Frontend **Next.js 14** (`frontend/`) avec design glassmorphism inspiré Revolut.
- Page d’accueil : upload connecté à `POST /api/v1/proof`, vérification `GET /verify/:hash`, CTA pricing.
- Dashboard : suivi des quotas via `GET /api/v1/usage` (X-API-Key) et génération de sessions Stripe `POST /api/v1/buy-credits`.
- Pages dédiées `/pricing` et `/verify/:hash` pour un accès public sans connaissances techniques.

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
│   │   └── routers/{auth,billing,proofs,ledger,admin}.py
│   ├── core/                      # Config, ORM, sécurité, logging
│   │   ├── settings.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── security.py
│   ├── services/                  # Blockchain, similarité, etc.
│   ├── templates/                 # Interface web (Jinja2)
│   └── web/router.py              # Routes web
├── scripts/                       # CLI et outils
├── frontend/                      # Frontend Next.js (landing, dashboard, pricing)
├── sdks/                          # SDKs clients (inchangés)
├── instance/                      # DB, artefacts, stockages
└── requirements.txt
```

## ✅ Tests rapides
```bash
# Sanity check : compilation et typage de base
python -m py_compile $(git ls-files '*.py')

# Tests unitaires
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest

# Lancer l'app en mode développement
uvicorn prooforigin.app:app --reload
```

## 🔒 Bonnes pratiques avant prod
- Utiliser PostgreSQL + migrations (Alembic) au lieu de SQLite (déjà supporté via `alembic`).
- Brancher un service KMS/Vault pour la master key.
- Basculer le moteur ANN vers FAISS/Milvus/Pinecone et déployer la file Celery en production.
- Configurer Stripe live + Webhooks pour créditer après paiement confirmé.
- Brancher les dashboards Prometheus/Grafana et Sentry sur les endpoints `/metrics` et DSN dédiés.

## 📄 Licence
Projet distribué sous licence MIT.
