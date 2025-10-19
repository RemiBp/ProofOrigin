"use client";

import { useEffect, useState } from "react";

import { useTranslations } from "../../components/i18n/language-provider";
import { API_BASE_URL } from "../../lib/config";

export default function PricingPage() {
  const t = useTranslations();
  const [token, setToken] = useState("");
  const [remember, setRemember] = useState(true);
  const [status, setStatus] = useState("");
  const [checkoutUrl, setCheckoutUrl] = useState("");
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedToken = window.localStorage.getItem("prooforigin.billing.token");
    if (storedToken) {
      setToken(storedToken);
    }
    const storedRemember = window.localStorage.getItem("prooforigin.billing.remember");
    if (storedRemember) {
      setRemember(storedRemember === "true");
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (remember && token) {
      window.localStorage.setItem("prooforigin.billing.token", token);
    } else {
      window.localStorage.removeItem("prooforigin.billing.token");
    }
    window.localStorage.setItem("prooforigin.billing.remember", String(remember));
  }, [remember, token]);

  useEffect(() => {
    setStatus("");
    setCheckoutUrl("");
  }, [token]);

  const launchCheckout = async (plan: string) => {
    if (!token) {
      setStatus(t.pricing.statusNeedToken);
      return;
    }
    setLoadingPlan(plan);
    setStatus(t.pricing.statusLoading);
    setCheckoutUrl("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/buy-credits`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan }),
      });
      if (!response.ok) {
        let message = `${response.status}`;
        try {
          const payload = await response.json();
          if (payload.detail) message = payload.detail;
        } catch (error) {
          const fallback = await response.text();
          if (fallback) message = fallback;
        }
        throw new Error(message);
      }
      const result = await response.json();
      setCheckoutUrl(result.checkout_url);
      setStatus(t.pricing.statusReady.replace("{{plan}}", String(result.plan ?? plan).toUpperCase()));
    } catch (error) {
      setStatus(t.pricing.statusError.replace("{{message}}", (error as Error).message));
    } finally {
      setLoadingPlan(null);
    }
  };

  return (
    <section className="glass-card" style={{ gap: "2rem" }}>
      <header>
        <h1 style={{ margin: 0, fontSize: "2.6rem" }}>{t.pricing.heading}</h1>
        <p style={{ margin: 0, color: "var(--primary)" }}>{t.pricing.subheading}</p>
      </header>
      <div className="glass-card" style={{ gap: "1rem" }}>
        <label>
          <span>{t.pricing.tokenLabel}</span>
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder={t.pricing.tokenPlaceholder}
          />
        </label>
        <label className="remember-toggle">
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          <span>{t.pricing.rememberToken}</span>
        </label>
        <p className="helper-text">{t.pricing.helper}</p>
      </div>
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
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => launchCheckout(plan.value)}
              disabled={loadingPlan === plan.value}
            >
              {loadingPlan === plan.value ? "…" : t.pricing.actionCheckout}
            </button>
          </article>
        ))}
      </div>
      {status && <p>{status}</p>}
      {checkoutUrl && (
        <a className="btn btn-secondary" href={checkoutUrl} target="_blank" rel="noreferrer">
          {t.pricing.openCheckout}
        </a>
      )}
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
