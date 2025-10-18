"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

type Language = "fr" | "en";

const STORAGE_KEY = "prooforigin-language";

const translations = {
  fr: {
    nav: {
      pricing: "Tarifs",
      dashboard: "Dashboard",
      docs: "Documentation API",
    },
    language: {
      switchToEnglish: "Passer en anglais",
      switchToFrench: "Passer en français",
      indicatorFrench: "🇫🇷 FR",
      indicatorEnglish: "🇬🇧 EN",
    },
    theme: {
      light: "☀️ Mode jour",
      dark: "🌙 Mode nuit",
    },
    home: {
      heroBadge: "Proof-as-a-Service",
      heroTitle: "Le passeport infalsifiable de vos créations.",
      heroSubtitle:
        "ProofOrigin combine hashing SHA-256, signatures Ed25519, ancrage blockchain et horodatage OpenTimestamps pour délivrer des certificats PDF vérifiables à l’échelle mondiale. Upload unique, API batch ou intégration IA : tout est prêt.",
      ctaUpload: "Déposer une création",
      ctaPricing: "Découvrir les plans",
      ctaDocs: "Documentation API",
      featureAnchorTitle: "Ancrage blockchain",
      featureAnchorDescription: "Polygon, Base, Arbitrum & OpenTimestamps, orchestrés automatiquement.",
      featureSdkTitle: "Webhooks & SDK",
      featureSdkDescription: "Recevez les preuves en push et intégrez nos SDK Python & Node en quelques lignes.",
      integrationHeading: "Connectez ProofOrigin à votre stack",
      integrationBadge: "API REST / OAuth2 / Webhooks",
      oauthTitle: "OAuth2 + JWT",
      oauthDescription:
        "Connexion rapide via Google, GitHub ou Auth0. Les tokens JWT sécurisent vos requêtes serveur à serveur.",
      oauthBullets: [
        "Rotation de clés Ed25519 chiffrées côté serveur",
        "Gestion de comptes multi-équipes et rôles",
        "API keys illimitées avec quotas par plan",
      ],
      aiTitle: "Proof for AI",
      aiDescription:
        "Endpoint /api/v1/ai/proof pour certifier vos générations IA (model_name, prompt, timestamp).",
      aiBullets: [
        "Webhook de retour pour Runway, Midjourney, StableDiffusion",
        "Badges dynamiques « ProofOrigin Certified »",
        "Batch processing jusqu’à 10 000 contenus",
      ],
      ctaBannerTitle: "Prêt à passer en production ?",
      ctaBannerDescription:
        "Déployez sur Render grâce au blueprint fourni et suivez vos preuves depuis le dashboard Next.js.",
      ctaBannerButton: "Ouvrir le dashboard",
    },
    upload: {
      heading: "Uploader et certifier en direct",
      subheading: "Hash SHA-256, signature Ed25519 et certificat PDF instantané.",
      apiKeyLabel: "Clé API (X-API-Key)",
      keyPasswordLabel: "Mot de passe de clé",
      textLabel: "Texte à certifier",
      textPlaceholder: "Collez ici une description, un prompt IA, un script…",
      fileLabel: "Fichier (optionnel)",
      submit: "Certifier maintenant",
      submitting: "Génération…",
      compatibilityBadge: "Compatible Polygon · Base · OpenTimestamps",
      statusMissingApiKey: "Merci de renseigner votre clé API X-API-Key.",
      statusMissingKeyPassword: "Votre mot de passe de clé privée est requis.",
      statusMissingPayload: "Ajoutez un fichier ou un texte à certifier.",
      statusLoading: "Génération de la preuve en cours…",
      statusSuccess: "Preuve générée avec succès. Vous pouvez télécharger le certificat.",
      statusError: "Impossible de générer la preuve : {{message}}",
      proofHeading: "Preuve #",
      hashLabel: "Hash :",
      createdAtLabel: "Créée le :",
      anchorLink: "Voir l’ancrage blockchain",
      anchorPending: "En attente d’ancrage blockchain…",
      verifyButton: "Vérifier publiquement",
      downloadButton: "Télécharger le certificat PDF",
    },
    verify: {
      heading: "Vérification publique instantanée",
      subheading: "Consultez le statut, la date et téléchargez le certificat.",
      hashLabel: "Hash (SHA-256)",
      hashPlaceholder: "0x…",
      submit: "Vérifier",
      submitting: "Recherche…",
      statusPrompt: "Indiquez un hash à contrôler",
      statusLoading: "Contrôle en cours…",
      statusVerified: "Preuve trouvée",
      statusMissing: "Hash inconnu",
      statusError: "Erreur : {{message}}",
      resultStatusLabel: "Statut :",
      resultVerified: "✅ Validé",
      resultMissing: "❌ Inconnu",
      resultCreatedAt: "Créé le :",
      resultOwner: "Propriétaire :",
      anchorLink: "Voir la transaction blockchain",
      downloadButton: "Télécharger le certificat PDF",
    },
    dashboard: {
      heading: "Dashboard ProofOrigin",
      subheading:
        "Consultez vos preuves, quotas API et générez des sessions de paiement Stripe pour upgrader instantanément.",
      usageTitle: "Suivi d’usage API",
      usageSubtitle: "Rafraîchissez vos quotas et lancez un upgrade de plan.",
      syncLabel: "Clé API",
      syncButton: "Synchroniser",
      checkoutTokenLabel: "Jeton d’accès (Bearer)",
      checkoutPlanLabel: "Plan cible",
      checkoutButton: "Générer une session Stripe",
      checkoutOpen: "Ouvrir la session de paiement",
      checkoutNeedToken: "Fournissez un jeton d’accès JWT",
      checkoutLoading: "Génération de la session Stripe en cours…",
      checkoutReady: "Session prête pour le plan {{plan}}",
      checkoutError: "Impossible de créer la session : {{message}}",
      usageError: "Erreur lors du chargement : {{message}}",
      planLabel: "Plan :",
      proofsLabel: "Preuves générées :",
      verificationsLabel: "Vérifications effectuées :",
      creditsLabel: "Crédits restants :",
      rateLabel: "Limite / minute :",
      quotaLabel: "Quota mensuel :",
      lastPaymentLabel: "Dernier paiement :",
      nextBatchLabel: "Prochain lot blockchain :",
      planOptions: {
        free: "Free",
        pro: "Pro",
        business: "Business",
      },
    },
    pricing: {
      heading: "Plans & Tarification",
      subheading:
        "Choisissez le plan adapté à votre flux et générez la session Stripe directement depuis le dashboard.",
      priceSuffix: "/ mois",
      plans: [
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
          value: "pro",
          highlight: true,
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
      ],
      choosePlan: "Choisir ce plan",
      contactTitle: "Besoin d’un onboarding assisté ?",
      contactDescription:
        "Contactez notre équipe pour connecter votre bucket S3, configurer Stripe et automatiser vos webhooks.",
      contactButton: "Contacter un expert",
    },
    publicVerify: {
      notFoundTitle: "Preuve introuvable",
      notFoundDescription: "Impossible de charger le statut pour le hash {{hash}}.",
      backHome: "Revenir à l’accueil",
      loading: "Chargement du statut…",
      heading: "Statut de la preuve",
      hashLabel: "Hash :",
      statusLabel: "Statut :",
      statusVerified: "✅ Vérifiée",
      statusMissing: "❌ Non enregistrée",
      createdAt: "Date de création :",
      owner: "Propriétaire :",
      anchorLink: "Voir l’ancrage blockchain",
      anchorHeading: "Ancrages & registres",
      anchorPending: "Ancrage en cours, revenez dans un instant pour voir la transaction.",
      downloadButton: "Télécharger le certificat PDF",
      newProof: "Générer une nouvelle preuve",
      summary: "Synthèse",
      riskLabel: "Indice de risque",
      zeroTrustHeading: "Vérification hors-ligne",
      zeroTrustDescription:
        "Recalculez le hash localement, comparez-le au ledger et au manifest C2PA sans connexion.",
      zeroTrustUpload: "Déposer un fichier pour vérifier",
      zeroTrustVerifying: "Analyse cryptographique en cours…",
      zeroTrustComputed: "Hash recalculé :",
      zeroTrustLedger: "Ledger : ",
      zeroTrustManifest: "Manifest C2PA : ",
      zeroTrustOk: "✅ Conforme",
      zeroTrustKo: "⚠️ Divergent",
      zeroTrustNA: "N/A",
      zeroTrustUnavailable: "Module de vérification hors-ligne indisponible.",
      receiptsHeading: "Reçus & ancres",
    },
    footer: {
      pricing: "Tarifs",
      dashboard: "Dashboard",
      docs: "Documentation API",
      tagline: "© {{year}} ProofOrigin. Toutes preuves, un seul hub.",
    },
  },
  en: {
    nav: {
      pricing: "Pricing",
      dashboard: "Dashboard",
      docs: "API Docs",
    },
    language: {
      switchToEnglish: "Switch to English",
      switchToFrench: "Basculer en français",
      indicatorFrench: "🇫🇷 FR",
      indicatorEnglish: "🇬🇧 EN",
    },
    theme: {
      light: "☀️ Light mode",
      dark: "🌙 Dark mode",
    },
    home: {
      heroBadge: "Proof-as-a-Service",
      heroTitle: "The tamper-proof passport for your creations.",
      heroSubtitle:
        "ProofOrigin combines SHA-256 hashing, Ed25519 signatures, blockchain anchoring, and OpenTimestamps to deliver PDF certificates that can be verified worldwide. One-click upload, batch API, or AI integration: everything is ready.",
      ctaUpload: "Submit a creation",
      ctaPricing: "Explore plans",
      ctaDocs: "API Documentation",
      featureAnchorTitle: "Blockchain anchoring",
      featureAnchorDescription: "Polygon, Base, Arbitrum & OpenTimestamps orchestrated automatically.",
      featureSdkTitle: "Webhooks & SDK",
      featureSdkDescription: "Receive proofs via push and integrate our Python & Node SDKs in a few lines.",
      integrationHeading: "Connect ProofOrigin to your stack",
      integrationBadge: "REST API / OAuth2 / Webhooks",
      oauthTitle: "OAuth2 + JWT",
      oauthDescription:
        "Fast onboarding with Google, GitHub, or Auth0. JWT tokens secure your server-to-server requests.",
      oauthBullets: [
        "Server-side encrypted Ed25519 key rotation",
        "Multi-team account management and roles",
        "Unlimited API keys with plan-based quotas",
      ],
      aiTitle: "Proof for AI",
      aiDescription:
        "Endpoint /api/v1/ai/proof to certify your AI generations (model_name, prompt, timestamp).",
      aiBullets: [
        "Webhook callbacks for Runway, Midjourney, StableDiffusion",
        "Dynamic “ProofOrigin Certified” badges",
        "Batch processing up to 10,000 assets",
      ],
      ctaBannerTitle: "Ready to ship to production?",
      ctaBannerDescription:
        "Deploy on Render with the provided blueprint and track your proofs from the Next.js dashboard.",
      ctaBannerButton: "Open the dashboard",
    },
    upload: {
      heading: "Upload and certify instantly",
      subheading: "SHA-256 hash, Ed25519 signature, and PDF certificate in seconds.",
      apiKeyLabel: "API Key (X-API-Key)",
      keyPasswordLabel: "Key password",
      textLabel: "Text to certify",
      textPlaceholder: "Paste a description, AI prompt, script…",
      fileLabel: "File (optional)",
      submit: "Certify now",
      submitting: "Generating…",
      compatibilityBadge: "Polygon · Base · OpenTimestamps ready",
      statusMissingApiKey: "Please provide your X-API-Key.",
      statusMissingKeyPassword: "Your private key password is required.",
      statusMissingPayload: "Add a file or some text to certify.",
      statusLoading: "Creating your proof…",
      statusSuccess: "Proof generated successfully. You can download the certificate.",
      statusError: "Unable to generate the proof: {{message}}",
      proofHeading: "Proof #",
      hashLabel: "Hash:",
      createdAtLabel: "Created at:",
      anchorLink: "View blockchain anchoring",
      anchorPending: "Waiting for blockchain anchoring…",
      verifyButton: "Verify publicly",
      downloadButton: "Download PDF certificate",
    },
    verify: {
      heading: "Instant public verification",
      subheading: "Check the status, date, and download the certificate.",
      hashLabel: "Hash (SHA-256)",
      hashPlaceholder: "0x…",
      submit: "Verify",
      submitting: "Searching…",
      statusPrompt: "Provide a hash to inspect",
      statusLoading: "Checking…",
      statusVerified: "Proof found",
      statusMissing: "Unknown hash",
      statusError: "Error: {{message}}",
      resultStatusLabel: "Status:",
      resultVerified: "✅ Valid",
      resultMissing: "❌ Missing",
      resultCreatedAt: "Created at:",
      resultOwner: "Owner:",
      anchorLink: "View blockchain transaction",
      downloadButton: "Download PDF certificate",
    },
    dashboard: {
      heading: "ProofOrigin Dashboard",
      subheading:
        "Review your proofs, API quotas, and spin up Stripe payment sessions to upgrade instantly.",
      usageTitle: "API usage tracking",
      usageSubtitle: "Refresh your quotas and trigger a plan upgrade.",
      syncLabel: "API key",
      syncButton: "Sync",
      checkoutTokenLabel: "Access token (Bearer)",
      checkoutPlanLabel: "Target plan",
      checkoutButton: "Create Stripe session",
      checkoutOpen: "Open payment session",
      checkoutNeedToken: "Provide a JWT access token",
      checkoutLoading: "Generating Stripe session…",
      checkoutReady: "Session ready for plan {{plan}}",
      checkoutError: "Unable to create the session: {{message}}",
      usageError: "Failed to load usage: {{message}}",
      planLabel: "Plan:",
      proofsLabel: "Proofs generated:",
      verificationsLabel: "Verifications performed:",
      creditsLabel: "Credits remaining:",
      rateLabel: "Rate limit / minute:",
      quotaLabel: "Monthly quota:",
      lastPaymentLabel: "Last payment:",
      nextBatchLabel: "Next blockchain batch:",
      planOptions: {
        free: "Free",
        pro: "Pro",
        business: "Business",
      },
    },
    pricing: {
      heading: "Plans & Pricing",
      subheading: "Pick the plan that fits your flow and launch a Stripe session right from the dashboard.",
      priceSuffix: "/ month",
      plans: [
        {
          name: "Free",
          price: "€0",
          description: "100 proofs per month — perfect to get started.",
          features: [
            "100 proofs / month",
            "30 requests / minute limit",
            "PDF certificates and badges",
          ],
          value: "free",
        },
        {
          name: "Pro",
          price: "€79",
          description: "For creative studios and marketing teams.",
          features: [
            "10,000 proofs / month",
            "Priority webhook support",
            "Batch API and AI Proof included",
          ],
          value: "pro",
          highlight: true,
        },
        {
          name: "Business",
          price: "€199",
          description: "For AI platforms and global enterprises.",
          features: [
            "100,000 proofs / month",
            "99.9% SLA with dedicated support",
            "Customizable dynamic badge",
          ],
          value: "business",
        },
      ],
      choosePlan: "Select this plan",
      contactTitle: "Need a guided onboarding?",
      contactDescription:
        "Reach our team to connect your S3 bucket, configure Stripe, and automate your webhooks.",
      contactButton: "Talk to an expert",
    },
    publicVerify: {
      notFoundTitle: "Proof not found",
      notFoundDescription: "Unable to load the status for hash {{hash}}.",
      backHome: "Back to homepage",
      loading: "Loading proof status…",
      heading: "Proof status",
      hashLabel: "Hash:",
      statusLabel: "Status:",
      statusVerified: "✅ Verified",
      statusMissing: "❌ Not recorded",
      createdAt: "Created at:",
      owner: "Owner:",
      anchorLink: "View blockchain anchoring",
      anchorHeading: "Anchors & transparency log",
      anchorPending: "Anchoring still pending. Check back shortly for the transaction hash.",
      downloadButton: "Download PDF certificate",
      newProof: "Generate a new proof",
      summary: "Executive summary",
      riskLabel: "Risk index",
      zeroTrustHeading: "Offline verification",
      zeroTrustDescription:
        "Re-hash the asset locally and reconcile it with the ledger & C2PA manifest directly in your browser.",
      zeroTrustUpload: "Drop a file to verify",
      zeroTrustVerifying: "Crunching cryptography…",
      zeroTrustComputed: "Computed hash:",
      zeroTrustLedger: "Ledger check: ",
      zeroTrustManifest: "C2PA manifest: ",
      zeroTrustOk: "✅ Match",
      zeroTrustKo: "⚠️ Mismatch",
      zeroTrustNA: "N/A",
      zeroTrustUnavailable: "Offline verifier unavailable.",
      receiptsHeading: "Receipts & anchors",
    },
    footer: {
      pricing: "Pricing",
      dashboard: "Dashboard",
      docs: "API Docs",
      tagline: "© {{year}} ProofOrigin. Every proof, one hub.",
    },
  },
} as const;

type TranslationShape = typeof translations["fr"];

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  dictionary: TranslationShape;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window === "undefined") {
      return "fr";
    }
    const stored = window.localStorage.getItem(STORAGE_KEY) as Language | null;
    if (stored === "fr" || stored === "en") {
      return stored;
    }
    return window.navigator.language?.toLowerCase().startsWith("fr") ? "fr" : "en";
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, language);
    }
  }, [language]);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = language;
    }
  }, [language]);

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      dictionary: translations[language],
    }),
    [language]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return { language: context.language, setLanguage: context.setLanguage };
}

export function useTranslations(): TranslationShape {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useTranslations must be used within a LanguageProvider");
  }
  return context.dictionary;
}

