import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { BackLink } from "@/components/back-link";
import { SupportForm } from "@/components/support-form";

export const metadata: Metadata = {
  title: "Hilfe & Kontakt – Ratslotse",
  description: "Fragen, Fehler oder Probleme mit dem Konto? Hier erreichst du den Ratslotse-Support.",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border pt-6">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <div className="mt-2 space-y-2 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

function Frage({ question, children }: { question: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border/60 pt-4 first:border-t-0 first:pt-0">
      <h3 className="font-semibold text-foreground">{question}</h3>
      <div className="mt-1.5 space-y-2 leading-relaxed text-muted-foreground">{children}</div>
    </div>
  );
}

export default function HilfePage() {
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
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Hilfe &amp; Kontakt</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Ratslotse macht die Arbeit des Oldenburger Stadtrats durchsuchbar und verständlich.
          Wenn etwas klemmt, eine Angabe falsch aussieht oder du eine Frage zu deinem Konto hast:
          Schreib mir. Hinter Ratslotse steckt kein Callcenter, sondern eine Person — dafür
          antwortet die auch selbst.
        </p>

        <div className="mt-8 space-y-8">
          <section>
            <h2 className="text-lg font-semibold text-foreground">Schreib mir</h2>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              Das Formular geht direkt an mich — ein Konto brauchst du dafür nicht.
            </p>
            <div className="mt-4 rounded-2xl border border-border bg-card p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
              <SupportForm />
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              Lieber direkt per Mail?{" "}
              <a href="mailto:ratslotse@timsigl.de" className="text-primary hover:underline">
                ratslotse@timsigl.de
              </a>
            </p>
          </section>

          <Section title="Häufige Fragen">
            <div className="mt-3 space-y-4">
              <Frage question="Ich komme nicht in mein Konto.">
                <p>
                  Über <Link href="/forgot-password" className="text-primary hover:underline">Passwort vergessen</Link>{" "}
                  bekommst du einen Link zum Zurücksetzen an deine Adresse. Kommt keine Mail an, sieh
                  bitte im Spam-Ordner nach — und wenn sie auch dort fehlt, schreib mir oben kurz über
                  das Formular.
                </p>
              </Frage>

              <Frage question="Wie lösche ich mein Konto?">
                <p>
                  In der App und im Browser unter <b>Mein Konto → Konto löschen</b>. Das Konto und alles,
                  was daran hängt — Themen, Benachrichtigungen, gespeicherte Gespräche — werden dabei
                  endgültig entfernt; rückgängig machen lässt sich das nicht. Wenn du nicht mehr in dein
                  Konto kommst, übernehme ich die Löschung auf Anfrage.
                </p>
              </Frage>

              <Frage question="Ich bekomme zu viele (oder keine) Benachrichtigungen.">
                <p>
                  Unter <b>Mein Konto → Benachrichtigungen</b> stellst du ein, ob du per E-Mail, per
                  Push oder gar nicht informiert wirst, und zu welchen Anlässen. Nachts wird ohnehin
                  nichts zugestellt, und es gibt eine Obergrenze pro Tag.
                </p>
              </Frage>

              <Frage question="Eine Angabe stimmt nicht.">
                <p>
                  Ratslotse liest das offizielle Ratsinformationssystem der Stadt Oldenburg aus und
                  fasst es maschinell zusammen. Dabei können Fehler entstehen — maßgeblich ist immer
                  das amtliche Originaldokument, das auf jeder Beschluss-Seite verlinkt ist. Wenn dir
                  etwas auffällt, melde es mir gern: Solche Hinweise sind der schnellste Weg, die
                  Aufbereitung zu verbessern.
                </p>
              </Frage>

              <Frage question="Was kostet Ratslotse?">
                <p>Nichts. Es gibt keine Bezahlfunktionen, keine Abos und keine Werbung.</p>
              </Frage>

              <Frage question="Was passiert mit meinen Daten?">
                <p>
                  Das steht vollständig in der{" "}
                  <Link href="/datenschutz" className="text-primary hover:underline">Datenschutzerklärung</Link>.
                  Kurz: nur, was für den Betrieb nötig ist — kein Weiterverkauf, kein Tracking für Werbung.
                </p>
              </Frage>
            </div>
          </Section>

          <Section title="Wie schnell kommt eine Antwort?">
            <p>
              In der Regel innerhalb von zwei Werktagen. Ratslotse ist ein Feierabendprojekt — am
              Wochenende oder im Urlaub kann es also etwas länger dauern. Verloren geht keine
              Nachricht.
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
