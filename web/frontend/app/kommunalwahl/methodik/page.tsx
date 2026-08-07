// /kommunalwahl/methodik — die Vertrauensseite (Design 3d, bewusst Gerüst).
//
// Zwei Abschnitte bleiben laut Handoff GESTRICHELT OFFEN („Wie die KI liest",
// „Die vier Einschränkungen"): Die Extraktion wird gerade überarbeitet und
// verschärft — die Texte werden danach geschrieben, nicht vorher. Die Route
// existiert trotzdem, sie ist von jeder Seite verlinkt.

import type { Metadata } from "next";
import { Glyph, KiPlakette, KwCrumb, KwFuss, KwKopf } from "@/components/kommunalwahl/ui";
import { methodik, stand } from "@/lib/kommunalwahl";

export const metadata: Metadata = {
  title: "Methodik & Quellen",
  description:
    "So ist der Wahlprogramm-Vergleich gerechnet: Rechenweg, Thesenkatalog und prüfbares Quellenverzeichnis mit SHA256-Prüfsummen.",
};

function groesse(bytes: number | null): string {
  if (!bytes) return "—";
  return bytes >= 1_048_576 ? `${(bytes / 1_048_576).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

export default function MethodikSeite() {
  const m = methodik();
  return (
    <>
      <KwKopf crumb={<KwCrumb teil="Methodik" />} />
      <main className="mx-auto w-full max-w-[860px] px-4 pb-16 pt-9 sm:px-6 sm:pt-11">
        <h1 className="font-display text-[26px] font-bold leading-tight tracking-tight sm:text-[34px]">
          So ist dieser Vergleich gerechnet
        </h1>
        <p className="mt-3 max-w-[70ch] text-sm leading-relaxed text-muted-foreground">
          Die Vertrauensseite: Rechenweg, KI-Auswertung und ihre Grenzen, der vollständige Thesenkatalog
          und das prüfbare Quellenverzeichnis.
        </p>

        <div className="mt-7 flex flex-col gap-3">
          <div className="rounded-[14px] border border-border bg-card px-5 py-4">
            <p className="text-sm font-bold">Der Rechenweg</p>
            <p className="mt-1.5 font-mono text-[12.5px] leading-relaxed text-muted-foreground sm:text-[13px]">
              Übereinstimmung je These = 1 − |a−b| / 2 · Ähnlichkeit = Mittelwert × 100 · n = gemeinsame
              Thesen · n &lt; {m.minN} → nicht belastbar
            </p>
            <p className="mt-2 text-[12.5px] leading-relaxed text-muted-foreground">
              Position je These: +1 Zustimmung, 0 teils/teils, −1 Ablehnung, „keine Aussage" bleibt außen
              vor. Gewertet werden nur Thesen, zu denen sich <strong className="font-semibold text-foreground">beide</strong>{" "}
              Listen äußern. Äußern sich beide nur unbestimmt (0/0), zählt das als volle Übereinstimmung —
              das Paar-Detail auf der Nähe-Seite weist diese Thesen deshalb eigens aus.
            </p>
          </div>

          <div className="flex items-center gap-3.5 rounded-[14px] border-2 border-dashed border-border px-5 py-4">
            <KiPlakette className="!h-6 !w-[34px] text-[11px]" />
            <div>
              <p className="text-sm font-bold text-muted-foreground">Wie die KI liest, zuordnet und zitiert — folgt</p>
              <p className="mt-1 text-[12.5px] text-muted-foreground">
                Die Extraktion wird gerade überarbeitet und verschärft; dieser Abschnitt wird danach
                geschrieben, nicht vorher.
              </p>
            </div>
          </div>

          <div className="rounded-[14px] border-2 border-dashed border-border px-5 py-4">
            <p className="text-sm font-bold text-muted-foreground">Die vier Einschränkungen — folgt</p>
            <p className="mt-1 text-[12.5px] text-muted-foreground">
              Aus dem README des Datenbestands, in Ratslotse-Ton übersetzt.
            </p>
          </div>

          <div id="thesen" className="scroll-mt-24 rounded-[14px] border border-border bg-card px-5 py-4">
            <p className="text-sm font-bold">Thesenkatalog — alle 44, mit Themenfeld</p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
              Vollständig einsehbar, denn die Auswahl der Thesen beeinflusst jeden Prozentwert auf diesen
              Seiten. Verteilung jeweils über die 9 verglichenen Listen.
            </p>
            <div className="mt-3 flex flex-col">
              {m.thesen.map((t) => (
                <div key={t.id} className="border-b border-border/50 py-2.5 last:border-b-0">
                  <p className="text-[13px] font-semibold leading-snug">
                    <span className="text-primary">{t.id}</span> · {t.these}
                  </p>
                  <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-muted-foreground">
                    <span>{t.themaLabel}</span>
                    <span className="inline-flex items-center gap-1">
                      <Glyph pos={1} size={12} /> {t.stat.dafuer}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Glyph pos={0} size={12} /> {t.stat.teils}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Glyph pos={-1} size={12} /> {t.stat.dagegen}
                    </span>
                    <span>n = {t.stat.n}</span>
                    {!t.stat.belastbar && <span className="text-amber-700 dark:text-amber-400">unter der Schranke</span>}
                  </p>
                  {t.hinweis && <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">{t.hinweis}</p>}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[14px] border border-border bg-card px-5 py-4">
            <p className="text-sm font-bold">Quellenverzeichnis — je Liste URL, Abrufdatum, Format, Größe, SHA256</p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
              Wir verlinken ausschließlich auf die Originale bei den Parteien und speichern selbst nur den
              „Fingerabdruck" (SHA256) jeder ausgewerteten Datei. Auf jeder Profilseite prüft Ratslotse
              damit live, ob hinter dem Link noch genau die Datei steht, die wir ausgewertet haben — und
              sagt es dazu, falls nicht. Selbst nachprüfen: PDF bei der Partei herunterladen, dann{" "}
              <code className="font-mono text-[11.5px]">shasum -a 256 programm.pdf</code> — der Wert muss
              dem in der Tabelle entsprechen.
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[12.5px]">
                <thead>
                  <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
                    <th className="py-2 pr-3 font-semibold">Liste</th>
                    <th className="py-2 pr-3 font-semibold">Quelle</th>
                    <th className="py-2 pr-3 font-semibold">Format</th>
                    <th className="py-2 pr-3 font-semibold">Größe</th>
                    <th className="py-2 font-semibold">SHA256</th>
                  </tr>
                </thead>
                <tbody>
                  {m.quellen.map((q) => (
                    <tr key={q.slug} className="border-b border-border/50 align-top last:border-b-0">
                      <td className="py-2 pr-3 font-semibold">{q.liste}</td>
                      <td className="max-w-[300px] py-2 pr-3">
                        <a
                          href={q.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block truncate text-primary"
                          title={q.titel}
                        >
                          {q.url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0]} ↗
                        </a>
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground">
                        {q.format}
                        {q.seiten ? ` · ${q.seiten} S.` : ""}
                      </td>
                      <td className="py-2 pr-3 tabular-nums text-muted-foreground">{groesse(q.bytes)}</td>
                      <td className="py-2 font-mono text-[11px] text-muted-foreground">
                        {q.sha256 ? `${q.sha256.slice(0, 16)}…` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11.5px] text-muted-foreground">
              Ausgewertet am {m.abgerufen}. Die extrahierten Volltexte (mit Seitenmarkern) liegen offen im
              Ratslotse-Repository — die PDFs selbst hosten wir nicht, sie gehören den Parteien.
            </p>
          </div>
        </div>

        <KwFuss stand={stand()} links={[{ href: "/kommunalwahl", label: "Zurück zum Überblick" }]} />
      </main>
    </>
  );
}
