import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";

export const metadata: Metadata = {
  title: "Impressum – Ratslotse",
  description: "Anbieterkennzeichnung und Kontakt für Ratslotse.",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border pt-6">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <div className="mt-2 space-y-2 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export default function ImpressumPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
          <Link href="/" className="flex items-center gap-2"><BrandMark /><span className="font-semibold text-foreground">Ratslotse</span></Link>
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">Anmelden →</Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Impressum</h1>

        <div className="mt-6 space-y-6">
          <Section title="Angaben gemäß § 5 DDG">
            <p>
              Tim Sigl<br />
              Krusenweg 26<br />
              26135 Oldenburg<br />
              Deutschland
            </p>
          </Section>

          <Section title="Kontakt">
            <p>
              E-Mail:{" "}
              <a href="mailto:ratslotse@timsigl.de" className="text-primary hover:underline">ratslotse@timsigl.de</a>
            </p>
          </Section>

          <Section title="Inhaltlich verantwortlich gemäß § 18 Abs. 2 MStV">
            <p>Tim Sigl (Anschrift wie oben).</p>
          </Section>

          <Section title="Haftung für Inhalte">
            <p>
              Die Inhalte dieser Seiten wurden mit größter Sorgfalt erstellt; für Richtigkeit, Vollständigkeit und
              Aktualität kann jedoch keine Gewähr übernommen werden. Ratslotse bereitet öffentlich zugängliche
              Informationen aus dem Ratsinformationssystem der Stadt Oldenburg automatisiert auf — maßgeblich sind
              stets die amtlichen Originaldokumente. Als Diensteanbieter bin ich gemäß § 7 Abs. 1 DDG für eigene
              Inhalte nach den allgemeinen Gesetzen verantwortlich.
            </p>
          </Section>

          <Section title="Haftung für Links">
            <p>
              Diese Seite enthält Links zu externen Websites Dritter, auf deren Inhalte ich keinen Einfluss habe.
              Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter verantwortlich.
            </p>
          </Section>

          <Section title="Urheberrecht">
            <p>
              Die durch den Seitenbetreiber erstellten Inhalte unterliegen dem deutschen Urheberrecht. Inhalte und
              Rechte Dritter (z. B. Presseartikel) sind als solche gekennzeichnet und verbleiben bei deren Inhabern.
            </p>
          </Section>
        </div>

        <footer className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          <Link href="/datenschutz" className="text-primary hover:underline">Datenschutzerklärung</Link>
          {" · "}
          <Link href="/" className="hover:text-foreground">Startseite</Link>
        </footer>
      </main>
    </div>
  );
}
