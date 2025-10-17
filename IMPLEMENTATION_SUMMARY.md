# ProofOrigin – Résumé d'implémentation

## État actuel
- Backend migré vers **FastAPI** avec organisation modulaire (`prooforigin.api`, `prooforigin.core`, `prooforigin.services`).
- Stockage persistant via **SQLAlchemy** (SQLite par défaut, prêt pour PostgreSQL) et modèles couvrant utilisateurs, preuves, similarité, paiements, rapports et batch jobs.
- Authentification complète : inscription, login OAuth2, refresh token, rotation de clé privée, crédits utilisateurs.
- Preuve : génération multipart (`file` + `metadata` + `key_password`), signature Ed25519, export automatique d'un artefact `.proof`, journalisation d'usage, décrément des crédits, planification d'ancrage blockchain.
- Vérification : endpoints JSON & multipart, script CLI mis à jour pour Ed25519, stockage des logs d'utilisation.
- Similarité : moteur hybride pHash/dHash + SBERT (`sentence-transformers`) avec stockage des embeddings et matches.
- Facturation & quotas : intégration Stripe (avec mode simulation), suivi crédits via `/api/v1/usage` et enregistrement des paiements.
- Dashboard web : pages `/` et `/dashboard` alimentées par l'API, formulaires JS pour inscription/login/génération/vérification.
- Services : ancrage blockchain (mode réel/simulé), structlog pour audit, script CLI de vérification hors ligne.

## Points notables
- **Sécurité clés** : Ed25519 chiffrées via AES-256-GCM, clé dérivée Argon2id + master key serveur (`PROOFORIGIN_PRIVATE_KEY_MASTER_KEY`).
- **JWT** : HS256, TTL configurable, refresh 14 jours.
- **Artefact .proof** : POP-1.0 (hash SHA-256, signature Ed25519, clé publique PEM + raw, métadonnées). Stocké dans `instance/storage/<proof_id>/`.
- **Tables principales** : `users`, `proofs`, `proof_files`, `similarity_matches`, `api_keys`, `payments`, `usage_logs`, `alerts`, `reports`, `batch_jobs`.
- **Similarité** : mise à jour automatique à la création de preuve, endpoint `search-similar` pour texte/fichier.
- **Billing** : `POST /api/v1/buy-credits` (Stripe ou mode démo) et `GET /api/v1/usage`.
- **Batch/Reporting** : endpoints placeholder fonctionnels (`batch_verify`, `report`) pour orchestrations futures.

## À prévoir
- Ajout d'une file de tâches (Celery/RQ) pour batch verify & ancrage massif.
- Pagination avancée + filtres supplémentaires côté `/dashboard`.
- Gestion des webhooks Stripe (créditer après paiement confirmé).
- Intégration d'un moteur ANN (FAISS/Milvus/Pinecone) si volumétrie élevée.
- Monitoring renforcé (Prometheus, Grafana, Sentry) et rate limiting distribué (Redis + slowapi).
- Mise en place de migrations Alembic pour environnements multi-tenant.
