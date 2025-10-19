"use client";

import { useEffect, useState } from "react";

import { APP_ORIGIN } from "../lib/config";

interface LogEntry {
  id: string;
  proof_id: string | null;
  profile: string | null;
  asset_hash: string;
  anchored_at: string | null;
  created_at: string;
  receipts: { chain: string; transaction_hash: string | null; anchored_at: string | null }[];
  chain: string | null;
  model: string | null;
  metadata: Record<string, unknown> | null;
  sequence: number;
}

export default function TransparencyLogPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(`${APP_ORIGIN}/api/v1/transparency?page_size=10`, {
          credentials: "include",
        });
        if (!response.ok) throw new Error("Failed to load log");
        const payload = await response.json();
        setEntries(payload.entries ?? []);
      } catch (error) {
        console.error("transparency_log_fetch_failed", error);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  return (
    <section className="page-section">
      <div className="page-header">
        <span className="badge">Ledger</span>
        <h1>Transparency Log</h1>
        <p>
          Explore chaque entrée signée : séquence, hash, profil signataire, modèle IA, reçus blockchain et
          horodatages OpenTimestamps. Filtrez par profil ou modèle pour vos audits RGPD.
        </p>
      </div>
      <div className="glass-card" style={{ display: "grid", gap: "1rem" }}>
        <div className="filters-grid">
          <label>
            Profil
            <input type="text" placeholder="studio@prooforigin.io" />
          </label>
          <label>
            Modèle
            <input type="text" placeholder="StableDiffusion XL" />
          </label>
          <label>
            Hash
            <input type="text" placeholder="0x..." />
          </label>
        </div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Sequence</th>
                <th>Profil</th>
                <th>Hash</th>
                <th>Chaîne</th>
                <th>Ancrage</th>
                <th>Preuve</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "1.2rem" }}>
                    Chargement du journal…
                  </td>
                </tr>
              )}
              {!isLoading && entries.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "1.2rem" }}>
                    Aucune entrée trouvée — générez votre première preuve pour alimenter le journal.
                  </td>
                </tr>
              )}
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td>{entry.sequence}</td>
                  <td>{entry.profile ?? "—"}</td>
                  <td className="mono">{entry.asset_hash.slice(0, 16)}…</td>
                  <td>{entry.chain ?? "Polygon"}</td>
                  <td>{entry.anchored_at ? new Date(entry.anchored_at).toLocaleString() : "pending"}</td>
                  <td>
                    {entry.proof_id ? (
                      <a href={`/verify/${entry.asset_hash}`} className="link">
                        Voir la preuve
                      </a>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
