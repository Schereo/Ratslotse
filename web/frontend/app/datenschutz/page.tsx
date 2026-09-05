import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { BackLink } from "@/components/back-link";

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
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Datenschutzerklärung</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Diese Erklärung informiert über die Verarbeitung personenbezogener Daten bei der Nutzung von Ratslotse
          (ratslotse.de) gemäß Art. 13 DSGVO — und, im vorletzten Abschnitt, über die Verarbeitung der Daten von
          Ratsmitgliedern und Verwaltungsbeschäftigten aus den amtlichen Ratsdokumenten (Art. 14 DSGVO).
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
              <li><strong>Anmeldung mit Apple (optional):</strong> Meldest du dich mit Apple an, erhalten wir von Apple eine pseudonyme Nutzerkennung und deine E-Mail-Adresse (bei „E-Mail-Adresse verbergen" eine Apple-Weiterleitungsadresse). Beides dient ausschließlich der Anmeldung und Konto-Verknüpfung.</li>
              <li><strong>Push (optional):</strong> ein Geräte-Token, wenn du App-Push-Benachrichtigungen aktivierst.</li>
              <li><strong>Themen &amp; Watchlists:</strong> die von dir angelegten Suchthemen und Benachrichtigungseinstellungen.</li>
              <li><strong>„Frag den Rat"-Anfragen:</strong> die von dir eingegebenen Fragen, um eine KI-Antwort zu erzeugen.</li>
              <li><strong>Private Problemmeldungen:</strong> Entwürfe und bestätigte Beschreibungstexte, Kategorie, räumlicher Bezug, Ortsangabe, Koordinaten und Beobachtungsdatum. Die Meldungen bleiben deinem Konto zugeordnet. Bei einer Ablehnung speichern wir außerdem die endgültige Erklärung für dich.</li>
              <li><strong>Menschliche Prüfung:</strong> Die interne Moderationsentscheidung wird mit Zeitpunkt und prüfendem Konto protokolliert. Wird dieses Prüfkonto gelöscht, werden seine Kontodaten entfernt; nur eine nicht mehr zu einem bestehenden Konto auflösbare interne Prüfkennung und die Entscheidung bleiben als Nachweis bestehen.</li>
              <li><strong>Öffentliche Problemzuordnung:</strong> Erst nach einer getrennten menschlichen Bestätigung speichern wir intern, welche freigegebene Meldungsrevision welchem öffentlichen Problem zugeordnet wurde. Öffentlich erscheinen nur ein eigenständig formulierter Titel, eine neutrale Zusammenfassung, kontrollierte Angaben und die daraus abgeleitete Zahl unterschiedlicher meldender Konten — nie Kontodaten, privater Meldungstext oder genauer privater Ort.</li>
              <li><strong>Geteilte Antworten:</strong> Wenn du ausdrücklich „Teilen" auswählst, speichern wir Frage, Antwort und die dazugehörigen Belege unter einem nicht erratbaren öffentlichen Link. Jede Person mit dem Link kann den Inhalt lesen und melden. Der Link wird mit deinem Konto gelöscht; gemeldete Links können wir vorher entfernen.</li>
              <li><strong>Server-Logs:</strong> beim Aufruf technische Daten wie IP-Adresse, Zeitpunkt und User-Agent — zur Sicherheit und Fehleranalyse.</li>
            </ul>
          </Section>

          <Section title="Zwecke und Rechtsgrundlagen">
            <p>
              Bereitstellung von Konto, privaten Problemmeldungen, Themen und Benachrichtigungen zur Erfüllung des
              Nutzungsverhältnisses (Art. 6 Abs. 1 lit. b DSGVO). Der unveränderliche Nachweis menschlicher
              Moderationsentscheidungen, ausdrücklich bestätigten Problemzuordnungen sowie Server-Logs und Sicherheit beruhen auf dem berechtigten Interesse am
              nachvollziehbaren und sicheren Betrieb (Art. 6 Abs. 1 lit. f DSGVO).
            </p>
          </Section>

          <Section title="Empfänger / Auftragsverarbeiter">
            <p>Zur Erbringung des Dienstes setze ich folgende Dienstleister ein:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><strong>Hosting:</strong> Hetzner Online GmbH (Serverstandort EU). Betrieb der Server und Verarbeitung von Server-Logs.</li>
              <li><strong>KI-Verarbeitung (OpenRouter):</strong> „Frag den Rat"-Anfragen, für die Vorprüfung freigehaltene private Beschreibungstexte und die unten beschriebenen minimierten Angaben für Formulierungshilfen werden über OpenRouter an externe KI-Anbieter übermittelt; dabei kann eine Übermittlung in ein Drittland erfolgen. <strong>Bitte gib keine persönlichen oder sensiblen Daten in freie Textfelder ein.</strong></li>
              <li><strong>Resend:</strong> Versand von Benachrichtigungs-E-Mails (nur, wenn du E-Mail als Kanal wählst).</li>
              <li><strong>CARTO:</strong> Die Kartendarstellung lädt Kartenkacheln von CARTO; dabei wird deine IP-Adresse an CARTO übermittelt.</li>
              <li><strong>Apple / Google (Push):</strong> App-Benachrichtigungen werden über den Push-Dienst des Betriebssystems (APNs bzw. FCM) zugestellt — nur, wenn du Push als Kanal aktivierst.</li>
              <li><strong>Apple (Sign in with Apple):</strong> Nutzt du die Anmeldung mit Apple, wickelt Apple den Anmeldevorgang ab (Apple Distribution International Ltd., Irland); wir erhalten dabei nur die oben genannte Kennung und E-Mail-Adresse. Rechtsgrundlage ist die Vertragserfüllung (Art. 6 Abs. 1 lit. b DSGVO).</li>
            </ul>
          </Section>

          <Section title="KI-Vorprüfung privater Meldungen">
            <p>
              Nach dem privaten Eingang kann der bestätigte Beschreibungstext automatisch über OpenRouter an einen
              externen KI-Anbieter gesendet werden. Die Vorprüfung liefert nur einen kontrollierten Hinweis für eine
              spätere Prüfung durch einen Menschen. Sie trifft keine automatische Entscheidung über Wahrheit,
              Dringlichkeit, Zuständigkeit, Weitergabe oder Veröffentlichung der Meldung.
            </p>
            <p>
              Übermittelt werden nur die aktuellen Beschreibungstexte sowie die gewählte Kategorie und der räumliche
              Bezug. Kontodaten, die separat gespeicherte Ortsangabe, Koordinaten und das Beobachtungsdatum werden
              nicht an den Anbieter gesendet. Da der freie Beschreibungstext selbst persönliche Angaben enthalten
              kann, nenne dort bitte keine persönlichen oder sensiblen Daten.
            </p>
            <p>
              Für die Anbieterwahl werden OpenRouters Einstellungen gegen Datensammlung und Training sowie Zero Data
              Retention (ZDR) verwendet. Trotzdem kann die Verarbeitung in einem Drittland außerhalb der EU/des EWR
              stattfinden. Gespeichert wird nur das kontrollierte Ergebnis mit Modell- und Prüfungsversion, nicht die
              Modellantwort oder der dafür erzeugte Prompt.
            </p>
          </Section>

          <Section title="Menschliche Prüfung und KI-Formulierungshilfe">
            <p>
              Aktive Ratslotse-Admins und aktive, bestätigte Moderationskonten können private Meldungen prüfen. Dabei sehen
              sie Beschreibung und Beobachtungen, Kategorie, räumlichen Bezug, Datum und automatische Hinweise —
              aber weder dein Konto oder deine E-Mail-Adresse noch die genaue Ortsangabe oder Koordinaten. Die
              Entscheidung trifft immer ein Mensch. KI-Hinweise können vollständig überstimmt werden.
            </p>
            <p>
              Für eine Ablehnung kann ein bearbeitbarer deutscher Textentwurf über OpenRouter erzeugt werden. Hat
              die lokale Prüfung mögliche Notfall- oder Kontaktdaten erkannt, wird dafür kein Beschreibungstext
              übermittelt: Der Anbieter erhält dann nur kontrollierte Grundcodes sowie Kategorie und räumlichen
              Bezug. Andernfalls können die bereits minimierten Beschreibungstexte und kontrollierten Prüfhilfe-
              Angaben verwendet werden. Konto- und Meldungskennung, genauer Ort, Koordinaten und Datum werden nie
              für diese Formulierungshilfe gesendet. Ein Fehler des Dienstes verhindert keine manuell geschriebene
              Erklärung und löst niemals selbst eine Ablehnung aus.
            </p>
            <p>
              Gespeichert werden nur der bearbeitbare Entwurf mit Modell- und Versionsangabe sowie die davon
              getrennte endgültige menschliche Entscheidung. Rohe Prompts, Modellantworten, Begründungsketten und
              Anbieterfehler werden nicht als Moderationsevidenz gespeichert.
            </p>
          </Section>

          <Section title="Menschlich bestätigte öffentliche Problemzuordnung">
            <p>
              Eine menschliche Freigabe veröffentlicht noch nichts. Ein aktives Prüf- oder Adminkonto muss eine
              freigegebene Meldung in einem getrennten Schritt ausdrücklich einem bereits öffentlichen Problem
              zuordnen oder für eine stadtweite Meldung einen neuen öffentlichen Titel und eine neutrale
              Zusammenfassung verfassen und bestätigen. Dafür wird kein KI-Dienst aufgerufen; privater Meldungstext
              wird nicht automatisch in die öffentliche Darstellung übernommen.
            </p>
            <p>
              Die interne Zuordnung enthält Meldungsrevision, öffentliches Problem, Zeitpunkt und eine Prüfkennung.
              Öffentlich werden daraus nur die getrennt formulierten Problemangaben sowie eine Zahl unterschiedlicher,
              weiterhin berechtigter Meldekonten abgeleitet. Mehrere Meldungen desselben Kontos zählen für dasselbe
              Problem einmal. Konto, E-Mail-Adresse, privater Text, genauer Ort, Koordinaten, Prüf- und KI-Evidenz
              erscheinen nicht in der öffentlichen API oder Oberfläche.
            </p>
            <p>
              Wird das Meldekonto gelöscht, werden Meldung und abhängige Zuordnung gelöscht und ihr Beitrag aus der
              öffentlichen Zahl entfernt. Fehlt danach jede tragende Meldung, ist eine dadurch entstandene Projektion
              nicht mehr öffentlich sichtbar. Eine Veröffentlichung durch Ratslotse ist keine Annahme, Bearbeitung,
              Zuständigkeit oder Statusaussage der Stadt Oldenburg.
            </p>
          </Section>

          <Section title="Drittlandübermittlung">
            <p>
              Bei der KI-Verarbeitung kann eine Übermittlung in Länder außerhalb der EU/des EWR erfolgen. Die
              Anbieterwahl wird technisch auf Endpunkte ohne Datensammlung oder Training und mit Zero Data Retention
              beschränkt. Freie Texte werden dennoch nur übermittelt, wenn dies für die gewählte Funktion nötig ist;
              sie können persönliche Inhalte enthalten, falls du solche selbst eingibst.
            </p>
          </Section>

          <Section title="Cookies und lokale Speicherung">
            <p>
              Ratslotse setzt nur ein technisch notwendiges Cookie zur Anmeldung (Session). Im Browser und in der
              App werden außerdem einige technisch notwendige Daten lokal auf deinem Gerät gespeichert (localStorage):
              deine Design-Einstellung (hell/dunkel), in der App das Anmelde-Token sowie ein Zwischenspeicher der
              zuletzt geladenen Inhalte (bis zu 24 Stunden), damit die App auch offline etwas anzeigen kann. Es
              findet kein Tracking und keine Analyse-Software statt; daher ist keine Einwilligung (Cookie-Banner)
              erforderlich (§ 25 Abs. 2 TDDDG).
            </p>
          </Section>

          <Section title="Speicherdauer">
            <p>
              Kontodaten, private Problemmeldungen und ihre Prüfergebnisse werden gespeichert, solange dein Konto
              besteht. Server-Logs werden nur kurzzeitig zur Sicherheit vorgehalten. Du kannst die Löschung deines
              Kontos jederzeit verlangen.
            </p>
          </Section>

          {/* Art. 14 DSGVO: Ratslotse verarbeitet die mit Abstand meisten
              personenbezogenen Daten NICHT über seine Nutzer, sondern über
              Mandatsträger — erhoben aus amtlichen Protokollen, also nicht bei
              den Betroffenen selbst. Ohne diesen Abschnitt fehlte die
              Informationspflicht, und Apple liest das Zusammentragen aus
              öffentlichen Quellen ohne Erklärung als Verstoß gegen
              Guideline 5.1.1(viii). */}
          <Section title="Daten von Ratsmitgliedern und Verwaltung">
            <p>
              Ratslotse wertet die öffentlich zugänglichen Dokumente des Ratsinformationssystems der Stadt Oldenburg
              aus. Darin kommen Menschen vor: Ratsmitglieder, sachkundige Bürger*innen, Ausschussvorsitzende und
              Beschäftigte der Verwaltung. Diese Daten stammen nicht von den Betroffenen selbst, deshalb informiert
              dieser Abschnitt nach Art. 14 DSGVO.
            </p>
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <strong>Welche Daten:</strong> Name, Fraktion bzw. Gruppe und Parteizugehörigkeit, Mitgliedschaften
                und Ämter in Gremien samt Zeiträumen, protokollierte Anwesenheit, sinngemäß zusammengefasste
                Wortbeiträge und eingebrachte Anträge — jeweils mit Datum und Gremium.
              </li>
              <li>
                <strong>Woher:</strong> ausschließlich aus den veröffentlichten Einladungen, Vorlagen, Niederschriften
                und Beschlüssen unter{" "}
                <a href="https://buergerinfo.oldenburg.de" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  buergerinfo.oldenburg.de
                </a>
                . Es werden keine weiteren Quellen zusammengeführt, keine Profile aus sozialen Netzwerken ergänzt und
                keine Kontaktdaten, Anschriften oder Angaben aus dem Privatleben erhoben.
              </li>
              <li>
                <strong>Wozu und auf welcher Grundlage:</strong> die Arbeit des Stadtrats nachvollziehbar zu machen
                (Art. 6 Abs. 1 lit. f DSGVO). Das berechtigte Interesse ist die öffentliche Kontrolle politischer
                Entscheidungen; verarbeitet wird deshalb nur, was Personen in Ausübung ihres öffentlichen Mandats
                oder Amtes tun, nicht ihre Privatsphäre. Wortbeiträge werden als Zusammenfassung wiedergegeben, nicht
                als wörtliches Zitat.
              </li>
              <li>
                <strong>KI-Antworten:</strong> Für die Beantwortung einer Frage können Ausschnitte dieser Dokumente
                — und damit auch Namen von Mandatsträger*innen — an den KI-Dienst übermittelt werden. Antworten
                belegen jede Aussage mit der Quelle; maßgeblich bleibt das amtliche Original.
              </li>
              <li>
                <strong>Speicherdauer:</strong> solange die zugrunde liegenden Dokumente amtlich veröffentlicht sind
                und Ratslotse betrieben wird.
              </li>
              <li>
                <strong>Widerspruch und Korrektur:</strong> Wer in diesen Daten vorkommt, kann der Verarbeitung nach
                Art. 21 DSGVO widersprechen sowie Auskunft, Berichtigung oder Löschung verlangen — formlos an{" "}
                <a href="mailto:ratslotse@timsigl.de" className="text-primary hover:underline">ratslotse@timsigl.de</a>.
                Fehlerhafte Zuordnungen (etwa Namensverwechslungen) korrigiere ich auch ohne förmlichen Antrag; ein
                Hinweis genügt. Bei einem Widerspruch prüfe ich im Einzelfall, ob das öffentliche Interesse an der
                Nachvollziehbarkeit einer konkreten Entscheidung überwiegt, und teile das Ergebnis mit.
              </li>
            </ul>
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
