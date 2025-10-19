"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { FormEvent, useEffect, useState } from "react";

import { API_BASE_URL, APP_ORIGIN } from "../lib/config";
import { useTranslations } from "./i18n/language-provider";

interface ProofOwner {
  id?: string;
  email?: string | null;
  display_name?: string | null;
}

interface ProofResult {
  id: string;
  file_hash: string;
  normalized_hash: string;
  created_at: string;
  blockchain_tx?: string | null;
  metadata?: Record<string, unknown> | null;
  owner?: ProofOwner | null;
interface ProofResult {
  id: string;
  file_hash: string;
  created_at: string;
  blockchain_tx?: string | null;
}

const emptyResult: ProofResult | null = null;

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function sha256FromBuffer(buffer: ArrayBuffer): Promise<string> {
  if (typeof window === "undefined" || !window.crypto?.subtle) {
    return "";
  }
  const digest = await window.crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function sha256FromText(input: string): Promise<string> {
  const encoded = new TextEncoder().encode(input);
  return sha256FromBuffer(encoded.buffer);
}

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
  const [clientHash, setClientHash] = useState<string | null>(null);
  const t = useTranslations();

  const proofOwnerLabel = useMemo(() => {
    if (!proof?.owner) return null;
    return proof.owner.display_name ?? proof.owner.email ?? proof.owner.id ?? null;
  }, [proof?.owner]);

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
      return;
    }

    setLoading(true);
    setStatus(t.upload.statusHashing);
    setProof(null);
    setClientHash(null);
    setStatus(t.upload.statusLoading);
    setProof(null);

    try {
      const payload: Record<string, unknown> = {
        key_password: keyPassword,
        metadata: { channel: "web" },
      };
      let computedHash: string | null = null;
      if (file) {
        const buffer = await file.arrayBuffer();
        computedHash = await sha256FromBuffer(buffer);
        payload.content = arrayBufferToBase64(buffer);
      if (file) {
        payload.content = await fileToBase64(file);
        payload.filename = file.name;
        payload.mime_type = file.type;
      } else {
        payload.text = textPayload;
        computedHash = await sha256FromText(textPayload);
        payload.filename = `texte-${Date.now()}.txt`;
        payload.mime_type = "text/plain";
      }

      if (computedHash) {
        payload.client_hash = computedHash;
        setClientHash(computedHash);
      }

      setStatus(t.upload.statusLoading);

      const response = await fetch(`${API_BASE_URL}/api/v1/proof`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = `Erreur ${response.status}`;
        try {
          const errorPayload = await response.json();
          if (errorPayload.detail) {
            message = errorPayload.detail;
          }
        } catch (parseError) {
          const fallback = await response.text();
          if (fallback) message = fallback;
        }
        throw new Error(message);
        const errorText = await response.text();
        throw new Error(errorText || `Erreur ${response.status}`);
      }

      const data = await response.json();
      setProof({
        id: data.id,
        file_hash: data.file_hash,
        normalized_hash: data.normalized_hash,
        created_at: data.created_at,
        blockchain_tx: data.blockchain_tx,
        metadata: data.metadata,
        owner: data.owner,
        created_at: data.created_at,
        blockchain_tx: data.blockchain_tx,
      });
      setStatus(t.upload.statusSuccess);
    } catch (error) {
      console.error(error);
      setStatus(t.upload.statusError.replace("{{message}}", (error as Error).message));
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
          <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? t.upload.submitting : t.upload.submit}
          </button>
          <span className="badge">{t.upload.compatibilityBadge}</span>
        </div>
      </form>
      {status && <p>{status}</p>}
      {proof && (
        <div className="glass-card" style={{ gap: "0.75rem", padding: "1.5rem" }}>
          <h3 style={{ margin: 0 }}>
            {t.upload.proofHeading}
            {proof.id.slice(0, 8)}
          </h3>
          {clientHash && (
            <p style={{ margin: 0 }}>
              {t.upload.clientHashLabel} <code>{clientHash}</code>
            </p>
          )}
          <p style={{ margin: 0 }}>
            {t.upload.hashLabel} {proof.file_hash}
          </p>
          <p style={{ margin: 0 }}>
            {t.upload.normalizedHashLabel} {proof.normalized_hash}
          </p>
          <p style={{ margin: 0 }}>
            {t.upload.createdAtLabel} {new Date(proof.created_at).toLocaleString()}
          </p>
          {proofOwnerLabel && (
            <p style={{ margin: 0 }}>
              {t.upload.ownerLabel} {proofOwnerLabel}
            </p>
          )}
            {t.upload.createdAtLabel} {new Date(proof.created_at).toLocaleString()}
          </p>
          {proof.blockchain_tx ? (
            <a href={`https://polygonscan.com/tx/${proof.blockchain_tx}`} target="_blank" rel="noreferrer">
              {t.upload.anchorLink}
            </a>
          ) : (
            <span>{t.upload.anchorPending}</span>
          )}
          <div className="metadata-block">
            <h4>{t.upload.metadataHeading}</h4>
            {proof.metadata ? (
              <pre>{JSON.stringify(proof.metadata, null, 2)}</pre>
            ) : (
              <p>{t.upload.metadataEmpty}</p>
            )}
          </div>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <a className="btn btn-secondary" href={`${appUrl}/verify/${proof.file_hash}`} target="_blank" rel="noreferrer">
              {t.upload.verifyButton}
            </a>
            <a className="btn btn-secondary" href={`${API_BASE_URL}/verify/${proof.file_hash}/certificate`} target="_blank" rel="noreferrer">
              {t.upload.downloadButton}
            </a>
          </div>
        </div>
      )}
    </section>
  );
}

