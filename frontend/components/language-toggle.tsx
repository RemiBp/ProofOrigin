"use client";

import { useLanguage, useTranslations } from "./i18n/language-provider";

export function LanguageToggle() {
  const { language, setLanguage } = useLanguage();
  const t = useTranslations();
  const isFrench = language === "fr";

  const handleToggle = () => {
    setLanguage(isFrench ? "en" : "fr");
  };

  return (
    <button
      className="btn btn-secondary"
      type="button"
      onClick={handleToggle}
      aria-label={isFrench ? t.language.switchToEnglish : t.language.switchToFrench}
    >
      {isFrench ? t.language.indicatorFrench : t.language.indicatorEnglish}
    </button>
  );
}

