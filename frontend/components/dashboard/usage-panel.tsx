"use client";

import { FormEvent, useCallback, useState } from "react";
import useSWR from "swr";

import { API_BASE_URL } from "../../lib/config";
import { useTranslations } from "../i18n/language-provider";
import { FormEvent, useState } from "react";
import useSWR from "swr";
import { API_BASE_URL } from "../../lib/config";

interface UsageResponse {
  proofs_generated: number;
  verifications_performed: number;
  remaining_credits: number;
  last_payment?: string | null;
  next_anchor_batch?: string | null;
  plan: string;
  rate_limit_per_minute: number;
  monthly_quota: number;
}

const fetcher = async (key: string, apiKey: string) => {
  const response = await fetch(key, {
    headers: {
      "X-API-Key": apiKey,
    },
  });
  if (!response.ok) {
    throw new Error(`Erreur ${response.status}`);
  }
  return (await response.json()) as UsageResponse;
};

export function UsagePanel() {
  const [apiKey, setApiKey] = useState("");
  const [token, setToken] = useState("");
  const [selectedPlan, setSelectedPlan] = useState("pro");
  const [checkoutUrl, setCheckoutUrl] = useState<string>("");
  const [checkoutStatus, setCheckoutStatus] = useState<string>("");
  const t = useTranslations();

  const fetcher = useCallback(async (url: string, key: string) => {
    const response = await fetch(url, {
      headers: {
        "X-API-Key": key,
      },
    });
    if (!response.ok) {
      throw new Error(String(response.status));
    }
    return (await response.json()) as UsageResponse;
  }, []);

  const { data, error, mutate, isLoading } = useSWR(
    apiKey ? [`${API_BASE_URL}/api/v1/usage`, apiKey] : null,
    ([url, key]) => fetcher(url, key),
    { revalidateOnFocus: false }
  );

  const requestCheckout = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) {
      setCheckoutStatus(t.dashboard.checkoutNeedToken);
      return;
    }
    setCheckoutStatus(t.dashboard.checkoutLoading);
      setCheckoutStatus("Fournissez un jeton d’accès JWT");
      return;
    }
    setCheckoutStatus("Génération de la session Stripe en cours…");
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/buy-credits`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan: selectedPlan }),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || String(response.status));
      }
      const result = await response.json();
      setCheckoutUrl(result.checkout_url);
      setCheckoutStatus(t.dashboard.checkoutReady.replace("{{plan}}", result.plan.toUpperCase()));
    } catch (error) {
      setCheckoutStatus(t.dashboard.checkoutError.replace("{{message}}", (error as Error).message));
        throw new Error(`Erreur ${response.status}`);
      }
      const result = await response.json();
      setCheckoutUrl(result.checkout_url);
      setCheckoutStatus(`Session prête pour le plan ${result.plan.toUpperCase()}`);
    } catch (error) {
      setCheckoutStatus(`Impossible de créer la session : ${(error as Error).message}`);
    }
  };

  return (
    <div className="glass-card">
      <div className="section-heading">
        <div>
          <h2 style={{ margin: 0 }}>{t.dashboard.usageTitle}</h2>
          <p style={{ marginTop: "0.25rem", color: "var(--primary)" }}>{t.dashboard.usageSubtitle}</p>
        </div>
      </div>
      <form
        className="grid"
        onSubmit={(event) => {
          event.preventDefault();
          mutate();
        }}
      >
        <label>
          <span>{t.dashboard.syncLabel}</span>
          <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="pk_live_..." required />
        </label>
        <button className="btn btn-primary" type="submit" disabled={!apiKey}>
          {isLoading ? "…" : t.dashboard.syncButton}
        </button>
      </form>
      {error && <p>{t.dashboard.usageError.replace("{{message}}", error.message)}</p>}
      {data && (
        <div style={{ display: "grid", gap: "0.6rem" }}>
          <p style={{ margin: 0 }}>
            {t.dashboard.planLabel} <strong>{data.plan.toUpperCase()}</strong>
          </p>
          <p style={{ margin: 0 }}>
            {t.dashboard.proofsLabel} {data.proofs_generated}
          </p>
          <p style={{ margin: 0 }}>
            {t.dashboard.verificationsLabel} {data.verifications_performed}
          </p>
          <p style={{ margin: 0 }}>
            {t.dashboard.creditsLabel} {data.remaining_credits}
          </p>
          <p style={{ margin: 0 }}>
            {t.dashboard.rateLabel} {data.rate_limit_per_minute}
          </p>
          <p style={{ margin: 0 }}>
            {t.dashboard.quotaLabel} {data.monthly_quota}
          </p>
          {data.last_payment && (
            <p style={{ margin: 0 }}>
              {t.dashboard.lastPaymentLabel} {new Date(data.last_payment).toLocaleString()}
            </p>
          )}
          {data.next_anchor_batch && (
            <p style={{ margin: 0 }}>
              {t.dashboard.nextBatchLabel} {new Date(data.next_anchor_batch).toLocaleString()}
            </p>
          )}
          <h2 style={{ margin: 0 }}>Suivi d’usage API</h2>
          <p style={{ marginTop: "0.25rem", color: "var(--primary)" }}>Rafraîchissez vos quotas et lancez un upgrade de plan.</p>
        </div>
      </div>
      <form className="grid" onSubmit={(event) => {
        event.preventDefault();
        mutate();
      }}>
        <label>
          <span>Clé API</span>
          <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="pk_live_..." required />
        </label>
        <button className="btn btn-primary" type="submit" disabled={!apiKey}>
          {isLoading ? "Chargement…" : "Synchroniser"}
        </button>
      </form>
      {error && <p>Erreur lors du chargement : {error.message}</p>}
      {data && (
        <div style={{ display: "grid", gap: "0.6rem" }}>
          <p style={{ margin: 0 }}>Plan : <strong>{data.plan.toUpperCase()}</strong></p>
          <p style={{ margin: 0 }}>Preuves générées : {data.proofs_generated}</p>
          <p style={{ margin: 0 }}>Vérifications effectuées : {data.verifications_performed}</p>
          <p style={{ margin: 0 }}>Crédits restants : {data.remaining_credits}</p>
          <p style={{ margin: 0 }}>Limite / minute : {data.rate_limit_per_minute}</p>
          <p style={{ margin: 0 }}>Quota mensuel : {data.monthly_quota}</p>
          {data.last_payment && <p style={{ margin: 0 }}>Dernier paiement : {new Date(data.last_payment).toLocaleString()}</p>}
          {data.next_anchor_batch && <p style={{ margin: 0 }}>Prochain lot blockchain : {new Date(data.next_anchor_batch).toLocaleString()}</p>}
        </div>
      )}
      <form className="grid" onSubmit={requestCheckout}>
        <label>
          <span>{t.dashboard.checkoutTokenLabel}</span>
          <input value={token} onChange={(event) => setToken(event.target.value)} placeholder="eyJhbGciOiJI…" />
        </label>
        <label>
          <span>{t.dashboard.checkoutPlanLabel}</span>
          <select value={selectedPlan} onChange={(event) => setSelectedPlan(event.target.value)}>
            <option value="free">{t.dashboard.planOptions.free}</option>
            <option value="pro">{t.dashboard.planOptions.pro}</option>
            <option value="business">{t.dashboard.planOptions.business}</option>
          </select>
        </label>
        <button className="btn btn-secondary" type="submit">
          {t.dashboard.checkoutButton}
          <span>Jeton d’accès (Bearer)</span>
          <input value={token} onChange={(event) => setToken(event.target.value)} placeholder="eyJhbGciOiJI…" />
        </label>
        <label>
          <span>Plan cible</span>
          <select value={selectedPlan} onChange={(event) => setSelectedPlan(event.target.value)}>
            <option value="free">Free</option>
            <option value="pro">Pro</option>
            <option value="business">Business</option>
          </select>
        </label>
        <button className="btn btn-secondary" type="submit">
          Générer une session Stripe
        </button>
      </form>
      {checkoutStatus && <p>{checkoutStatus}</p>}
      {checkoutUrl && (
        <a className="btn btn-primary" href={checkoutUrl} target="_blank" rel="noreferrer">
          {t.dashboard.checkoutOpen}
          Ouvrir la session de paiement
        </a>
      )}
    </div>
  );
}

