"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useTranslations } from "../../../components/i18n/language-provider";
import { API_BASE_URL } from "../../../lib/config";

interface PublicProofStatus {
  hash: string;
  status: "verified" | "missing";
  created_at?: string | null;
  owner?: { id?: string; email?: string | null; display_name?: string | null } | null;
  blockchain_tx?: string | null;
  download_url?: string | null;
  proof_id?: string | null;
  anchored?: boolean;
  normalized_hash?: string | null;
  ledger?: Record<string, unknown> | null;
  c2pa_manifest_ref?: string | null;
  opentimestamps_receipt?: Record<string, unknown> | null;
  risk_score?: number | null;
}

type ZeroTrustResult = {
  computedHash: string;
  matchesLedger: boolean | null;
  matchesManifest: boolean | null;
  receipts: Array<{ chain?: string; transaction_hash?: string | null; anchored_at?: string | null }>;
};

declare global {
  interface Window {
    ProofOriginVerifier?: {
      verify: (options: {
        file: File;
        manifestUrl?: string | null;
        ledger?: Record<string, unknown> | null;
      }) => Promise<ZeroTrustResult>;
    };
  }
}

interface Props {
  params: { hash: string };
}

export default function VerifyPage({ params }: Props) {
  const [proof, setProof] = useState<PublicProofStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [zeroTrust, setZeroTrust] = useState<ZeroTrustResult | null>(null);
  const [verifying, setVerifying] = useState(false);
  const t = useTranslations();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/verify/${encodeURIComponent(params.hash)}`, {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error("not_found");
        }
        const data = (await response.json()) as PublicProofStatus;
        if (!cancelled) {
          setProof(data);
          setZeroTrust(null);
        }
      } catch (err) {
        if (!cancelled) {
          const code = (err as Error).message;
          if (code === "not_found") {
            setError(t.publicVerify.notFoundDescription.replace("{{hash}}", params.hash));
          } else {
            setError(t.verify.statusError.replace("{{message}}", (err as Error).message));
          }
          setProof(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [params.hash, t.publicVerify.notFoundDescription, t.verify.statusError]);

  if (loading) {
    return (
      <section className="glass-card">
        <h1>{t.publicVerify.heading}</h1>
        <p>{t.publicVerify.loading}</p>
      </section>
    );
  }

  if (error || !proof) {
    return (
      <section className="glass-card">
        <h1>{t.publicVerify.notFoundTitle}</h1>
        <p>{error ?? t.publicVerify.notFoundDescription.replace("{{hash}}", params.hash)}</p>
        <Link className="btn btn-secondary" href="/">
          {t.publicVerify.backHome}
        </Link>
      </section>
    );
  }

  return (
    <section className="glass-card">
      <h1 style={{ margin: 0 }}>{t.publicVerify.heading}</h1>
      <p style={{ margin: 0 }}>
        {t.publicVerify.hashLabel} {proof.hash}
      </p>
      <p style={{ margin: 0 }}>
        {t.publicVerify.statusLabel} {proof.status === "verified" ? t.publicVerify.statusVerified : t.publicVerify.statusMissing}
      </p>
      <div className="verify-grid">
        <div className="verify-card">
          <h2>{t.publicVerify.summary}</h2>
          <ul>
            {proof.created_at && (
              <li>
                <span>{t.publicVerify.createdAt}</span>
                <strong>{new Date(proof.created_at).toLocaleString()}</strong>
              </li>
            )}
            {proof.owner && (
              <li>
                <span>{t.publicVerify.owner}</span>
                <strong>{proof.owner.display_name ?? proof.owner.email ?? proof.owner.id}</strong>
              </li>
            )}
            {proof.normalized_hash && (
              <li>
                <span>Normalized SHA-256</span>
                <code>{proof.normalized_hash}</code>
              </li>
            )}
          </ul>
          <div className="risk-meter">
            <div className="risk-meter__label">{t.publicVerify.riskLabel}</div>
            <div className="risk-meter__bar">
              <div
                className="risk-meter__fill"
                style={{ width: `${Math.min(100, proof.risk_score ?? 0)}%` }}
              />
            </div>
            <span className="risk-meter__score">{proof.risk_score ?? 0}/100</span>
          </div>
        </div>
        <div className="verify-card">
          <h2>{t.publicVerify.anchorHeading}</h2>
          {proof.anchored && proof.blockchain_tx ? (
            <a
              className="anchor-link"
              href={`https://polygonscan.com/tx/${proof.blockchain_tx}`}
              target="_blank"
              rel="noreferrer"
            >
              {t.publicVerify.anchorLink}
            </a>
          ) : (
            <p>{t.publicVerify.anchorPending}</p>
          )}
          {proof.opentimestamps_receipt && (
            <pre className="ots-receipt">
              {JSON.stringify(proof.opentimestamps_receipt, null, 2)}
            </pre>
          )}
        </div>
        <div className="verify-card">
          <h2>{t.publicVerify.zeroTrustHeading}</h2>
          <p>{t.publicVerify.zeroTrustDescription}</p>
          <label className="upload-button">
            <input
              type="file"
              hidden
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file || !proof) return;
                if (!window.ProofOriginVerifier) {
                  setError(t.publicVerify.zeroTrustUnavailable);
                  return;
                }
                setVerifying(true);
                try {
                  const result = await window.ProofOriginVerifier.verify({
                    file,
                    manifestUrl: proof.c2pa_manifest_ref
                      ? `${API_BASE_URL}/verify/${proof.hash}/manifest`
                      : undefined,
                    ledger: proof.ledger as Record<string, unknown> | null,
                  });
                  setZeroTrust(result);
                } catch (verificationError) {
                  setError((verificationError as Error).message);
                } finally {
                  setVerifying(false);
                }
              }}
            />
            {verifying ? t.publicVerify.zeroTrustVerifying : t.publicVerify.zeroTrustUpload}
          </label>
          {zeroTrust && (
            <div className="zero-trust-results">
              <p>
                {t.publicVerify.zeroTrustComputed} <code>{zeroTrust.computedHash}</code>
              </p>
              <p>
                {t.publicVerify.zeroTrustLedger}
                <strong>
                  {zeroTrust.matchesLedger === null
                    ? t.publicVerify.zeroTrustNA
                    : zeroTrust.matchesLedger
                    ? t.publicVerify.zeroTrustOk
                    : t.publicVerify.zeroTrustKo}
                </strong>
              </p>
              <p>
                {t.publicVerify.zeroTrustManifest}
                <strong>
                  {zeroTrust.matchesManifest === null
                    ? t.publicVerify.zeroTrustNA
                    : zeroTrust.matchesManifest
                    ? t.publicVerify.zeroTrustOk
                    : t.publicVerify.zeroTrustKo}
                </strong>
              </p>
            </div>
          )}
        </div>
        <div className="verify-card">
          <h2>{t.publicVerify.receiptsHeading}</h2>
          <ul className="receipt-list">
            {(zeroTrust?.receipts || (proof.ledger?.blockchain_receipts as Array<Record<string, string>>) || []).map(
              (receipt, idx) => (
                <li key={idx}>
                  <span>{receipt.chain?.toUpperCase()}</span>
                  {receipt.transaction_hash && (
                    <a
                      href={`https://${receipt.chain?.includes("polygon") ? "polygonscan" : "explorer"}.com/tx/${receipt.transaction_hash}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {receipt.transaction_hash}
                    </a>
                  )}
                </li>
              )
            )}
          </ul>
        </div>
      </div>
      <div className="verify-actions">
        {proof.download_url && (
          <a className="btn btn-primary" href={`${API_BASE_URL}${proof.download_url}`} target="_blank" rel="noreferrer">
            {t.publicVerify.downloadButton}
          </a>
        )}
        <Link className="btn btn-secondary" href="/">
          {t.publicVerify.newProof}
        </Link>
      </div>
    </section>
  );
}

