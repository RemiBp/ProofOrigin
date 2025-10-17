# ProofOrigin – Résumé d'implémentation

## État actuel
- Backend migré vers **FastAPI** avec organisation modulaire (`prooforigin.api`, `prooforigin.core`, `prooforigin.services`).
- Stockage persistant via **SQLAlchemy** (SQLite par défaut, prêt pour PostgreSQL) et modèles couvrant utilisateurs, preuves, similarité, paiements, rapports et batch jobs.
- Authentification complète : inscription, login OAuth2, refresh token, vérification e-mail, rotation de clé (`/rotate-key`) avec journalisation `key_revocations`, crédits utilisateurs.
- Preuve : génération multipart (`file` + `metadata` + `key_password`), signature Ed25519, export `.proof`, attribution à un batch d'ancrage (`anchor_batches`), journalisation d'usage et décrément des crédits.
- Vérification : endpoints JSON & multipart, script CLI, stockage des logs, endpoint `/ledger/{id}` pour la vue détaillée.
- Similarité : moteur hybride pHash/dHash + SBERT + CLIP (`sentence-transformers`), index `similarity_index`, relations (`proof_relations`) et alertes automatiques.
- Facturation & quotas : intégration Stripe (simulation ou clé live), enregistrement des paiements/sessions, suivi crédits via `/api/v1/usage` avec prochaine fenêtre d'ancrage.
- Administration : endpoints `/api/v1/admin/users` & `/api/v1/admin/proofs`, génération d'evidence pack zip via `/api/v1/report`.
- Dashboard web : pages `/` et `/dashboard` alimentées par l'API, formulaires JS pour inscription/login/génération/vérification.
- Services : ancrage blockchain (mode réel/simulé), structlog pour audit, script CLI de vérification hors ligne.

## Points notables
- **Sécurité clés** : Ed25519 chiffrées via AES-256-GCM, clé dérivée Argon2id + master key serveur (`PROOFORIGIN_PRIVATE_KEY_MASTER_KEY`).
- **JWT** : HS256, TTL configurable, refresh 14 jours.
- **Artefact .proof** : POP-1.0 (hash SHA-256, signature Ed25519, clé publique PEM + raw, métadonnées). Stocké dans `instance/storage/<proof_id>/`.
- **Tables principales** : `users`, `proofs`, `proof_files`, `similarity_matches`, `similarity_index`, `proof_relations`, `anchor_batches`, `api_keys`, `payments`, `usage_logs`, `alerts`, `reports`, `batch_jobs`, `key_revocations`.
- **Similarité** : mise à jour automatique (embeddings CLIP/SBERT + pHash), alertes si score ≥ 0.8, endpoint `search-similar` multi-modal.
- **Ledger/Admin** : `/ledger/{id}` expose hash/signature/ancrage + matches/alertes, `/api/v1/admin/*` agrège utilisateurs/proofs et scores suspects.
- **Billing** : `POST /api/v1/buy-credits` (Stripe ou mode démo) enregistre paiements/sessions, `GET /api/v1/usage` fournit la prochaine fenêtre d'ancrage.
- **Batch/Reporting** : `POST /api/v1/report` produit un evidence pack `.zip`; `batch_verify` enregistre le job pour traitement différé.

## À prévoir
- Ajout d'une file de tâches (Celery/RQ) pour batch verify & ancrage massif.
- Pagination avancée + filtres supplémentaires côté `/dashboard`.
- Gestion des webhooks Stripe (créditer après paiement confirmé).
- Intégration d'un moteur ANN (FAISS/Milvus/Pinecone) si volumétrie élevée.
- Monitoring renforcé (Prometheus, Grafana, Sentry) et rate limiting distribué (Redis + slowapi).
- Mise en place de migrations Alembic pour environnements multi-tenant.
