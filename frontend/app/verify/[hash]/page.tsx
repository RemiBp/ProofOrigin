import Link from "next/link";
import { API_BASE_URL } from "../../../lib/config";

export const dynamic = "force-dynamic";

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

async function getStatus(hash: string): Promise<PublicProofStatus | null> {
  const response = await fetch(`${API_BASE_URL}/verify/${encodeURIComponent(hash)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as PublicProofStatus;
}

interface Props {
  params: { hash: string };
}

export default async function VerifyPage({ params }: Props) {
  const status = await getStatus(params.hash);

  if (!status) {
    return (
      <section className="glass-card">
        <h1>Preuve introuvable</h1>
        <p>Impossible de charger le statut pour le hash {params.hash}.</p>
        <Link className="btn btn-secondary" href="/">
          Revenir à l’accueil
        </Link>
      </section>
    );
  }

  return (
    <>
      <section className="glass-card">
        <h1 style={{ margin: 0 }}>Statut de la preuve</h1>
        <p style={{ margin: 0 }}>Hash : {status.hash}</p>
        <p style={{ margin: 0 }}>Statut : {status.status === "verified" ? "✅ Vérifiée" : "❌ Non enregistrée"}</p>
        {status.created_at && <p>Date de création : {new Date(status.created_at).toLocaleString()}</p>}
        {status.owner && (
          <p>
            Propriétaire : {status.owner.display_name ?? status.owner.email ?? status.owner.id}
          </p>
        )}
        {status.anchored && status.blockchain_tx && (
          <a href={`https://polygonscan.com/tx/${status.blockchain_tx}`} target="_blank" rel="noreferrer">
            Voir l’ancrage blockchain
          </a>
        )}
        {status.download_url && (
          <a className="btn btn-primary" href={`${API_BASE_URL}${status.download_url}`} target="_blank" rel="noreferrer">
            Télécharger le certificat PDF
          </a>
        )}
        <Link className="btn btn-secondary" href="/">
          Générer une nouvelle preuve
        </Link>
      </section>
    </>
  );
}
