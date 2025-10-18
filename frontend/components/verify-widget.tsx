"use client";

import { FormEvent, useState } from "react";
import { API_BASE_URL } from "../lib/config";

interface VerifyResult {
  status: "verified" | "missing";
  created_at?: string | null;
  download_url?: string | null;
  owner?: { id?: string; email?: string | null; display_name?: string | null } | null;
  blockchain_tx?: string | null;
}

export function VerifyWidget() {
  const [hash, setHash] = useState("");
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!hash.trim()) {
      setStatus("Indiquez un hash à contrôler");
      return;
    }
    setLoading(true);
    setStatus("Contrôle en cours…");
    setResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/verify/${encodeURIComponent(hash.trim())}`, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Vérification impossible (${response.status})`);
      }
      const data = await response.json();
      setResult(data);
      setStatus(data.status === "verified" ? "Preuve trouvée" : "Hash inconnu");
    } catch (error) {
      setStatus(`Erreur : ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="glass-card" id="verify">
      <div className="section-heading">
        <div>
          <h2 style={{ margin: 0, fontSize: "1.8rem" }}>Vérification publique instantanée</h2>
          <p style={{ marginTop: "0.25rem", color: "var(--primary)" }}>Consultez le statut, la date et téléchargez le certificat.</p>
        </div>
      </div>
      <form className="grid" onSubmit={handleSubmit}>
        <label>
          <span>Hash (SHA-256)</span>
          <input value={hash} onChange={(event) => setHash(event.target.value)} placeholder="0x…" required />
        </label>
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Recherche…" : "Vérifier"}
        </button>
      </form>
      {status && <p>{status}</p>}
      {result && (
        <div className="glass-card" style={{ gap: "0.75rem", padding: "1.5rem" }}>
          <p style={{ margin: 0 }}>Statut : {result.status === "verified" ? "✅ Validé" : "❌ Inconnu"}</p>
          {result.created_at && <p style={{ margin: 0 }}>Créé le : {new Date(result.created_at).toLocaleString()}</p>}
          {result.owner && (
            <p style={{ margin: 0 }}>
              Propriétaire : {result.owner.display_name ?? result.owner.email ?? result.owner.id}
            </p>
          )}
          {result.blockchain_tx && (
            <a href={`https://polygonscan.com/tx/${result.blockchain_tx}`} target="_blank" rel="noreferrer">
              Voir la transaction blockchain
            </a>
          )}
          {result.download_url && (
            <a className="btn btn-secondary" href={`${API_BASE_URL}${result.download_url}`} target="_blank" rel="noreferrer">
              Télécharger le certificat PDF
            </a>
          )}
        </div>
      )}
    </section>
  );
}
