import Link from "next/link";

const plans = [
  {
    name: "Free",
    price: "0 €",
    description: "100 preuves par mois, idéal pour démarrer.",
    features: [
      "100 preuves/mois",
      "Limite 30 requêtes/min",
      "Certificats PDF et badges",
    ],
    value: "free",
  },
  {
    name: "Pro",
    price: "79 €",
    description: "Pour les studios créatifs et équipes marketing.",
    features: [
      "10 000 preuves/mois",
      "Support webhook prioritaire",
      "API batch et AI Proof inclus",
    ],
    highlight: true,
    value: "pro",
  },
  {
    name: "Business",
    price: "199 €",
    description: "Pour les plateformes IA et entreprises globales.",
    features: [
      "100 000 preuves/mois",
      "SLA 99.9% et support dédié",
      "Badge dynamique personnalisable",
    ],
    value: "business",
  },
];

export default function PricingPage() {
  return (
    <section className="glass-card" style={{ gap: "2rem" }}>
      <header>
        <h1 style={{ margin: 0, fontSize: "2.6rem" }}>Plans & Tarification</h1>
        <p style={{ margin: 0, color: "var(--primary)" }}>
          Choisissez le plan adapté à votre flux et générez la session Stripe directement depuis le dashboard.
        </p>
      </header>
      <div className="grid grid-two">
        {plans.map((plan) => (
          <article key={plan.name} className="glass-card" style={{ borderWidth: plan.highlight ? 2 : 1, borderColor: plan.highlight ? "var(--primary)" : undefined }}>
            <h2 style={{ margin: 0 }}>{plan.name}</h2>
            <p style={{ margin: "0.25rem 0", fontSize: "2rem", fontWeight: 700 }}>{plan.price} / mois</p>
            <p style={{ marginTop: 0 }}>{plan.description}</p>
            <ul>
              {plan.features.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
            <Link className="btn btn-primary" href={`/dashboard?plan=${plan.value}`}>
              Choisir ce plan
            </Link>
          </article>
        ))}
      </div>
      <div className="cta-banner">
        <h3 style={{ margin: 0 }}>Besoin d’un onboarding assisté ?</h3>
        <p style={{ margin: 0 }}>Contactez notre équipe pour connecter votre bucket S3, configurer Stripe et automatiser vos webhooks.</p>
        <a className="btn btn-secondary" href="mailto:hello@prooforigin.com">
          Contacter un expert
        </a>
      </div>
    </section>
  );
}
