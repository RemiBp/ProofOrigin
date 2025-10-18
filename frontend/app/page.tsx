import Link from "next/link";

import { UploadForm } from "../components/upload-form";
import { VerifyWidget } from "../components/verify-widget";
import { APP_ORIGIN } from "../lib/config";

export default function HomePage() {
  return (
    <>
      <section className="glass-card" style={{ position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 10% 10%, rgba(99,102,241,0.3), transparent 55%)" }} />
        <div style={{ position: "relative", display: "grid", gap: "1.5rem" }}>
          <span className="badge">Proof-as-a-Service</span>
          <h1 style={{ fontSize: "3rem", margin: 0 }}>Le passeport infalsifiable de vos créations.</h1>
          <p style={{ maxWidth: "720px", fontSize: "1.1rem", lineHeight: 1.6 }}>
            ProofOrigin combine hashing SHA-256, signatures Ed25519, ancrage blockchain et horodatage OpenTimestamps pour délivrer
            des certificats PDF vérifiables à l’échelle mondiale. Upload unique, API batch ou intégration IA : tout est prêt.
          </p>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <Link className="btn btn-primary" href="#upload">
              Déposer une création
            </Link>
            <Link className="btn btn-secondary" href="/pricing">
              Découvrir les plans
            </Link>
            <a className="btn btn-secondary" href={`${APP_ORIGIN}/docs`} target="_blank" rel="noreferrer">
              Documentation API
            </a>
          </div>
          <div className="grid grid-two">
            <div>
              <h3 style={{ marginBottom: "0.25rem" }}>Ancrage blockchain</h3>
              <p style={{ margin: 0 }}>Polygon, Base, Arbitrum & OpenTimestamps, orchestrés automatiquement.</p>
            </div>
            <div>
              <h3 style={{ marginBottom: "0.25rem" }}>Webhooks & SDK</h3>
              <p style={{ margin: 0 }}>Recevez les preuves en push et intégrez nos SDK Python & Node en quelques lignes.</p>
            </div>
          </div>
        </div>
      </section>
      <UploadForm />
      <VerifyWidget />
      <section className="glass-card">
        <div className="section-heading">
          <h2 style={{ margin: 0 }}>Connectez ProofOrigin à votre stack</h2>
          <span className="badge">API REST / OAuth2 / Webhooks</span>
        </div>
        <div className="grid grid-two">
          <article>
            <h3>OAuth2 + JWT</h3>
            <p>Connexion rapide via Google, GitHub ou Auth0. Les tokens JWT sécurisent vos requêtes serveur à serveur.</p>
            <ul>
              <li>Rotation de clés Ed25519 chiffrées côté serveur</li>
              <li>Gestion de comptes multi-équipes et rôles</li>
              <li>API keys illimitées avec quotas par plan</li>
            </ul>
          </article>
          <article>
            <h3>Proof for AI</h3>
            <p>Endpoint <code>/api/v1/ai/proof</code> pour certifier vos générations IA (model_name, prompt, timestamp).</p>
            <ul>
              <li>Webhook de retour pour Runway, Midjourney, StableDiffusion</li>
              <li>Badges dynamiques « ProofOrigin Certified »</li>
              <li>Batch processing jusqu’à 10 000 contenus</li>
            </ul>
          </article>
        </div>
        <div className="cta-banner">
          <h3 style={{ margin: 0 }}>Prêt à passer en production ?</h3>
          <p style={{ margin: 0 }}>Déployez sur Render grâce au blueprint fourni et suivez vos preuves depuis le dashboard Next.js.</p>
          <Link className="btn btn-secondary" href="/dashboard">
            Ouvrir le dashboard
          </Link>
        </div>
      </section>
    </>
  );
}
