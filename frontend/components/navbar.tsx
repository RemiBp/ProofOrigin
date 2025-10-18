"use client";

import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";
import { LanguageToggle } from "./language-toggle";
import { useTranslations } from "./i18n/language-provider";

export function NavBar() {
  const t = useTranslations();
  return (
    <header style={{ padding: "1.4rem 1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontWeight: 700, fontSize: "1.1rem" }}>
        <span style={{ width: "2.6rem", height: "2.6rem", borderRadius: "20px", background: "linear-gradient(135deg,#6366f1,#22d3ee)", display: "grid", placeItems: "center", color: "#fff", fontWeight: 700 }}>
          PO
        </span>
        <span>ProofOrigin</span>
      </Link>
      <nav style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <Link href="/pricing" className="btn btn-secondary" style={{ paddingInline: "1.2rem" }}>
          {t.nav.pricing}
        </Link>
        <Link href="/dashboard" className="btn btn-secondary" style={{ paddingInline: "1.2rem" }}>
          {t.nav.dashboard}
        </Link>
        <LanguageToggle />
        <ThemeToggle />
      </nav>
    </header>
  );
}
