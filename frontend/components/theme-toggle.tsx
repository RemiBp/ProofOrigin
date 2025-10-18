"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "prooforigin-theme";

type Theme = "light" | "dark";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const stored = (window.localStorage.getItem(STORAGE_KEY) as Theme | null) ?? undefined;
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial = stored ?? (prefersDark ? "dark" : "light");
    applyTheme(initial);
    setTheme(initial);
  }, []);

  const applyTheme = (nextTheme: Theme) => {
    document.body.setAttribute("data-theme", nextTheme === "dark" ? "dark" : "light");
    window.localStorage.setItem(STORAGE_KEY, nextTheme);
  };

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
  };

  return (
    <button className="btn btn-secondary" onClick={toggle} aria-label="Basculer le thème">
      {theme === "dark" ? "🌙 Mode nuit" : "☀️ Mode jour"}
    </button>
  );
}
