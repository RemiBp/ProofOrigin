"use client";

import { FormEvent, useEffect, useState } from "react";

import { API_BASE_URL, APP_ORIGIN } from "../lib/config";
import { useTranslations } from "./i18n/language-provider";
import { API_BASE_URL, APP_ORIGIN } from "../lib/config";

interface ProofResult {
  id: string;
  file_hash: string;
  created_at: string;
  blockchain_tx?: string | null;
}

const emptyResult: ProofResult | null = null;

async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary);
}

export function UploadForm() {
  const [apiKey, setApiKey] = useState("");
  const [keyPassword, setKeyPassword] = useState("");
  const [textPayload, setTextPayload] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>("");
  const [proof, setProof] = useState<ProofResult | null>(emptyResult);
  const [loading, setLoading] = useState(false);
  const [appUrl, setAppUrl] = useState(APP_ORIGIN);
  const t = useTranslations();

  useEffect(() => {
    if (typeof window !== "undefined") {
      setAppUrl(window.location.origin);
    }
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey) {
      setStatus(t.upload.statusMissingApiKey);
      return;
    }
    if (!keyPassword) {
      setStatus(t.upload.statusMissingKeyPassword);
      return;
    }
    if (!file && !textPayload.trim()) {
      setStatus(t.upload.statusMissingPayload);
      setStatus("Merci de renseigner votre clé API X-API-Key.");
      return;
    }
    if (!keyPassword) {
      setStatus("Votre mot de passe de clé privée est requis.");
      return;
    }
    if (!file && !textPayload.trim()) {
      setStatus("Ajoutez un fichier ou un texte à certifier.");
      return;
    }

    setLoading(true);
    setStatus(t.upload.statusLoading);
    setStatus("Génération de la preuve en cours…");
    setProof(null);

    try {
      const payload: Record<string, unknown> = {
        key_password: keyPassword,
        metadata: { channel: "web" },
      };
      if (file) {
        payload.content = await fileToBase64(file);
        payload.filename = file.name;
        payload.mime_type = file.type;
      } else {
        payload.text = textPayload;
        payload.filename = `texte-${Date.now()}.txt`;
        payload.mime_type = "text/plain";
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/proof`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Erreur ${response.status}`);
      }

      const data = await response.json();
      setProof({
        id: data.id,
        file_hash: data.file_hash,
        created_at: data.created_at,
        blockchain_tx: data.blockchain_tx,
      });
      setStatus(t.upload.statusSuccess);
    } catch (error) {
      console.error(error);
      setStatus(t.upload.statusError.replace("{{message}}", (error as Error).message));
      setStatus("Preuve générée avec succès. Vous pouvez télécharger le certificat.");
    } catch (error) {
      console.error(error);
      setStatus(`Impossible de générer la preuve : ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="glass-card" id="upload">
      <div className="section-heading">
        <div>
          <h2 style={{ margin: 0, fontSize: "1.8rem" }}>{t.upload.heading}</h2>
          <p style={{ marginTop: "0.25rem", color: "var(--primary)" }}>{t.upload.subheading}</p>
          <h2 style={{ margin: 0, fontSize: "1.8rem" }}>Uploader et certifier en direct</h2>
          <p style={{ marginTop: "0.25rem", color: "var(--primary)" }}>Hash SHA-256, signature Ed25519 et certificat PDF instantané.</p>
        </div>
      </div>
      <form className="grid" onSubmit={handleSubmit}>
        <div className="grid grid-two">
          <label>
            <span>{t.upload.apiKeyLabel}</span>
            <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="pk_live_..." required />
          </label>
          <label>
            <span>{t.upload.keyPasswordLabel}</span>
            <input type="password" value={keyPassword} onChange={(event) => setKeyPassword(event.target.value)} placeholder="•••••" required />
          </label>
        </div>
        <label>
          <span>{t.upload.textLabel}</span>
          <textarea
            rows={4}
            value={textPayload}
            onChange={(event) => setTextPayload(event.target.value)}
            placeholder={t.upload.textPlaceholder}
          />
        </label>
        <label>
          <span>{t.upload.fileLabel}</span>
            <span>Clé API (X-API-Key)</span>
            <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="pk_live_..." required />
          </label>
          <label>
            <span>Mot de passe de clé</span>
            <input type="password" value={keyPassword} onChange={(event) => setKeyPassword(event.target.value)} placeholder="••••••" required />
          </label>
        </div>
        <label>
          <span>Texte à certifier</span>
          <textarea rows={4} value={textPayload} onChange={(event) => setTextPayload(event.target.value)} placeholder="Collez ici une description, un prompt IA, un script…" />
        </label>
        <label>
          <span>Fichier (optionnel)</span>
          <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? t.upload.submitting : t.upload.submit}
          </button>
          <span className="badge">{t.upload.compatibilityBadge}</span>
            {loading ? "Génération…" : "Certifier maintenant"}
          </button>
          <span className="badge">Compatible Polygon · Base · OpenTimestamps</span>
        </div>
      </form>
      {status && <p>{status}</p>}
      {proof && (
        <div className="glass-card" style={{ gap: "0.75rem", padding: "1.5rem" }}>
          <h3 style={{ margin: 0 }}>
            {t.upload.proofHeading}
            {proof.id.slice(0, 8)}
          </h3>
          <p style={{ margin: 0 }}>
            {t.upload.hashLabel} {proof.file_hash}
          </p>
          <p style={{ margin: 0 }}>
            {t.upload.createdAtLabel} {new Date(proof.created_at).toLocaleString()}
          </p>
          {proof.blockchain_tx ? (
            <a href={`https://polygonscan.com/tx/${proof.blockchain_tx}`} target="_blank" rel="noreferrer">
              {t.upload.anchorLink}
            </a>
          ) : (
            <span>{t.upload.anchorPending}</span>
          )}
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <a className="btn btn-secondary" href={`${appUrl}/verify/${proof.file_hash}`} target="_blank" rel="noreferrer">
              {t.upload.verifyButton}
            </a>
            <a className="btn btn-secondary" href={`${API_BASE_URL}/verify/${proof.file_hash}/certificate`} target="_blank" rel="noreferrer">
              {t.upload.downloadButton}
          <h3 style={{ margin: 0 }}>Preuve #{proof.id.slice(0, 8)}</h3>
          <p style={{ margin: 0 }}>Hash : {proof.file_hash}</p>
          <p style={{ margin: 0 }}>Créée le : {new Date(proof.created_at).toLocaleString()}</p>
          {proof.blockchain_tx ? (
            <a href={`https://polygonscan.com/tx/${proof.blockchain_tx}`} target="_blank" rel="noreferrer">
              Voir l’ancrage blockchain
            </a>
          ) : (
            <span>En attente d’ancrage blockchain…</span>
          )}
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <a className="btn btn-secondary" href={`${appUrl}/verify/${proof.file_hash}`} target="_blank" rel="noreferrer">
              Vérifier publiquement
            </a>
            <a className="btn btn-secondary" href={`${API_BASE_URL}/verify/${proof.file_hash}/certificate`} target="_blank" rel="noreferrer">
              Télécharger le certificat PDF
            </a>
          </div>
        </div>
      )}
    </section>
  );
}

