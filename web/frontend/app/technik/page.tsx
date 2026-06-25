import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";

export const metadata: Metadata = {
  title: "Technik & Methodik – Ratslotse",
  description: "Wie Ratslotse die Oldenburger Ratsinformationen aufbereitet: Extraktion, Klassifikation, Embeddings, Hybrid-Retrieval mit Reranker, Ziel-Tracking und Qualitätsmessung.",
};

/* Diese Seite ist bewusst als zusammenhängender Text gehalten, damit sie leicht
   fortgeschrieben werden kann: neue Abschnitte einfach als <Section> ergänzen. */

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-border pt-8">
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      <div className="mt-3 space-y-3 leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">{n}</div>
      <div>
        <p className="font-medium text-foreground">{title}</p>
        <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}

const Code = ({ children }: { children: React.ReactNode }) => (
  <code className="rounded bg-muted px-1.5 py-0.5 text-[0.85em] text-foreground">{children}</code>
);

export default function TechnikPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
          <Link href="/" className="flex items-center gap-2"><BrandMark /><span className="font-semibold text-foreground">Ratslotse</span></Link>
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">Anmelden →</Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Wie Ratslotse funktioniert</h1>
        <p className="mt-3 text-lg leading-relaxed text-muted-foreground">
          Ratslotse macht die Beschlüsse des Oldenburger Stadtrats durchsuchbar, vergleichbar und
          verständlich. Diese Seite erklärt offen, mit welchen Verfahren — von der PDF-Extraktion bis
          zur KI-gestützten Suche — das geschieht, und wo die Grenzen liegen. Sie wird fortlaufend
          erweitert.
        </p>

        <div className="mt-8 space-y-8">
          <Section id="daten" title="Datengrundlage">
            <p>
              Quelle sind die öffentlichen Sitzungsprotokolle des Oldenburger Ratsinformationssystems
              (RIS) sowie — für die Presse-Verknüpfung — Artikel der Nordwest-Zeitung. Ratslotse
              verarbeitet ausschließlich öffentlich zugängliche Dokumente und ist <em>kein</em> amtliches
              Angebot der Stadt.
            </p>
          </Section>

          <Section id="pipeline" title="Die Verarbeitungskette">
            <p>Jeder Beschluss durchläuft mehrere Schritte — klassische Verfahren und KI dort, wo sie wirklich hilft:</p>
            <div className="mt-4 space-y-4 rounded-lg border border-border bg-card p-4 sm:p-5">
              <Step n={1} title="Extraktion (PDF → Struktur)">
                Die Protokoll-PDFs werden Tagesordnungspunkt für Tagesordnungspunkt von einem
                Sprachmodell (deepseek-v4-pro über OpenRouter) in strukturierte Beschlüsse,
                Abstimmungen, Teilabstimmungen und Anwesenheiten zerlegt.
              </Step>
              <Step n={2} title="Klassifikation (Themenfelder)">
                Dasselbe Modell ordnet jeden Beschluss einem von zwölf Themenfeldern zu (Verkehr,
                Klima &amp; Umwelt, Bauen &amp; Wohnen …), vergibt feinere Schlagworte und schreibt eine
                neutrale Ein-Satz-Zusammenfassung — ohne Trainingsbeispiele (Zero-Shot), nur anhand
                einer Definition je Feld.
              </Step>
              <Step n={3} title="Embeddings (Bedeutung als Vektor)">
                Ein kleines, mehrsprachiges Modell (<Code>paraphrase-multilingual-MiniLM-L12-v2</Code> via
                fastembed/ONNX) wandelt jeden Beschluss in einen 384-dimensionalen Zahlenvektor um.
                Inhaltlich ähnliche Beschlüsse liegen darin nah beieinander — die Basis für „Ähnliche
                Beschlüsse" und die semantische Suche.
              </Step>
              <Step n={4} title="Anreicherung">
                Regeln und Modelle ergänzen: erkannte €-Beträge, normalisierte Antragstellenden-
                Fraktionen, Verknüpfungen zu Stadtzielen und zu Presseartikeln.
              </Step>
            </div>
          </Section>

          <Section id="retrieval" title="Frag den Rat: Retrieval und Antwort">
            <p>
              Die Freitext-Frage wird nicht einfach 1:1 gesucht. Stattdessen läuft eine mehrstufige
              Pipeline, wie sie auch in aktuellen Such-/RAG-Systemen Standard ist:
            </p>
            <div className="mt-4 space-y-4 rounded-lg border border-border bg-card p-4 sm:p-5">
              <Step n={1} title="Query-Expansion">
                Ein Sprachmodell wandelt die Frage zuerst in themenspezifische Suchbegriffe um
                („Radverkehr?" → „Radverkehr Fahrradinfrastruktur Radwege Fahrradstraßen …"). Das hebt
                die wirklich relevanten Beschlüsse deutlich nach oben.
              </Step>
              <Step n={2} title="Hybrid-Retrieval (Stichwort + Bedeutung)">
                Parallel wird klassisch über einen Volltext-Index (SQLite FTS5, BM25-Ranking, inklusive
                Umlaut- und ß-Normalisierung) <em>und</em> semantisch über die Vektoren gesucht. Die
                Stichwortsuche fängt exakte Begriffe, die Vektorsuche den Sinn — zusammen ist die
                Trefferliste robuster als jede Methode allein.
              </Step>
              <Step n={3} title="Reranking (Cross-Encoder)">
                Aus dem gemeinsamen Kandidatenpool sortiert ein mehrsprachiger Cross-Encoder
                (<Code>jina-reranker-v2</Code>) die Treffer neu — er liest Frage und Beschluss gemeinsam und
                bewertet die echte Relevanz, statt nur Vektor-Abstände zu vergleichen.
              </Step>
              <Step n={4} title="Antwort mit Quellen">
                Erst die besten Treffer gehen an das Sprachmodell, das eine Antwort formuliert, die
                <em> ausschließlich</em> aus diesen Beschlüssen zitiert (mit Quell-Verweisen) und ehrlich
                sagt, wenn nichts Passendes gefunden wurde.
              </Step>
            </div>
          </Section>

          <Section id="ziele" title="Ziel-Tracking">
            <p>
              Für jedes übergeordnete Stadtziel (z. B. Klimaneutralität 2035, Mobilitätsplan 2030,
              bezahlbarer Wohnraum) werden passende Beschlüsse über Stichworte <em>und</em> semantische
              Ähnlichkeit gesammelt. Ein Sprachmodell bewertet dann je Beschluss, ob er das Ziel
              <em> voranbringt</em>, <em>bremst</em> oder <em>neutral</em> berührt — wobei reine Berichte und
              vertagte Punkte bewusst als neutral gelten.
            </p>
          </Section>

          <Section id="weiteres" title="News, Geld und Parteien">
            <p>
              <strong className="text-foreground">Presse-Verknüpfung:</strong> Beschlüsse und NWZ-Artikel
              werden über den Artikelinhalt eingebettet und nur verknüpft, wenn sie ein themenspezifisches
              Wort teilen und zeitlich zusammenpassen — das hält Stichwort-Zufälle heraus.
            </p>
            <p>
              <strong className="text-foreground">Geld-Tracking:</strong> per Mustererkennung (Regex) wird der
              im Text genannte €-Betrag erkannt — Einheitspreise wie „275 €/m²" werden ausgeschlossen, damit
              nur belastbare Größenordnungen erscheinen.
            </p>
            <p>
              <strong className="text-foreground">Parteien:</strong> Fraktionsnamen werden auf eine gepflegte
              Liste der real existierenden Oldenburger Fraktionen normalisiert; Nicht-Parteien (Verwaltung,
              Verbände, Beiräte) werden aus der Partei-Analyse herausgehalten.
            </p>
          </Section>

          <Section id="qualitaet" title="Qualität und Messung">
            <p>
              KI kann irren — deshalb wird die Qualität laufend gegen ein „Gold-Set" gemessen:
              rund 200 Beschlüsse, die zweimal unabhängig eingeordnet wurden; übernommen wird nur,
              worüber sich beide Durchläufe einig waren. Bei jeder Änderung an Modellen, Prompts oder
              Suche läuft die Prüfung erneut und schlägt an, wenn die Genauigkeit fällt.
            </p>
            <p>Auf diesem Gold-Set zeigt sich (Stand der jüngsten Messung):</p>
            <ul className="ml-4 list-disc space-y-1">
              <li><strong className="text-foreground">Themenfeld:</strong> ~88 % stimmen mit der unabhängigen Einordnung überein. Die meisten Abweichungen betreffen Beschlüsse, die echt zwei Themenfelder berühren.</li>
              <li><strong className="text-foreground">Ziel-Bewertung:</strong> die Richtung (bringt voran ↔ bremst) wird verlässlich getroffen — kein einziger Richtungsfehler. Unschärfe gibt es nur an der Grenze „neutral".</li>
              <li><strong className="text-foreground">Frag den Rat:</strong> im Test ausschließlich belegte Antworten — keine erfundenen Fakten, keine falschen Quellen, und ehrliches „nichts gefunden", wenn es nichts gibt.</li>
            </ul>
            <p className="text-sm">
              Diese Zahlen sind bewusst nüchtern: Sie messen Übereinstimmung mit einer sorgfältigen,
              aber ebenfalls fehlbaren Referenz — kein „die KI hat zu X % recht".
            </p>
          </Section>

          <Section id="grenzen" title="Grenzen und Transparenz">
            <p>
              Automatische Zusammenfassungen und Einordnungen können unvollständig oder falsch sein.
              Ratslotse zeigt deshalb immer die zugrunde liegenden Beschlüsse und verlinkt das amtliche
              Ratsinformationssystem — verbindlich ist allein das Originaldokument. Die KI-Antworten sind
              eine Orientierung, kein Rechtsdokument.
            </p>
          </Section>
        </div>

        <footer className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          <p>
            Ratslotse ist ein offenes Projekt. Quellcode und technische Details:{" "}
            <a href="https://github.com/Schereo/kommunalwahl-scraper" target="_blank" rel="noreferrer" className="text-primary hover:underline">GitHub</a>.
          </p>
        </footer>
      </main>
    </div>
  );
}
