export default function DocsPage() {
  return (
    <section className="page-section">
      <div className="page-header">
        <span className="badge">Docs</span>
        <h1>Documentation ProofOrigin API & SDK</h1>
        <p>
          Intégrez le pipeline portable dans vos produits : endpoints REST, SDK Node/Python, webhooks
          idempotents et vérificateur embarquable. Un quickstart en 5 minutes pour générer votre première
          preuve et vérifier hors-ligne.
        </p>
      </div>
      <div className="docs-grid">
        <article className="glass-card">
          <h2>Quickstart (5 min)</h2>
          <ol>
            <li>Créez un projet et récupérez votre clé API.</li>
            <li>Installez le SDK : <code>pip install prooforigin</code> ou <code>npm i @prooforigin/sdk</code>.</li>
            <li>
              Appelez <code>client.generateProof(file, metadata)</code> pour obtenir le hash, le .proof et la
              manifest C2PA.
            </li>
            <li>Vérifiez avec <code>client.verify(hash)</code> ou en embarquant le script zero-trust.</li>
          </ol>
        </article>
        <article className="glass-card">
          <h2>Endpoints REST v1</h2>
          <ul>
            <li>
              <code>POST /api/v1/proof</code> — enregistre une création, retourne hash, certificats, reçus.
            </li>
            <li>
              <code>GET /api/v1/transparency</code> — journal append-only filtrable (profil, date, modèle).
            </li>
            <li>
              <code>POST /api/v1/similarity</code> — moteur double index (pHash + CLIP) avec score de risque.
            </li>
            <li>
              <code>GET /api/v1/risk-thresholds</code> — seuils configurés par plan (Free, Pro, Team).
            </li>
          </ul>
        </article>
        <article className="glass-card">
          <h2>SDK Python</h2>
          <pre>
            <code>{`from prooforigin import ProofOrigin
client = ProofOrigin(api_key="sk_live_...")
result = client.generate_proof("cover.png", metadata={"title": "AI cover"})
print(result.hash, result.certificate_url)`}</code>
          </pre>
        </article>
        <article className="glass-card">
          <h2>SDK Node.js</h2>
          <pre>
            <code>{`import { ProofOrigin } from "@prooforigin/sdk";
const client = new ProofOrigin({ apiKey: process.env.PROOFORIGIN_KEY });
const { hash, proofArtifact } = await client.generateProof("cover.mp4", { profile: "Studio" });
`}</code>
          </pre>
        </article>
      </div>
    </section>
  );
}
