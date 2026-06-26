import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";

export const metadata: Metadata = {
  title: "Datenschutzerklärung – Ratslotse",
  description: "Welche Daten Ratslotse verarbeitet, zu welchen Zwecken, an welche Empfänger — und welche Rechte du hast.",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border pt-6">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <div className="mt-2 space-y-2 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export default function DatenschutzPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
          <Link href="/" className="flex items-center gap-2"><BrandMark /><span className="font-semibold text-foreground">Ratslotse</span></Link>
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">Anmelden →</Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Datenschutzerklärung</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Diese Erklärung informiert über die Verarbeitung personenbezogener Daten bei der Nutzung von Ratslotse
          (ratslotse.de) gemäß Art. 13 DSGVO.
        </p>

        <div className="mt-6 space-y-6">
          <Section title="Verantwortlicher">
            <p>
              Tim Sigl, Krusenweg 26, 26135 Oldenburg ·{" "}
              <a href="mailto:ratslotse@timsigl.de" className="text-primary hover:underline">ratslotse@timsigl.de</a>
            </p>
          </Section>

          <Section title="Welche Daten wir verarbeiten">
            <ul className="list-disc space-y-1 pl-5">
              <li><strong>Konto:</strong> E-Mail-Adresse und ein Passwort-Hash (das Passwort selbst wird nicht im Klartext gespeichert).</li>
              <li><strong>Telegram (optional):</strong> die Chat-ID, wenn du den Telegram-Bot verknüpfst.</li>
              <li><strong>NWZ-Zugang (optional):</strong> dein NWZ-Benutzername zur Verifikation. <strong>Dein NWZ-Passwort wird nicht gespeichert</strong> — es wird einmalig zur Prüfung an die NWZ übermittelt und danach verworfen.</li>
              <li><strong>Themen &amp; Watchlists:</strong> die von dir angelegten Suchthemen und Benachrichtigungseinstellungen.</li>
              <li><strong>„Frag den Rat"-Anfragen:</strong> die von dir eingegebenen Fragen, um eine KI-Antwort zu erzeugen.</li>
              <li><strong>Server-Logs:</strong> beim Aufruf technische Daten wie IP-Adresse, Zeitpunkt und User-Agent — zur Sicherheit und Fehleranalyse.</li>
            </ul>
          </Section>

          <Section title="Zwecke und Rechtsgrundlagen">
            <p>
              Bereitstellung von Konto, Themen und Benachrichtigungen zur Erfüllung des Nutzungsverhältnisses
              (Art. 6 Abs. 1 lit. b DSGVO). Server-Logs und Sicherheit auf Grundlage des berechtigten Interesses am
              sicheren Betrieb (Art. 6 Abs. 1 lit. f DSGVO).
            </p>
          </Section>

          <Section title="Empfänger / Auftragsverarbeiter">
            <p>Zur Erbringung des Dienstes setze ich folgende Dienstleister ein:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><strong>Hosting:</strong> Hetzner Online GmbH (Serverstandort EU). Betrieb der Server und Verarbeitung von Server-Logs.</li>
              <li><strong>KI-Verarbeitung (OpenRouter):</strong> „Frag den Rat"-Anfragen werden zur Beantwortung an einen externen KI-Dienst übermittelt; dabei kann eine Übermittlung in ein Drittland erfolgen. <strong>Bitte gib keine personenbezogenen oder sensiblen Daten in die Fragen ein.</strong></li>
              <li><strong>Resend:</strong> Versand von Benachrichtigungs-E-Mails (nur, wenn du E-Mail als Kanal wählst).</li>
              <li><strong>CARTO:</strong> Die Kartendarstellung lädt Kartenkacheln von CARTO; dabei wird deine IP-Adresse an CARTO übermittelt.</li>
              <li><strong>Telegram:</strong> Zustellung von Benachrichtigungen (nur bei verknüpftem Telegram-Konto).</li>
            </ul>
          </Section>

          <Section title="Drittlandübermittlung">
            <p>
              Bei der KI-Verarbeitung kann eine Übermittlung in Länder außerhalb der EU/des EWR erfolgen. Ich bemühe
              mich, die Verarbeitung auf Anbieter mit angemessenem Datenschutzniveau bzw. geeigneten Garantien zu
              beschränken und keine personenbezogenen Inhalte zu übermitteln.
            </p>
          </Section>

          <Section title="Cookies">
            <p>
              Ratslotse setzt nur ein technisch notwendiges Cookie zur Anmeldung (Session). Es findet kein Tracking
              und keine Analyse-Software statt; daher ist keine Einwilligung (Cookie-Banner) erforderlich
              (§ 25 Abs. 2 TDDDG).
            </p>
          </Section>

          <Section title="Speicherdauer">
            <p>
              Kontodaten werden gespeichert, solange dein Konto besteht. Server-Logs werden nur kurzzeitig zur
              Sicherheit vorgehalten. Du kannst die Löschung deines Kontos jederzeit verlangen.
            </p>
          </Section>

          <Section title="Deine Rechte">
            <p>
              Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung,
              Datenübertragbarkeit und Widerspruch (Art. 15–21 DSGVO). Wende dich dafür an die oben genannte
              Kontaktadresse. Außerdem besteht ein Beschwerderecht bei einer Datenschutz-Aufsichtsbehörde, z. B. der
              Landesbeauftragten für den Datenschutz Niedersachsen.
            </p>
          </Section>
        </div>

        <footer className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          <Link href="/impressum" className="text-primary hover:underline">Impressum</Link>
          {" · "}
          <Link href="/" className="hover:text-foreground">Startseite</Link>
        </footer>
      </main>
    </div>
  );
}
