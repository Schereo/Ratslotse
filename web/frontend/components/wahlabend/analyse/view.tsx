"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { analysePfad, stimmenanteil, type Bezugsbasis, type StichwahlAnalyse } from "@/lib/stichwahl-analyse";
import { prozent, zahl } from "@/lib/wahlabend";
import { Kopf } from "@/components/wahlabend/kopf";
import { Segmented } from "@/components/ui/segmented";
import { Abschnitt, Erklaerung, Kennzahl, Quelle } from "./bausteine";
import { Historie } from "./historie";

function Ausgangslage({ p }: { p: StichwahlAnalyse }) {
  return (
    <Abschnitt id="erster-wahlgang" kicker="13. September 2026 · beobachtetes Ergebnis" titel="Was im ersten Wahlgang gezählt wurde">
      <Erklaerung>
        Ulf Prange und Jascha Rohr erreichten die Stichwahl. Ihr Abstand betrug {zahl(p.lead_votes)} Stimmen.
        Die folgende Tabelle bezieht jeden Anteil auf alle {zahl(p.totals.valid_votes)} gültigen Stimmen.
      </Erklaerung>
      <div className="overflow-x-auto rounded-xl border border-border bg-card px-4">
        <table className="w-full min-w-[20rem] text-left text-sm" data-testid="kandidaten-ergebnis">
          <caption className="sr-only">Ergebnis des ersten Wahlgangs 2026, Anteil an allen gültigen Stimmen</caption>
          <thead className="border-b border-border text-meta text-muted-foreground"><tr><th scope="col" className="py-3 pr-3">Kandidatur</th><th scope="col" className="p-3 text-right">Stimmen</th><th scope="col" className="py-3 pl-3 text-right">Anteil</th></tr></thead>
          <tbody className="divide-y divide-border">
            {p.candidates.map((c) => (
              <tr key={c.slug}>
                <th scope="row" className="py-3 pr-3 font-medium">{c.name}{c.in_runoff && <span className="block text-meta font-normal text-muted-foreground">in der Stichwahl</span>}{c.slug === "other" && <span className="block text-meta font-normal text-muted-foreground">zusammen als „Sonstige“ ausgewiesen</span>}</th>
                <td className="whitespace-nowrap p-3 text-right tabular-nums">{zahl(c.votes)}</td>
                <td className="whitespace-nowrap py-3 pl-3 text-right tabular-nums">{prozent(c.share_all_pct, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Erklaerung>
        Insgesamt gingen {zahl(p.eliminated_votes)} Stimmen an die sieben ausgeschiedenen Kandidaturen. Darin enthalten
        sind {zahl(p.grouped_other_votes)} Stimmen für Michael Stille und Yakup Castur, die die Bezirksdatei zusammenfasst.
        Wie diese Wählenden in der Stichwahl entscheiden und ob sie erneut teilnehmen, geht daraus nicht hervor.
      </Erklaerung>
      <Quelle href={p.source_url}>Quelle: OB-Wahl 2026 im Votemanager</Quelle>
    </Abschnitt>
  );
}

function Beteiligung({ p }: { p: StichwahlAnalyse }) {
  const t = p.totals;
  return (
    <Abschnitt id="wahlbeteiligung" kicker="Wahlbeteiligung · ganze Stadt" titel="Wie viele Menschen teilgenommen haben">
      <div className="grid gap-6 sm:grid-cols-3">
        <Kennzahl wert={zahl(t.urn_voters)} titel="an der Urne">Wählende in {p.urn_district_count} Urnenbezirken.</Kennzahl>
        <Kennzahl wert={zahl(t.postal_voters)} titel="per Brief">Wählende in {p.postal_district_count} Briefwahlbezirken.</Kennzahl>
        <Kennzahl wert={zahl(t.non_voters)} titel="nicht teilgenommen">Wahlberechtigte abzüglich aller Wählenden, einschließlich Briefwahl.</Kennzahl>
      </div>
      <Erklaerung>
        {zahl(t.eligible)} Menschen waren wahlberechtigt. {zahl(t.voters)} nahmen teil, also {prozent(t.turnout_pct, 2)}.
        Unter den abgegebenen Stimmzetteln waren {zahl(t.invalid_ballots)} ungültige. Auch wer ungültig wählt, zählt zur Wahlbeteiligung.
      </Erklaerung>
      <p className="rounded-xl border border-border bg-card p-4 text-hinweis">
        <strong>Für einzelne Wohngebiete nicht bestimmbar:</strong> Die Briefwahl wird separat gezählt. Wer nur die
        Urnenwählenden von den Wahlberechtigten eines Bezirks abzieht, zählt Briefwählende fälschlich zu den Nichtwählenden.
        Ohne passende Zuordnung lässt sich deren Zahl je Urnenbezirk aus diesen Daten nicht ermitteln.
      </p>
    </Abschnitt>
  );
}

function Wahlarten({ p }: { p: StichwahlAnalyse }) {
  const [basis, setBasis] = useState<Bezugsbasis>("alle");
  return (
    <Abschnitt id="bezugsgrössen" kicker="Urne und Brief · Bezugsgröße wählen" titel="Wovon ist das ein Prozentanteil?">
      <Erklaerung>
        Derselbe Stimmenstand kann verschiedene Prozentwerte ergeben. Entscheidend ist, welche Stimmen im Nenner
        stehen. Wechsle die Bezugsgröße: Die Stimmenzahlen bleiben gleich, ihre Anteile ändern sich.
      </Erklaerung>
      <div className="overflow-x-auto pb-1"><Segmented<Bezugsbasis> value={basis} onChange={setBasis} options={[
        { value: "alle", label: "Alle gültigen Stimmen" }, { value: "finalisten", label: "Nur Prange und Rohr" },
      ]} /></div>
      <p aria-live="polite" className="text-hinweis" data-testid="bezugsbasis">
        {basis === "alle" ? "100 % = alle gültigen Stimmen der jeweiligen Wahlart, auch für ausgeschiedene Kandidaturen." : "100 % = nur die Stimmen für Prange und Rohr in der jeweiligen Wahlart. Die übrigen Kandidaturen sind herausgerechnet."}
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {p.voting_methods.map((m) => (
          <div key={m.name} className="rounded-xl border border-border bg-card p-4" data-testid={`wahlart-${m.name}`}>
            <h3 className="font-display text-lg font-bold">{m.name}</h3>
            <p className="mt-1 text-meta text-muted-foreground">Bezugsgröße: {zahl(basis === "alle" ? m.valid_votes : m.finalist_votes)} Stimmen</p>
            <dl className="mt-3 divide-y divide-border">
              {[...m.candidates].sort((a, b) => a.name.localeCompare(b.name, "de")).map((c) => (
                <div key={c.slug} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 py-3">
                  <dt className="font-medium">{c.name}</dt>
                  <dd className="text-right tabular-nums"><strong className="font-display text-xl">{prozent(stimmenanteil(c.votes, m.valid_votes, m.finalist_votes, basis))}</strong><span className="ml-3 text-meta text-muted-foreground">{zahl(c.votes)} Stimmen</span></dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
      <Erklaerung>
        Die Zweieranteile sind keine Vorhersage für die Stichwahl. Sie lassen die übrigen Kandidaturen lediglich aus
        dem Nenner weg. Unterschiede zwischen Brief- und Urnenwahl zeigen außerdem keine Wirkung der Wahlart auf die
        politische Entscheidung: Es können unterschiedlich zusammengesetzte Gruppen gewählt haben.
      </Erklaerung>
    </Abschnitt>
  );
}

function Ratswahl({ p }: { p: StichwahlAnalyse }) {
  const c = p.council;
  return (
    <Abschnitt id="ratswahl" kicker={`Ratswahl ${c.year} · andere Einheit`} titel="Stimmen sind nicht immer Personen">
      <Erklaerung>
        Bei der Ratswahl kann jede Person bis zu drei Stimmen vergeben und auf Listen oder Personen verteilen.
        Bei der OB-Wahl hat jede Person eine Stimme. Ratswahlstimmen sind deshalb keine „Zweitstimmen“ und keine
        zusätzliche Gruppe von OB-Wählenden.
      </Erklaerung>
      <div className="rounded-xl border border-border bg-card p-4">
        <Kennzahl wert={zahl(c.cdu_votes)} titel={`Beispiel: CDU-Stimmen bei der Ratswahl ${c.year}`}>
          {zahl(c.cdu_list_votes)} Listenstimmen + {zahl(c.cdu_candidate_votes)} Personenstimmen.
          Daraus lässt sich keine genaue Zahl verschiedener Wählender ableiten – auch nicht durch pauschales Teilen durch drei.
        </Kennzahl>
      </div>
      <div className="flex flex-wrap gap-x-6"><Quelle href={c.source_url}>Quelle: Ratswahl {c.year}</Quelle><Quelle href="https://landeswahlleiter.niedersachsen.de/wahlen/kommunalwahlen/grundzuege_kommunalwahlsystem/grundzuge-des-niedersachsischen-kommunalwahlsystems-252504.html">So funktioniert das Dreistimmenwahlrecht</Quelle></div>
    </Abschnitt>
  );
}

function Begriffe() {
  return (
    <Abschnitt id="zahlen-verstehen" kicker="Zahlen einordnen" titel="Was die Kennzahlen sagen – und was offenbleibt">
      <dl className="grid gap-x-8 gap-y-6 sm:grid-cols-2">
        <div><dt className="font-semibold">Prozent oder Prozentpunkte?</dt><dd className="mt-2 text-hinweis text-muted-foreground">Ein Anstieg von 40 auf 50 Prozent sind 10 Prozentpunkte. Gegenüber dem Ausgangswert von 40 Prozent ist das ein relativer Anstieg um 25 Prozent. Die Begriffe beantworten verschiedene Fragen.</dd></div>
        <div><dt className="font-semibold">Ein größerer Faktor bedeutet nicht mehr Stimmen.</dt><dd className="mt-2 text-hinweis text-muted-foreground">100 → 220 Stimmen: Faktor 2,2, also 120 Prozent oder 120 Stimmen mehr. 1.000 → 1.550: Faktor 1,55, aber 550 Stimmen mehr. Deshalb stehen im historischen Vergleich Ausgangszahl, Endzahl und beide Veränderungen zusammen.</dd></div>
        <div><dt className="font-semibold">Korrelation beschreibt einen Zusammenhang.</dt><dd className="mt-2 text-hinweis text-muted-foreground">Ein Wert nahe null belegt keine gleichmäßige Verteilung. Ein negativer Wert ist keine Wechselquote. Aus Zusammenhängen zwischen Bezirken lassen sich weder individuelle Absichten noch die Wirkung eines Gesprächs ablesen.</dd></div>
        <div><dt className="font-semibold">Eine Annahme ist kein beobachtetes Ergebnis.</dt><dd className="mt-2 text-hinweis text-muted-foreground">Ein Szenario rechnet aus, was unter gewählten Voraussetzungen folgen würde. Es sagt nicht, wie wahrscheinlich diese Voraussetzungen sind. Ein Ergebnis mit vielen Nachkommastellen kann trotzdem auf unsicheren Annahmen beruhen.</dd></div>
      </dl>
      <Erklaerung>
        Diese Daten enthalten keine Messung von Haustürbesuchen, geführten Gesprächen oder dadurch veränderten
        Wahlentscheidungen. Eine Wirkung je Kontakt lässt sich daraus nicht bestimmen. Die historischen Veränderungen
        sind ebenfalls kein Nachweis dafür, dass Stimmen aus einer bestimmten Gruppe kamen.
      </Erklaerung>
      <p className="text-hinweis text-muted-foreground">Prozentwerte sind für die Anzeige gerundet. Summen der angezeigten Anteile können deshalb geringfügig von 100 Prozent abweichen.</p>
    </Abschnitt>
  );
}

export function StichwahlAnalyseView() {
  const token = useSearchParams().get("k") ?? "";
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ["stichwahl-analyse", token], queryFn: () => api.get<StichwahlAnalyse>(analysePfad(token)),
    enabled: !!token, retry: false, staleTime: 10 * 60_000,
  });
  const nichtGefunden = !token || (error instanceof ApiError && error.status === 404);
  return (
    <>
      <Kopf label="Stichwahl · Analyse" />
      <main className="mx-auto w-full max-w-4xl px-4 pb-20 hyphens-auto [overflow-wrap:anywhere] sm:px-6">
        {nichtGefunden ? (
          <div data-testid="analyse-fehlt" className="py-16"><h1 className="font-display text-2xl font-bold">Diese Seite wurde nicht gefunden.</h1><p className="mt-3 text-hinweis">Prüfe, ob der Link vollständig ist.</p></div>
        ) : <>
          {error && <div role="alert" className="mt-8 rounded-xl border border-border bg-card p-4"><p>Die Analyse konnte nicht geladen werden.{data ? " Der zuletzt geladene Stand bleibt sichtbar." : ""}</p><button type="button" disabled={isFetching} onClick={() => refetch()} className="mt-2 min-h-11 font-semibold text-primary">{isFetching ? "Lädt …" : "Erneut versuchen"}</button></div>}
          {!data && !error && <p role="status" className="py-16 text-hinweis">Wahlergebnisse werden geladen …</p>}
          {data && <>
            <header className="mt-8"><p className="font-mono text-meta text-muted-foreground">Oldenburg · Stichwahl 2026</p><h1 className="mt-2 font-display text-3xl font-bold tracking-tight sm:text-4xl">Die Zahlen hinter der Stichwahl</h1><p className="mt-4 max-w-[76ch] text-lese">Was der erste Wahlgang zeigt, wie frühere Stichwahlen verliefen und welche Schlüsse die Ergebnisse zulassen.</p><p className="mt-3 text-meta text-muted-foreground">{data.data_status} · {data.district_count} ausgezählte Bezirke</p></header>
            <div data-testid="analyse-tafel" className="hh-tafel mt-6 grid gap-6 rounded-2xl border p-5 sm:grid-cols-2 sm:p-6">
              <Kennzahl wert={zahl(data.totals.voters)} titel="Menschen haben gewählt">{prozent(data.totals.turnout_pct, 2)} der {zahl(data.totals.eligible)} Wahlberechtigten, einschließlich Briefwahl.</Kennzahl>
              <Kennzahl wert={zahl(data.eliminated_votes)} titel="Stimmen für ausgeschiedene Kandidaturen">Alle sieben weiteren Kandidaturen zusammen. Wie deren Wählende bei der Stichwahl entscheiden, ist offen.</Kennzahl>
            </div>
            <nav aria-label="Abschnitte der Analyse" className="mt-5 flex flex-wrap gap-x-5 gap-y-1 text-sm text-primary">{[["erster-wahlgang", "Ergebnis"], ["wahlbeteiligung", "Beteiligung"], ["bezugsgrössen", "Prozentangaben"], ["historischer-vergleich", "Historischer Vergleich"], ["zahlen-verstehen", "Zahlen verstehen"]].map(([id, text]) => <a key={id} href={`#${id}`} className="inline-flex min-h-11 items-center underline decoration-primary/30 underline-offset-4">{text}</a>)}</nav>
            <Ausgangslage p={data} /><Beteiligung p={data} /><Wahlarten p={data} /><Ratswahl p={data} /><Historie history={data.history} /><Begriffe />
            <footer className="mt-12 border-t border-border pt-5 text-hinweis text-muted-foreground">Auswertung öffentlicher Wahlergebnisse durch Ratslotse. Die Wahlzahlen stammen aus den verlinkten Quellen; Anteile und Veränderungen berechnet Ratslotse daraus. Für die Wahl vom {data.election_date.split("-").reverse().join(".")} wird ein eingefrorener Datenstand verwendet. Diese Seite enthält keine Umfrage und keine Prognose.</footer>
          </>}
        </>}
      </main>
    </>
  );
}
