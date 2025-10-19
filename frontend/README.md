# ProofOrigin Frontend (Next.js)

Cette application Next.js offre une expérience web immersive pour ProofOrigin :

- Page d’accueil bilingue avec onboarding, upload connecté à l’API publique (`POST /api/v1/proof`) et prévisualisation de l’ancrage multi-chaînes.
- Page `/verify/:hash` immersive avec badge Polygon, reçus Merkle, téléchargement manifeste C2PA et vérificateur hors-ligne (WebCrypto).
- Dashboard client permettant de suivre les quotas, le risque, les clés API et de déclencher des upgrades Stripe.
- Pages publiques de tarification, badges et documentation Proof-as-a-Service.

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
