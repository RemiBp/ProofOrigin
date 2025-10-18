"use client";

import Link from "next/link";

import { useTranslations } from "../../components/i18n/language-provider";

export default function PricingPage() {
  const t = useTranslations();
  return (
    <section className="glass-card" style={{ gap: "2rem" }}>
      <header>
        <h1 style={{ margin: 0, fontSize: "2.6rem" }}>{t.pricing.heading}</h1>
        <p style={{ margin: 0, color: "var(--primary)" }}>{t.pricing.subheading}</p>
      </header>
      <div className="grid grid-two">
        {t.pricing.plans.map((plan) => (
          <article
            key={plan.name}
            className="glass-card"
            style={{ borderWidth: plan.highlight ? 2 : 1, borderColor: plan.highlight ? "var(--primary)" : undefined }}
          >
            <h2 style={{ margin: 0 }}>{plan.name}</h2>
            <p style={{ margin: "0.25rem 0", fontSize: "2rem", fontWeight: 700 }}>
              {plan.price} {t.pricing.priceSuffix}
            </p>
            <p style={{ marginTop: 0 }}>{plan.description}</p>
            <ul>
              {plan.features.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
            <Link className="btn btn-primary" href={`/dashboard?plan=${plan.value}`}>
              {t.pricing.choosePlan}
            </Link>
          </article>
        ))}
      </div>
      <div className="cta-banner">
        <h3 style={{ margin: 0 }}>{t.pricing.contactTitle}</h3>
        <p style={{ margin: 0 }}>{t.pricing.contactDescription}</p>
        <a className="btn btn-secondary" href="mailto:hello@prooforigin.com">
          {t.pricing.contactButton}
        </a>
      </div>
    </section>
  );
}
