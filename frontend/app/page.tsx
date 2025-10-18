"use client";

import Link from "next/link";

import { UploadForm } from "../components/upload-form";
import { VerifyWidget } from "../components/verify-widget";
import { useTranslations } from "../components/i18n/language-provider";
import { APP_ORIGIN } from "../lib/config";

export default function HomePage() {
  const t = useTranslations();
  const aiDescription = t.home.aiDescription.replace("Endpoint /api/v1/ai/proof", "").trimStart();
  return (
    <>
      <section className="glass-card" style={{ position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 10% 10%, rgba(99,102,241,0.3), transparent 55%)" }} />
        <div style={{ position: "relative", display: "grid", gap: "1.5rem" }}>
          <span className="badge">{t.home.heroBadge}</span>
          <h1 style={{ fontSize: "3rem", margin: 0 }}>{t.home.heroTitle}</h1>
          <p style={{ maxWidth: "720px", fontSize: "1.1rem", lineHeight: 1.6 }}>{t.home.heroSubtitle}</p>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <Link className="btn btn-primary" href="#upload">
              {t.home.ctaUpload}
            </Link>
            <Link className="btn btn-secondary" href="/pricing">
              {t.home.ctaPricing}
            </Link>
            <a className="btn btn-secondary" href={`${APP_ORIGIN}/docs`} target="_blank" rel="noreferrer">
              {t.home.ctaDocs}
            </a>
          </div>
          <div className="grid grid-two">
            <div>
              <h3 style={{ marginBottom: "0.25rem" }}>{t.home.featureAnchorTitle}</h3>
              <p style={{ margin: 0 }}>{t.home.featureAnchorDescription}</p>
            </div>
            <div>
              <h3 style={{ marginBottom: "0.25rem" }}>{t.home.featureSdkTitle}</h3>
              <p style={{ margin: 0 }}>{t.home.featureSdkDescription}</p>
            </div>
          </div>
        </div>
      </section>
      <UploadForm />
      <VerifyWidget />
      <section className="glass-card">
        <div className="section-heading">
          <h2 style={{ margin: 0 }}>{t.home.integrationHeading}</h2>
          <span className="badge">{t.home.integrationBadge}</span>
        </div>
        <div className="grid grid-two">
          <article>
            <h3>{t.home.oauthTitle}</h3>
            <p>{t.home.oauthDescription}</p>
            <ul>
              {t.home.oauthBullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
          <article>
            <h3>{t.home.aiTitle}</h3>
            <p>
              Endpoint <code>/api/v1/ai/proof</code> {aiDescription}
            </p>
            <ul>
              {t.home.aiBullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </div>
        <div className="cta-banner">
          <h3 style={{ margin: 0 }}>{t.home.ctaBannerTitle}</h3>
          <p style={{ margin: 0 }}>{t.home.ctaBannerDescription}</p>
          <Link className="btn btn-secondary" href="/dashboard">
            {t.home.ctaBannerButton}
          </Link>
        </div>
      </section>
    </>
  );
}
