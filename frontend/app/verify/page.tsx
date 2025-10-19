"use client";

import { VerifyWidget } from "components/verify-widget";

export default function VerifyPage() {
  return (
    <section className="page-section gradient-border">
      <div className="page-header">
        <span className="badge">Zero-Trust</span>
        <h1>Vérifiez une création en un instant</h1>
        <p>
          Déposez un fichier, collez une URL ou chargez un certificat .proof pour obtenir un verdict
          immédiat : hash, Merkle, C2PA et ancrage blockchain sont recalculés localement avant tout appel
          réseau.
        </p>
      </div>
      <VerifyWidget />
    </section>
  );
}
