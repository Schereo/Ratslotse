import type { Metadata, Viewport } from "next";
import { Inter, Bricolage_Grotesque } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
// Display-Schrift für Überschriften und Wortmarke — gibt der UI ihren Charakter.
const bricolage = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  metadataBase: new URL("https://ratslotse.de"),
  title: "Ratslotse — Oldenburger Ratsinformationen verständlich",
  description:
    "Ratslotse macht die Beschlüsse des Oldenburger Stadtrats durchsuchbar, vergleichbar und verständlich — mit KI-Fragen, Themen-Seiten, Karten und Analysen.",
  applicationName: "Ratslotse",
  manifest: "/manifest.json",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    url: "https://ratslotse.de",
    title: "Ratslotse — Oldenburger Ratsinformationen verständlich",
    description: "Beschlüsse des Oldenburger Stadtrats durchsuchbar, vergleichbar und verständlich.",
  },
  twitter: {
    // Großes Vorschaubild (1200×630) statt Mini-Thumbnail — das Bild selbst
    // kommt per Datei-Konvention aus app/twitter-image.png.
    card: "summary_large_image",
    title: "Ratslotse",
    description: "Oldenburger Ratsinformationen verständlich.",
  },
};

export const viewport: Viewport = {
  // Statusleiste folgt dem System-Farbschema und passt so zur Topbar der App.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f9fb" },
    { media: "(prefers-color-scheme: dark)", color: "#09111b" },
  ],
  width: "device-width",
  initialScale: 1,
  // Extend the page into the iOS safe areas so env(safe-area-inset-*) reports
  // real values — required for the bottom nav to clear the home indicator.
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" className={`${inter.variable} ${bricolage.variable}`} suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
