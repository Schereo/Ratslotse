import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { BackLink } from "@/components/back-link";
import { KONTAKT_EMAIL, KONTAKT_MAILTO } from "@/lib/kontakt";
import { KopfKontoLink } from "@/components/kopf-konto-link";

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
          <KopfKontoLink />
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
              <a href={KONTAKT_MAILTO} className="text-primary hover:underline">{KONTAKT_EMAIL}</a>
            </p>
          </Section>

          <Section title="Welche Daten wir verarbeiten">
            <ul className="list-disc space-y-1 pl-5">
              <li><strong>Konto:</strong> E-Mail-Adresse und ein Passwort-Hash (das Passwort selbst wird nicht im Klartext gespeichert).</li>
              <li><strong>Anmeldung mit Apple (optional):</strong> Meldest du dich mit Apple an, erhalten wir von Apple eine pseudonyme Nutzerkennung und deine E-Mail-Adresse (bei „E-Mail-Adresse verbergen" eine Apple-Weiterleitungsadresse). Beides dient ausschließlich der Anmeldung und Konto-Verknüpfung.</li>
              <li><strong>Push (optional):</strong> ein Geräte-Token, wenn du App-Push-Benachrichtigungen aktivierst.</li>
              <li><strong>Themen &amp; Watchlists:</strong> die von dir angelegten Suchthemen und Benachrichtigungseinstellungen. Dazu gehören auch die Stadtteile, die „Mein Viertel" als deine Viertel zeigt — sie sind Themen deines Kontos und liegen wie diese auf dem Server.</li>
              <li><strong>Meldungen zu „Mein Viertel":</strong> Meldest du ein Vorhaben als „Gehört nicht hierher", speichern wir die Meldung samt dem Grund, den du optional angibst, und dein Konto dazu. Die Redaktion sieht Vorhaben und Grund, nicht aber, wer gemeldet hat. Du kannst die Meldung zurücknehmen; mit deinem Konto wird sie gelöscht.</li>
              <li><strong>„Frag den Rat"-Anfragen und Fragen an Lotti:</strong> die von dir eingegebenen Fragen, um eine KI-Antwort zu erzeugen — bei Lotti zusammen mit dem Ausschnitt der Seite, auf den sich die Frage bezieht (etwa ein angeklickter Baustein oder markierter Text).</li>
              <li><strong>Gespeicherte Gespräche (nur mit deiner Einwilligung):</strong> Erlaubst du das Speichern, legen wir Fragen und Antworten mit deinem Konto ab, damit du sie auf allen Geräten unter „Gespräche" wiederfindest. Du kannst einzelne Gespräche oder alle auf einmal löschen und das Speichern jederzeit wieder ausschalten. Zur Verbesserung der Antworten sehe ich mir in der Verwaltung Fragen aus gespeicherten Gesprächen an, auf die es keine belegte Antwort gab (die letzten 30 Tage) — ohne Angabe, von welchem Konto sie stammen.</li>
              <li><strong>Gründliche Recherche:</strong> Eine Recherche läuft im Hintergrund weiter, auch wenn du die App schließt. Deshalb speichern wir Frage und Bericht mit deinem Konto, bis du sie abrufst. Ohne Einwilligung ins Speichern von Gesprächen löschen wir beides sieben Tage nach Fertigstellung; mit Einwilligung steht der Bericht als Gespräch in deinem Konto. „Alle Gespräche löschen" entfernt auch deine Recherchen.</li>
              <li><strong>Rückmeldungen zu KI-Antworten:</strong> Gibst du einer Antwort einen Daumen hoch oder runter, speichern wir die Frage, einen Auszug der Antwort, die Bewertung, den optional angegebenen Grund und — wenn du angemeldet bist — dein Konto. Sie werden mit deinem Konto gelöscht.</li>
              <li><strong>Feedback und Kontaktformular:</strong> Über den Feedback-Dialog (angemeldet) oder das Kontaktformular der Hilfe-Seite (ohne Konto) speichern wir deine Nachricht, ihre Art und deine E-Mail-Adresse und schicken sie mir per E-Mail, damit ich antworten kann. Feedback aus dem Konto wird mit dem Konto gelöscht.</li>
              <li><strong>Nutzung je Konto:</strong> Für angemeldete Konten zählen wir je Tag, welche Funktionen wie oft genutzt wurden (etwa Frage, Recherche, Suche, Karte) und ob über Web oder App — ohne Inhalte, ohne Uhrzeit, ohne IP-Adresse. Daraus entstehen die Übersichten in der Verwaltung, etwa wie viele Konten eine Woche aktiv waren. Die Zählung wird mit deinem Konto gelöscht. Seitenaufrufe zählen wir nur als Summe je Seite und Tag, ohne Konto- oder Gerätebezug.</li>
              <li><strong>Mailprotokoll:</strong> Welche Service- und Benachrichtigungs-Mails an dein Konto gingen (Anlass, Betreff, Zeitpunkt, Zustellkennung) — damit sich Fragen wie „warum kam keine Mail?" beantworten lassen. Es wird mit deinem Konto gelöscht.</li>
              <li><strong>Tippspiel zur Wahl:</strong> Spielst du mit, speichern wir den Namen, den du dafür wählst, optional eine Parteizugehörigkeit und deine Tipps. <strong>Name, Partei und Platzierung sind in der Rangliste öffentlich sichtbar</strong> — wähle also keinen Namen, der dich ungewollt erkennbar macht. Ohne Konto erkennt dich das Spiel an einem Cookie (siehe unten), in Konto-Runden an deinem Konto.</li>
              <li><strong>Geteilte Antworten:</strong> Wenn du ausdrücklich „Teilen" auswählst, speichern wir Frage, Antwort und die dazugehörigen Belege unter einem nicht erratbaren öffentlichen Link. Jede Person mit dem Link kann den Inhalt lesen und melden. Der Link wird mit deinem Konto gelöscht; gemeldete Links können wir vorher entfernen.</li>
              <li><strong>Rückmeldungen zu Einordnungen:</strong> Wenn du bei „Ideen aus anderen Städten" angibst, ob eine Einordnung stimmt, speichern wir deine Antwort mit deinem Konto, damit du sie wiedersiehst und wir die Einordnungen prüfen können. Sie werden mit deinem Konto gelöscht.</li>
              <li><strong>Server-Logs:</strong> beim Aufruf technische Daten wie IP-Adresse, Zeitpunkt und User-Agent — zur Sicherheit und Fehleranalyse.</li>
            </ul>
          </Section>

          <Section title="Zwecke und Rechtsgrundlagen">
            <p>
              Bereitstellung von Konto, Themen und Benachrichtigungen zur Erfüllung des Nutzungsverhältnisses
              (Art. 6 Abs. 1 lit. b DSGVO). Server-Logs und Sicherheit auf Grundlage des berechtigten Interesses am
              sicheren Betrieb (Art. 6 Abs. 1 lit. f DSGVO). Das Speichern von Gesprächen erfolgt nur mit deiner
              Einwilligung (Art. 6 Abs. 1 lit. a DSGVO), die du in den Einstellungen jederzeit widerrufen kannst.
              Nutzungszählung, Mailprotokoll und Rückmeldungen zu Antworten dienen dem berechtigten Interesse, den
              Dienst zuverlässig zu betreiben und zu verbessern (Art. 6 Abs. 1 lit. f DSGVO).
            </p>
          </Section>

          <Section title="Empfänger / Auftragsverarbeiter">
            <p>Zur Erbringung des Dienstes setze ich folgende Dienstleister ein:</p>
            <ul className="list-disc space-y-1 pl-5">
              <li><strong>Hosting:</strong> Hetzner Online GmbH (Serverstandort EU). Betrieb der Server und Verarbeitung von Server-Logs.</li>
              <li><strong>KI-Verarbeitung (OpenRouter):</strong> „Frag den Rat"-Anfragen und Fragen an Lotti werden zur Beantwortung über den Vermittler OpenRouter (USA) an ein KI-Sprachmodell übermittelt. Die Antworten erzeugt derzeit ein Modell von OpenAI. Im Regelfall läuft es bei Microsoft Azure in der EU, mit der Zusage, Anfragen nicht zu speichern („Zero Data Retention"). Nur wenn dieser Weg gestört ist, geht die Anfrage ausnahmsweise direkt an OpenAI (USA); dort wird sie vorübergehend gespeichert, eine solche Zusage gibt es dort nicht. Ausgeschlossen sind in jedem Fall Anbieter, die Anfragen zum Training verwenden, und Anbieter mit Sitz in China. Die vorbereitende Auswertung deiner Frage (Suchbegriffe) erzeugt ein Modell von Google, nur bei Anbietern mit Zero-Data-Retention-Zusage. Zur Qualitätssicherung prüft ein Modell von Google außerdem eine zufällige Stichprobe von Lottis Antworten nachträglich — dafür gehen Frage, Antwort und der Seitenausschnitt noch einmal über OpenRouter, ebenfalls nur an Anbieter mit Zero-Data-Retention-Zusage. Gespeichert wird bei uns das Urteil mit der Seite, auf der gefragt wurde; Frage und Antwort samt Konto-Zuordnung nur, wenn du das Speichern deiner Gespräche erlaubt hast, und sie werden mit deinem Konto gelöscht. <strong>Bitte gib keine personenbezogenen oder sensiblen Daten in die Fragen ein.</strong></li>
              <li><strong>Resend:</strong> Versand von Benachrichtigungs-E-Mails (nur, wenn du E-Mail als Kanal wählst).</li>
              <li><strong>CARTO:</strong> Die Kartendarstellung lädt Kartenkacheln von CARTO; dabei wird deine IP-Adresse an CARTO übermittelt.</li>
              <li><strong>Apple / Google (Push):</strong> App-Benachrichtigungen werden über den Push-Dienst des Betriebssystems (APNs bzw. FCM) zugestellt — nur, wenn du Push als Kanal aktivierst.</li>
              <li><strong>Apple (Sign in with Apple):</strong> Nutzt du die Anmeldung mit Apple, wickelt Apple den Anmeldevorgang ab (Apple Distribution International Ltd., Irland); wir erhalten dabei nur die oben genannte Kennung und E-Mail-Adresse. Rechtsgrundlage ist die Vertragserfüllung (Art. 6 Abs. 1 lit. b DSGVO).</li>
            </ul>
          </Section>

          <Section title="Drittlandübermittlung">
            <p>
              Bei der KI-Verarbeitung kann eine Übermittlung in Länder außerhalb der EU/des EWR erfolgen. Ich bemühe
              mich, die Verarbeitung auf Anbieter mit angemessenem Datenschutzniveau bzw. geeigneten Garantien zu
              beschränken und keine personenbezogenen Inhalte zu übermitteln.
            </p>
          </Section>

          <Section title="Cookies und lokale Speicherung">
            <p>
              Ratslotse setzt ein technisch notwendiges Cookie zur Anmeldung (Session). Spielst du ohne Konto beim
              Tippspiel mit, kommt ein zweites hinzu, das dich als Mitspieler*in wiedererkennt und nach 30 Tagen
              abläuft; es enthält nur ein zufälliges Geheimnis, gespeichert wird bei uns lediglich dessen Prüfsumme.
              Im Browser und in der App werden außerdem einige technisch notwendige Daten lokal auf deinem Gerät
              gespeichert (localStorage): deine Design-Einstellung (hell/dunkel), in der App das Anmelde-Token sowie
              ein Zwischenspeicher der zuletzt geladenen Inhalte (bis zu 24 Stunden), damit die App auch offline etwas
              anzeigen kann. Es gibt kein Tracking durch Dritte, keine Werbung und keine Analyse-Software; die
              oben beschriebene Nutzungszählung läuft auf unserem eigenen Server und braucht kein Cookie. Daher ist
              keine Einwilligung (Cookie-Banner) erforderlich (§ 25 Abs. 2 TDDDG).
            </p>
          </Section>

          <Section title="Speicherdauer">
            <p>
              Kontodaten werden gespeichert, solange dein Konto besteht; mit der Löschung des Kontos entfernen wir
              auch Themen, gespeicherte Gespräche, Recherchen, Rückmeldungen, Feedback, Nutzungszählung und
              Mailprotokoll. Recherchen ohne Einwilligung ins Speichern von Gesprächen löschen wir schon sieben Tage
              nach Fertigstellung. Server-Logs werden nur kurzzeitig zur Sicherheit vorgehalten. Tägliche
              Sicherungskopien der Datenbanken bewahren wir rund fünf Wochen auf; gelöschte Daten verschwinden aus
              ihnen spätestens dann. Du kannst die Löschung deines Kontos jederzeit selbst unter „Konto"
              auslösen oder verlangen.
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
                <a href={KONTAKT_MAILTO} className="text-primary hover:underline">{KONTAKT_EMAIL}</a>.
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
