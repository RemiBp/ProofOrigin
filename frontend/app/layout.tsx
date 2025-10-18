import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../styles/globals.css";

import { Footer } from "../components/footer";
import { NavBar } from "../components/navbar";
import { LanguageProvider } from "../components/i18n/language-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ProofOrigin · Prouvez l’origine de chaque création",
  description:
    "Certifiez, ancrez et monétisez vos créations avec des preuves blockchain, certificats PDF et API Proof-as-a-Service.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className={inter.className} data-theme="light">
        <LanguageProvider>
          <NavBar />
          <main>{children}</main>
          <Footer />
        </LanguageProvider>
        <NavBar />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
