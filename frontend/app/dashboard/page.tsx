"use client";

import { UsagePanel } from "../../components/dashboard/usage-panel";
import { useTranslations } from "../../components/i18n/language-provider";

export default function DashboardPage() {
  const t = useTranslations();
  return (
    <section className="glass-card" style={{ gap: "2rem" }}>
      <header>
        <h1 style={{ margin: 0, fontSize: "2.4rem" }}>{t.dashboard.heading}</h1>
        <p style={{ margin: 0, color: "var(--primary)" }}>{t.dashboard.subheading}</p>
import { UsagePanel } from "../../components/dashboard/usage-panel";

export default function DashboardPage() {
  return (
    <section className="glass-card" style={{ gap: "2rem" }}>
      <header>
        <h1 style={{ margin: 0, fontSize: "2.4rem" }}>Dashboard ProofOrigin</h1>
        <p style={{ margin: 0, color: "var(--primary)" }}>
          Consultez vos preuves, quotas API et générez des sessions de paiement Stripe pour upgrader instantanément.
        </p>
      </header>
      <UsagePanel />
    </section>
  );
}
