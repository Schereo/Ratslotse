import type { StichwahlAnalyse } from "@/lib/stichwahl-analyse";
import { prozent, zahl } from "@/lib/wahlabend";
import { Abschnitt, Erklaerung, Kennzahl, Quelle } from "./bausteine";

function datum(iso: string): string {
  return iso.split("-").reverse().join(".");
}

export function Historie({ history }: { history: StichwahlAnalyse["history"] }) {
  return (
    <Abschnitt id="historischer-vergleich" kicker="2014 und 2021 · beobachtete Ergebnisse" titel="Wie sich die Beteiligung verändert hat">
      <Erklaerung>
        2014 nahmen an der Stichwahl weniger Menschen teil, 2021 mehr. Verglichen werden hier jeweils die Ergebnisse
        der gesamten Stadt einschließlich Briefwahl. Diese Gesamtzahlen zeigen nicht, welche Personen in beiden Wahlgängen gewählt haben.
      </Erklaerung>
      {history.map((h) => (
        <article key={h.year} data-testid={`historie-${h.year}`} className="rounded-2xl border border-border bg-card p-4 sm:p-6">
          <h3 className="font-display text-xl font-bold">{h.year}: {h.candidates.map((c) => c.name).join(" und ")}</h3>
          <p className="mt-1 text-meta text-muted-foreground">Erster Wahlgang {datum(h.first_date)} · Stichwahl {datum(h.runoff_date)}</p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <Kennzahl wert={`${zahl(h.first.voters)} → ${zahl(h.runoff.voters)}`} titel="Wählende in beiden Wahlgängen">
              {zahl(Math.abs(h.change_voters))} {h.change_voters < 0 ? "weniger" : "mehr"} Wählende,
              {h.change_voters_pct === null ? "relative Veränderung nicht bestimmbar." : <>also {prozent(Math.abs(h.change_voters_pct))} {h.change_voters < 0 ? "weniger" : "mehr"} als im ersten Wahlgang.</>}
            </Kennzahl>
            <Kennzahl wert={prozent(h.voter_count_ratio_pct)} titel="der ursprünglichen Wählendenzahl">
              Die Zahl der Wählenden in der Stichwahl geteilt durch die Zahl im ersten Wahlgang. Keine Quote der Menschen, die wiederkamen.
            </Kennzahl>
          </div>
          <p className="mt-5 text-hinweis">
            <strong>Wahlbeteiligung:</strong> {prozent(h.first.turnout_pct, 2)} → {prozent(h.runoff.turnout_pct, 2)} der
            jeweils Wahlberechtigten.{" "}
            {h.turnout_change_pp === null ? "Die Veränderung ist nicht bestimmbar." : <>Das sind {Math.abs(h.turnout_change_pp).toLocaleString("de-DE", { maximumFractionDigits: 2 })} Prozentpunkte {h.turnout_change_pp < 0 ? "weniger" : "mehr"}.</>}
          </p>
          <p className="mt-3 max-w-[76ch] text-hinweis text-muted-foreground">{h.context}</p>
          <details className="mt-4 border-t border-border pt-2">
            <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-primary">Stimmenzahlen und Wachstum beider Kandidaten</summary>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <caption className="py-3 text-left text-hinweis text-muted-foreground">
                  Stadtweite Stimmen, einschließlich Briefwahl. Der Zuwachs zeigt keine Herkunft der Stimmen.
                </caption>
                <thead className="border-b border-border text-meta text-muted-foreground">
                  <tr><th scope="col" className="py-2 pr-4">Kandidat</th><th scope="col" className="p-2 text-right">1. Wahlgang</th><th scope="col" className="p-2 text-right">Stichwahl</th><th scope="col" className="p-2 text-right">Veränderung</th><th scope="col" className="p-2 text-right">Faktor</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {h.candidates.map((c) => (
                    <tr key={c.name}>
                      <th scope="row" className="py-3 pr-4 font-medium">{c.name}</th>
                      <td className="whitespace-nowrap p-2 text-right tabular-nums">{zahl(c.first_votes)}</td>
                      <td className="whitespace-nowrap p-2 text-right tabular-nums">{zahl(c.runoff_votes)}</td>
                      <td className="p-2 text-right tabular-nums"><span className="whitespace-nowrap">{c.change_votes >= 0 ? "+" : ""}{zahl(c.change_votes)}</span><span className="block whitespace-nowrap text-meta text-muted-foreground">{c.change_pct !== null && c.change_pct >= 0 ? "+" : ""}{prozent(c.change_pct)}</span></td>
                      <td className="whitespace-nowrap p-2 text-right tabular-nums">{c.growth_factor === null ? "nicht bestimmbar" : `× ${c.growth_factor.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-hinweis text-muted-foreground">Faktor = Stimmen in der Stichwahl ÷ Stimmen im ersten Wahlgang. Absolute und relative Veränderung beschreiben denselben Zuwachs mit verschiedenen Bezugsgrößen.</p>
          </details>
          <div className="mt-2 flex flex-wrap gap-x-6"><Quelle href={h.source_urls[0]}>Quelle: erster Wahlgang {h.year}</Quelle><Quelle href={h.source_urls[1]}>Quelle: Stichwahl {h.year}</Quelle></div>
        </article>
      ))}
      <Erklaerung>
        Aus den Zu- und Abnahmen lässt sich keine eindeutige Stimmenwanderung ableiten. Menschen können neu teilnehmen,
        fernbleiben, zwischen Kandidaturen wechseln oder ungültig wählen. Auch ein historischer Vergleich liefert deshalb
        keine gemessene Teilnahmequote einzelner politischer Gruppen für 2026.
      </Erklaerung>
      <Quelle href="https://www.bundeswahlleiterin.de/mitteilungen/bundestagswahlen/2021/20201214-wahltermin.html">Quelle: Termin der Bundestagswahl 2021</Quelle>
    </Abschnitt>
  );
}
