import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { BackLink } from "@/components/back-link";

export const metadata: Metadata = {
  title: "Erklärung zur Barrierefreiheit – Ratslotse",
  description: "Wie barrierefrei Ratslotse ist, was noch fehlt und wie du Barrieren meldest.",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border pt-6">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <div className="mt-2 space-y-2 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

/**
 * Erklärung zur Barrierefreiheit (Design „App-Store-Release", Abschnitt ⑨).
 *
 * Bewusst eine Selbsteinschätzung und keine Konformitätsbehauptung: Es gab
 * keine externe Prüfung, und eine behauptete WCAG-Konformität wäre schlimmer
 * als eine ehrliche Lückenliste. Der Meldeweg ist der eigentliche Zweck der
 * Seite — er ist billiger als jede Prüfung und bringt echte Befunde.
 */
export default function BarrierefreiheitPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            <BackLink />
            <Link href="/" className="flex items-center gap-2"><BrandMark /><span className="hidden font-semibold text-foreground sm:inline">Ratslotse</span></Link>
          </div>
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">Anmelden →</Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Erklärung zur Barrierefreiheit</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Ratslotse soll für alle nutzbar sein, die wissen wollen, was der Stadtrat beschließt. Diese Erklärung gilt
          für die Website ratslotse.de und die Apps für iOS und Android. Sie ist eine Selbsteinschätzung des
          Betreibers — eine externe Prüfung hat es bisher nicht gegeben.
        </p>

        <div className="mt-6 space-y-6">
          <Section title="Stand">
            <p>
              Angestrebt wird der Standard WCAG 2.2 Stufe AA. Nach eigener Einschätzung ist Ratslotse{" "}
              <strong className="text-foreground">weitgehend konform</strong>: Die im nächsten Abschnitt genannten
              Einschränkungen sind bekannt und nicht behoben. Diese Erklärung wurde am 13. August 2026 erstellt und
              beruht auf einer Selbstbewertung.
            </p>
          </Section>

          <Section title="Was umgesetzt ist">
            <ul className="list-disc space-y-1 pl-5">
              <li>Bedienung vollständig per Tastatur, mit sichtbarem Fokusring auf jedem interaktiven Element und einem „Zum Inhalt springen“-Link.</li>
              <li>Sprache der Seite ausgezeichnet (<code className="rounded bg-muted px-1 py-0.5 text-[13px]">lang=&quot;de&quot;</code>), Überschriften in einer sinnvollen Reihenfolge, Bedienelemente mit Namen für Screenreader.</li>
              <li>Heller und dunkler Modus mit geprüften Kontrasten; Farbe ist nie der einzige Träger einer Information (Ergebnisse tragen zusätzlich Text, Parteien zusätzlich ein Label).</li>
              <li>Bewegungen und Animationen richten sich nach der Systemeinstellung „Bewegung reduzieren“ — die Lotti-Szenen, Aufbau-Animationen und das automatische Scrollen halten dann still.</li>
              <li>Text lässt sich per Browser- bzw. Systemeinstellung vergrößern, ohne dass Inhalte verloren gehen; die Layouts sind auf 320 px Breite ausgelegt.</li>
              <li>Keine Zeitbegrenzung, kein automatisches Abspielen von Ton oder Video, kein Blinken.</li>
            </ul>
          </Section>

          <Section title="Bekannte Einschränkungen">
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <strong>Stadtkarte:</strong> Die Karte ist im Kern eine visuelle Darstellung. Alle Beschlüsse darauf
                sind auch über Suche und Themenlisten ohne Karte erreichbar, die Karte selbst ist aber nur
                eingeschränkt per Tastatur und Screenreader bedienbar.
              </li>
              <li>
                <strong>Diagramme in der Analyse:</strong> Balken- und Verlaufsgrafiken haben eine Textzusammenfassung,
                aber noch keine vollständige Tabellenalternative für jeden Wert.
              </li>
              <li>
                <strong>Amtliche Originaldokumente:</strong> Die verlinkten PDFs stammen aus dem Ratsinformationssystem
                der Stadt Oldenburg. Auf deren Barrierefreiheit habe ich keinen Einfluss; Ratslotse bereitet ihren
                Inhalt aber als Text auf, der ohne PDF readable ist.
              </li>
              <li>
                <strong>KI-Antworten</strong> entstehen automatisch. Sprache und Länge schwanken; eine
                Leichte-Sprache-Fassung gibt es nicht, wohl aber zu jedem Beschluss eine kurze Erklärung in
                Alltagssprache („Lotti erklärt&apos;s einfach“).
              </li>
            </ul>
          </Section>

          <Section title="Barriere melden">
            <p>
              Wenn dir etwas begegnet, das du nicht bedienen oder nicht lesen kannst, schreib mir — mit einem Satz,
              worum es ging und womit du unterwegs warst (Screenreader, Vergrößerung, Tastatur, Gerät). Das ist die
              schnellste Art, diese Seite kürzer zu machen.
            </p>
            <p>
              <a href="mailto:ratslotse@timsigl.de" className="text-primary hover:underline">ratslotse@timsigl.de</a>
              {" · "}
              <Link href="/hilfe" className="text-primary hover:underline">Kontaktformular (ohne Anmeldung)</Link>
              {" · "}
              in der App: Konto → Feedback
            </p>
            <p>Ich antworte in der Regel innerhalb weniger Tage.</p>
          </Section>

          <Section title="Rechtlicher Rahmen">
            <p>
              Ratslotse ist ein privates, nicht-kommerzielles Bürgerprojekt einer Einzelperson und kein Angebot einer
              öffentlichen Stelle. Die Anforderungen des Barrierefreiheitsstärkungsgesetzes (BFSG) richten sich an
              Wirtschaftsakteure und sehen für Kleinstunternehmen Ausnahmen vor; ob und in welchem Umfang sie hier
              greifen, ist nicht abschließend geklärt. Diese Erklärung erscheint deshalb freiwillig — der Anspruch,
              nutzbar zu sein, hängt nicht davon ab, ob ein Gesetz ihn erzwingt.
            </p>
          </Section>
        </div>

        <footer className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          <Link href="/impressum" className="text-primary hover:underline">Impressum</Link>
          {" · "}
          <Link href="/datenschutz" className="text-primary hover:underline">Datenschutz</Link>
          {" · "}
          <Link href="/" className="hover:text-foreground">Startseite</Link>
        </footer>
      </main>
    </div>
  );
}
