# ProofOrigin Frontend (Next.js)

Cette application Next.js offre une expérience web immersive pour ProofOrigin :

- Page d’accueil avec onboarding, upload connecté à l’API publique (`POST /api/v1/proof`) et vérification en direct (`GET /verify/:hash`).
- Dashboard client permettant de consulter les quotas via clé API et de générer des sessions Stripe pour upgrader le plan.
- Pages publiques de tarification et de vérification dynamique.

## Démarrage

```bash
cd frontend
npm install
npm run dev
```

Configurez les variables d’environnement dans `.env.local` :

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_ORIGIN=http://localhost:3000
```

Le build de production se lance via :

```bash
npm run build
npm start
```

La configuration Render incluse dans `render.yaml` déploie automatiquement ce frontend aux côtés de l’API FastAPI.
