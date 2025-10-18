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
}

interface Props {
  params: { hash: string };
}

export default function VerifyPage({ params }: Props) {
  const [proof, setProof] = useState<PublicProofStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
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
      {proof.created_at && <p>{t.publicVerify.createdAt} {new Date(proof.created_at).toLocaleString()}</p>}
      {proof.owner && (
        <p>
          {t.publicVerify.owner} {proof.owner.display_name ?? proof.owner.email ?? proof.owner.id}
        </p>
      )}
      {proof.anchored && proof.blockchain_tx && (
        <a href={`https://polygonscan.com/tx/${proof.blockchain_tx}`} target="_blank" rel="noreferrer">
          {t.publicVerify.anchorLink}
        </a>
      )}
      {proof.download_url && (
        <a className="btn btn-primary" href={`${API_BASE_URL}${proof.download_url}`} target="_blank" rel="noreferrer">
          {t.publicVerify.downloadButton}
        </a>
      )}
      <Link className="btn btn-secondary" href="/">
        {t.publicVerify.newProof}
      </Link>
    </section>
  );
}

