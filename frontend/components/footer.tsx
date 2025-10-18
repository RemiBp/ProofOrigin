import Link from "next/link";

export function Footer() {
  return (
    <footer>
      <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
        <Link href="/pricing">Tarifs</Link>
        <Link href="/dashboard">Dashboard</Link>
        <a href="https://docs.prooforigin.com" target="_blank" rel="noreferrer">
          Documentation API
        </a>
      </div>
      <p style={{ marginTop: "1rem", fontSize: "0.85rem" }}>© {new Date().getFullYear()} ProofOrigin. Toutes preuves, un seul hub.</p>
    </footer>
  );
}
