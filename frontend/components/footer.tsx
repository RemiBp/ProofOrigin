"use client";

import Link from "next/link";

import { useTranslations } from "./i18n/language-provider";

export function Footer() {
  const t = useTranslations();
  const year = new Date().getFullYear().toString();
  return (
    <footer>
      <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
        <Link href="/pricing">{t.footer.pricing}</Link>
        <Link href="/dashboard">{t.footer.dashboard}</Link>
        <a href="https://docs.prooforigin.com" target="_blank" rel="noreferrer">
          {t.nav.docs}
        </a>
      </div>
      <p style={{ marginTop: "1rem", fontSize: "0.85rem" }}>{t.footer.tagline.replace("{{year}}", year)}</p>
    </footer>
  );
}
