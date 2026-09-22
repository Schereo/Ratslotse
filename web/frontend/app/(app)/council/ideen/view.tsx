"use client";

/**
 * „Ideen aus anderen Städten" — was andere Räte beschlossen haben und
 * Oldenburg fehlt.
 *
 * **Zwei Zustände, eine Route.** Ohne `?feld=` die Übersicht über die
 * Themenfelder, mit `?feld=` die Liste darin. Ein Fließband über alle zwölf
 * Felder wäre eine Liste ohne Anfang; die Übersicht sagt zuerst, wo etwas
 * liegt.
 *
 * **Das Urteil steht mit seinen Belegen da.** Was das Modell über Oldenburg
 * sagt, ist nachprüfbar: Die Beschlüsse, auf die es sich stützt, stehen unter
 * der Karte und führen auf ihre Seite. Ohne sie wäre es eine Behauptung.
 *
 * **Keine Prozentzahl, kein Rang.** Wie sicher sich das Modell ist, steht als
 * Wort da, wo es etwas ändert — und sonst gar nicht.
 */
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowUpRight, Building2, ChevronLeft, ChevronRight, Search } from "lucide-react";

import { DecisionLinkCard, POLICY_FIELD_LABELS } from "@/components/decision-ui";
import { BewegungKarte, type Bewegung } from "@/components/ideen/bewegung-karte";
import { STAND } from "@/components/ideen/stand";
import { ZeitleisteLegende } from "@/components/ideen/zeitleiste";
import { Lotti } from "@/components/lotti";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import type { ApiAntwort } from "@/lib/vertrag";
import { useQuery } from "@tanstack/react-query";

type Felder = ApiAntwort<"/council/cities/ideas/fields">;
type Ideen = ApiAntwort<"/council/cities/ideas">;
type Suche = ApiAntwort<"/council/cities/search">;
type Bewegungen = ApiAntwort<"/council/cities/movements">;
type Idee = Ideen["items"][number];

/** Was das Urteil auf der Karte sagt — dieselben Stufen wie auf der Bewegung
 *  (`components/ideen/stand.tsx`). */
const STATUS = STAND;

/**
 * Was die Idee den Rat kosten würde — von der Frage bis zum Haushaltsposten.
 *
 * Knapp ein Drittel der Ideen sind Anfragen. „Eine Anfrage zu Fußwegbreiten
 * stellen" ist eine andere Sorte Vorschlag als „ein Darlehensprogramm
 * einführen", und wer die Liste liest, will das auf einen Blick sehen.
 */
// Wie die Haltung anderer Räte auf der Karte heißt. Drei Klassen und nicht
// fünf: `introduce` gegen `expand` war weder für das Modell noch für einen
// Menschen entscheidbar (gemessen 72 % gegen 87 %, s. `council/cities/
// annotators.py::IdeaStance`).
const HALTUNG: Record<string, { kurz: string; viele: (n: number) => string }> = {
  for: { kurz: "dafür", viele: (n) => `${n} dafür` },
  against: { kurz: "dagegen", viele: (n) => `${n} dagegen` },
  review: { kurz: "prüft erst", viele: (n) => `${n} prüfen erst` },
};

const AUFWAND: Record<string, string> = {
  inquiry: "Anfrage",
  review: "Prüfauftrag",
  resolution: "Resolution",
  decision: "Beschluss",
  budget: "kostet Geld",
};

/** Vorlagenarten — kurz, wie im Block „Anderswo beschlossen". */
const ART: Record<string, string> = {
  motion: "Antrag", amendment: "Änderungsantrag", inquiry: "Anfrage",
  answer: "Antwort", proposal: "Beschlussvorlage", report: "Bericht",
  notice: "Mitteilung", petition: "Eingabe",
};

function datum(iso: string | null): string {
  if (!iso) return "";
  const [j, m, t] = iso.slice(0, 10).split("-");
  return `${t}.${m}.${j}`;
}

// ------------------------------------------------------------- Übersicht

function Uebersicht({ felder, onFeld }: { felder: Felder | undefined; onFeld: (f: string) => void }) {
  const liste = felder?.fields ?? [];
  if (!felder) return null;
  if (!liste.length) {
    return (
      <p className="text-sm text-muted-foreground">
        Noch keine Ideen eingelesen. Sobald der wöchentliche Abgleich mit den
        anderen Städten gelaufen ist, steht hier etwas.
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {liste.map((f) => (
        <button
          key={f.field}
          type="button"
          onClick={() => onFeld(f.field)}
          className="text-left"
        >
          <Card className="card-interactive h-full p-4">
            <div className="text-sm font-semibold text-foreground">
              {POLICY_FIELD_LABELS[f.field] ?? f.field}
            </div>
            <div className="mt-2 text-2xl font-semibold tabular-nums text-primary">
              {f.total}
            </div>
            <div className="text-xs text-muted-foreground">
              {f.total === 1 ? "Idee aus einer anderen Stadt" : "Ideen aus anderen Städten"}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              {f.missing + f.partial} fehlen ganz oder halb · {f.present} hat Oldenburg schon
            </div>
          </Card>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------ Eine Karte

/**
 * „Stimmt" / „Stimmt nicht" — ein Klick, der den Maßstab baut.
 *
 * Jedes Urteil des Städtevergleichs wird gegen vierzig Fälle gemessen, die
 * EIN Mensch an einem Tag beurteilt hat — und in vier von sieben Pull
 * Requests war genau dieser Maßstab der Fehler, nicht das Modell.
 * Vierhundert Rückmeldungen von zwei Ratsmitgliedern wären ein besserer.
 *
 * Bewusst leise: zwei Wörter am Fuß der Karte, keine Sterne, keine Skala.
 * Wer nichts sagen will, sieht fast nichts.
 */
function Rueckmeldung({ idee }: { idee: Idee }) {
  const [gesagt, setGesagt] = useState(idee.feedback);
  const [fehler, setFehler] = useState(false);

  async function sagen(verdict: "right" | "wrong") {
    const neu = gesagt === verdict ? "" : verdict;
    setGesagt(neu);
    setFehler(false);
    if (!neu) return;
    try {
      await api.post(
        `/council/cities/ideas/${encodeURIComponent(idee.paper_id)}/feedback?verdict=${verdict}`,
      );
    } catch {
      // Ohne Konto geht es nicht, und das ist der Punkt: Eine Rückmeldung,
      // die sich nicht zählen lässt, ist kein Maßstab. Ein Hinweis statt
      // eines stillen Fehlschlags.
      setGesagt("");
      setFehler(true);
    }
  }

  return (
    <div className="mt-2 flex items-center gap-3 text-[11px]">
      <span className="text-muted-foreground/70">Stimmt das?</span>
      {(["right", "wrong"] as const).map((wert) => (
        <button
          key={wert}
          type="button"
          onClick={() => sagen(wert)}
          aria-pressed={gesagt === wert}
          className={
            gesagt === wert
              ? "font-medium text-primary"
              : "text-muted-foreground/70 hover:text-foreground"
          }
        >
          {wert === "right" ? "Ja" : "Nein"}
        </button>
      ))}
      {fehler && (
        <span className="text-muted-foreground/70">Dafür braucht es ein Konto.</span>
      )}
    </div>
  );
}

/** „3/2" → „2 von 3 Vorlagen"; leer, wenn es nur eine gibt oder keine Gruppe. */
function stimmen(votes: string | undefined): string {
  const [alle, dafuer] = (votes ?? "").split("/").map(Number);
  if (!alle || alle < 2 || !dafuer) return "";
  return `${dafuer} von ${alle} Vorlagen`;
}

function Haltungen({ idee }: { idee: Idee }) {
  // Wie die ANDEREN Räte zu derselben Sache stehen. Ohne diese Zeile zählte
  // die Karte eine Stadt für eine Idee, die sie gerade gestoppt hat: Die
  // Verpackungssteuer wurde in zwei von fünf Räten nicht eingeführt,
  // sondern die Prüfung eingestellt.
  const zaehler = Object.entries(idee.peer_stances ?? {})
    .filter(([wert, n]) => HALTUNG[wert] && n > 0)
    .sort((a, b) => b[1] - a[1]);
  if (zaehler.length === 0) return null;
  const dagegen = (idee.peer_stances ?? {}).against ?? 0;
  return (
    <p className="mt-1 text-xs text-muted-foreground">
      In den anderen Räten:{" "}
      {zaehler.map(([wert, n], i) => (
        <span key={wert}>
          {i > 0 && ", "}
          <span className={wert === "against" ? "font-medium text-foreground" : undefined}>
            {HALTUNG[wert].viele(n)}
          </span>
        </span>
      ))}
      {dagegen > 0 && "."}
    </p>
  );
}

/** Woher die Karte ihr Wissen über diese Stadt hat — und woher nicht.
 *
 * **Drei Zustände, nicht zwei.** „Kein Warum" heißt bei Magdeburg, dass die
 * Protokolle nicht abrufbar sind; bei Hannover, dass die Stadt ihre
 * Beratungsergebnisse ausdrücklich zurückhält. Wer beides gleich darstellt,
 * lässt eine Entscheidung der Stadt wie eine Lücke in unseren Daten aussehen.
 */
const NIEDERSCHRIFTEN: Record<string, string> = {
  available: "mit Niederschriften",
  none: "ohne Niederschriften",
  withheld: "Niederschriften nicht öffentlich",
};

function Herkunft({ idee }: { idee: Idee }) {
  const teile = [
    // „Vergleich ab", nicht „Beschlüsse ab": Das Fenster gehört der STADT,
    // nicht dieser Vorlage. Die Suche findet auch ältere — eine Hannoveraner
    // von 2021 unter der Zeile „Beschlüsse ab 2023" widerspricht sich selbst.
    idee.window_since ? `Vergleich ab ${idee.window_since.slice(0, 4)}` : null,
    NIEDERSCHRIFTEN[idee.protocol_source] ?? null,
  ].filter(Boolean);
  if (teile.length === 0) return null;
  return (
    <p className="mt-0.5 text-[11px] text-muted-foreground/80">{teile.join(" · ")}</p>
  );
}

function IdeenKarte({ idee }: { idee: Idee }) {
  const status = STATUS[idee.status];
  const kopf = [ART[idee.kind] ?? null, datum(idee.date)].filter(Boolean).join(" · ");
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-foreground">
          <Building2 className="h-3 w-3 text-muted-foreground" aria-hidden />
          {idee.body_name}
        </span>
        {kopf && <span className="text-xs text-muted-foreground">{kopf}</span>}
        {idee.originator && (
          <span className="text-xs text-muted-foreground/80">{idee.originator}</span>
        )}
        {/* Aufwand und Verbreitung: zwei Wörter, die den Rest der Karte
            einordnen. Sie stehen als leises Etikett neben der Herkunft, nicht
            als Auszeichnung — die Aussage macht das Urteil weiter unten. */}
        {AUFWAND[idee.effort] && (
          <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
            {AUFWAND[idee.effort]}
          </span>
        )}
        {idee.peers > 0 && (
          <span className="text-[11px] text-muted-foreground">
            {idee.peers === 1 ? "auch in 1 anderen Stadt" : `auch in ${idee.peers} anderen Städten`}
          </span>
        )}
        {(idee.siblings ?? []).length > 0 && (
          <span className="text-[11px] text-muted-foreground/80">
            {(idee.siblings ?? []).length === 1
              ? "1 weitere Vorlage dazu"
              : `${(idee.siblings ?? []).length} weitere Vorlagen dazu`}
          </span>
        )}
      </div>
      <Herkunft idee={idee} />

      {/* Die Überschrift ist die IDEE, nicht der Aktenname.
 
          Hier stand bis 14.09.2026 `idee.name` — der Rohtitel aus dem
          Ratsinformationssystem. Der ist für die Akte geschrieben, nicht
          zum Überfliegen: „Erneute Änderung der Parkgebührenordnung -
          kostenfreies Parken auf dem Wallring und an Samstagen, Einführung
          einer ‚Brötchentaste'". Wer zwanzig solcher Zeilen untereinander
          liest, sieht nicht, worum es geht.
 
          `instrument` sagt dasselbe in drei Wörtern — „Parkgebührenordnung
          ändern", „Feierabend-Parken pilotieren", „Barrierefreie
          Bordabsenkungen umsetzen" — und steht schon im Vertrag; es wurde
          nur nie gezeigt. Der Aktenname bleibt darunter stehen: Er ist das,
          wonach man im fremden System sucht, und der Beleg dafür, dass die
          kurze Zeile nicht erfunden ist. */}
      <h3 className="mt-1.5 text-sm font-semibold text-foreground">
        {idee.instrument || idee.name}
      </h3>
      {idee.instrument && idee.name && (
        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground/70">
          {idee.name}
        </p>
      )}
      {/* Die eigene Haltung, aber nur wenn sie GEGEN die Sache geht. „Dafür"
          ist der Normalfall und steht schon im Titel; „dagegen" dreht die
          Bedeutung der ganzen Karte um: Magdeburgs „Einwegverpackungsabgabe
          nicht umsetzen!" ist keine Idee, die Oldenburg fehlt.
 
          Ein Wort und kein Satz, weil `against` von „abschaffen" bis
          „verschieben" reicht. „Diese Vorlage will die Sache nicht" stand
          hier zuerst und war für Potsdams Verschiebung der Verpackungssteuer
          schlicht falsch — sie will die Steuer, nur später. Was die Vorlage
          genau bremst, sagt die Zusammenfassung darunter. */}
      {idee.stance === "against" && (
        <span className="mt-1 inline-block rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-foreground">
          Gegenrichtung
        </span>
      )}
      <Haltungen idee={idee} />
      {idee.summary && (
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{idee.summary}</p>
      )}

      {/* Das Urteil. Anzeigetafel-Tönung, nie eine dunkle Karte im Hellmodus. */}
      <div className="mt-3 rounded-lg bg-muted/50 p-3">
        <div className="flex flex-wrap items-center gap-2">
          {status && (
            <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${status.ton}`}>
              {status.text}
            </span>
          )}
          {/* „3/2": drei Vorlagen dieser Stadt, zwei tragen den Status. Das Urteil
              ist die MEHRHEIT, nicht das der einen gezeigten Vorlage — gemessen
              widersprach bei 14 Gruppen die jüngste ihrer Mehrheit. */}
          {stimmen(idee.votes) && (
            <span className="text-xs text-muted-foreground/70">{stimmen(idee.votes)}</span>
          )}
          {idee.confidence === "low" && (
            <span className="text-xs text-muted-foreground/70">unsicher</span>
          )}
        </div>
        {idee.reason && (
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{idee.reason}</p>
        )}
        {idee.addressee && (
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground/80">
            Entscheidet nicht die Stadt allein: {idee.addressee}
          </p>
        )}
        <Rueckmeldung idee={idee} />
      </div>

      {/* Das „Warum" aus der Niederschrift. Steht nur da, wenn im Protokoll
          wirklich eine Begründung steht — der Annotator sagt das mit
          `grounded`, und das Backend gibt sonst `null`. Ein „Warum", das aus
          dem Ergebnis erschlossen wäre, ist eine Behauptung über einen echten
          Ratsbeschluss; lieber eine Leerstelle. */}
      {idee.protocol && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            Warum es in {idee.body_name} so ausging
          </summary>
          <div className="mt-1.5 space-y-1.5 border-l-2 border-border pl-3">
            {idee.protocol.decided && (
              <p className="text-xs leading-relaxed text-foreground">
                {idee.protocol.decided}
                {idee.protocol.vote && (
                  <span className="ml-1.5 rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                    {idee.protocol.vote}
                  </span>
                )}
              </p>
            )}
            <p className="text-xs leading-relaxed text-muted-foreground">
              {idee.protocol.why}
            </p>
            {idee.protocol.discussed && (
              <p className="text-xs leading-relaxed text-muted-foreground/80">
                {idee.protocol.discussed}
              </p>
            )}
            <p className="text-[11px] text-muted-foreground/70">
              aus der Niederschrift
              {idee.protocol.organization ? ` des ${idee.protocol.organization}` : ""}
              {idee.protocol.date ? ` vom ${datum(idee.protocol.date)}` : ""}
            </p>
          </div>
        </details>
      )}

      {(idee.siblings ?? []).length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            {idee.body_name} hat die Sache {(idee.siblings ?? []).length + 1}-mal behandelt
          </summary>
          <ul className="mt-1.5 space-y-1">
            {(idee.siblings ?? []).map((g) => (
              <li key={g.paper_id} className="text-xs text-muted-foreground/80">
                {datum(g.date)} · {g.name}
              </li>
            ))}
          </ul>
        </details>
      )}

      {idee.evidence.length > 0 && (
        <div className="mt-3">
          <div className="text-xs font-medium text-muted-foreground">
            Worauf sich das stützt
          </div>
          <div className="mt-1.5 space-y-1.5">
            {idee.evidence.map((b) =>
              b.decision_id ? (
                <DecisionLinkCard
                  key={b.kvonr}
                  id={b.decision_id}
                  title={b.title}
                  session_date={b.date}
                />
              ) : (
                <p key={b.kvonr} className="text-xs text-muted-foreground">{b.title}</p>
              ),
            )}
          </div>
        </div>
      )}

      {idee.web && (
        <a
          href={idee.web}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          Im Ratsinformationssystem von {idee.body_name}
          <ArrowUpRight className="h-3 w-3" aria-hidden />
        </a>
      )}
    </Card>
  );
}


// -------------------------------------------------------------- Ein Feld

function Feld({ feld, zurueck }: { feld: string; zurueck: () => void }) {
  const { data, isPending } = useQuery({
    queryKey: ["ideen", feld],
    queryFn: () => api.get<Ideen>(`/council/cities/ideas?field=${encodeURIComponent(feld)}`),
    staleTime: 60 * 60 * 1000,
  });

  const label = POLICY_FIELD_LABELS[feld] ?? feld;
  return (
    <div>
      <button
        type="button"
        onClick={zurueck}
        className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-3 w-3" aria-hidden />
        Alle Themenfelder
      </button>
      <h3 className="mt-2 text-lg font-semibold text-foreground">{label}</h3>
      {!isPending && (
        <p className="text-xs text-muted-foreground">
          {data?.total ?? 0} Ideen aus anderen Städten. Zuerst, was mehrere
          Räte beschlossen haben und Oldenburg fehlt.
        </p>
      )}
      <div className="mt-4 space-y-3">
        {(data?.items ?? []).map((i) => (
          <IdeenKarte key={i.paper_id} idee={i} />
        ))}
      </div>
      {!isPending && !(data?.items ?? []).length && (
        <p className="mt-4 text-sm text-muted-foreground">
          In diesem Themenfeld ist noch nichts geprüft.
        </p>
      )}
    </div>
  );
}

// --------------------------------------------------------------- Suche

function Suchergebnis({ frage }: { frage: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["ideen-suche", frage],
    queryFn: () => api.get<Suche>(`/council/cities/search?q=${encodeURIComponent(frage)}`),
    staleTime: 60 * 60 * 1000,
  });
  return (
    <div>
      {!isPending && (
        <p className="text-xs text-muted-foreground">
          {data?.total ?? 0} einzelne Vorlagen zu „{frage}" in den
          Ratsinformationssystemen der anderen Städte.
        </p>
      )}
      <div className="mt-4 space-y-3">
        {(data?.items ?? []).map((i) => (
          <IdeenKarte key={i.paper_id} idee={i} />
        ))}
      </div>
      {!isPending && !(data?.items ?? []).length && (
        <p className="mt-4 text-sm text-muted-foreground">
          Dazu haben die anderen Städte nichts — jedenfalls nicht mit diesen Wörtern.
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------- Bewegungen

/** Der Stand in Oldenburg als Filter. „Noch offen" ist die Vorgabe: Was
 *  Oldenburg schon hat, gehört zur Antwort, aber nicht in die erste Ansicht. */
const STAENDE: { wert: string; text: string; zaehlt: string[] }[] = [
  { wert: "offen", text: "Noch offen", zaehlt: ["missing", "partial"] },
  { wert: "vorhanden", text: "Hat Oldenburg", zaehlt: ["present"] },
  { wert: "alle", text: "Alle", zaehlt: [] },
];
const STAND_PARAM: Record<string, string> = {
  offen: "missing,partial",
  vorhanden: "present",
  alle: "",
};

const PRO_SEITE = 12;

/** Der Zustand der Übersicht steht in der ADRESSE, nicht im Speicher: Wer
 *  von einer Ideen-Seite zurückkommt, findet Feld, Filter und Suche wieder,
 *  und ein geteilter Link zeigt dasselbe. */
type Zustand = { feld: string; stand: string; q: string; sort: string; seite: number };

function zustandAus(params: URLSearchParams | null): Zustand {
  const stand = params?.get("stand") ?? "offen";
  return {
    feld: params?.get("feld") ?? "",
    stand: STAND_PARAM[stand] !== undefined ? stand : "offen",
    q: params?.get("q") ?? "",
    sort: params?.get("sort") === "zuletzt" ? "zuletzt" : "staedte",
    seite: Math.max(1, Number(params?.get("seite") ?? "1") || 1),
  };
}

function adresse(z: Zustand): string {
  const p = new URLSearchParams();
  if (z.feld) p.set("feld", z.feld);
  if (z.stand !== "offen") p.set("stand", z.stand);
  if (z.q) p.set("q", z.q);
  if (z.sort !== "staedte") p.set("sort", z.sort);
  if (z.seite > 1) p.set("seite", String(z.seite));
  const s = p.toString();
  return s ? `/council/ideen?${s}` : "/council/ideen";
}

function bewegungsAnfrage(z: Zustand, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams({
    oldenburg: STAND_PARAM[z.stand],
    sort: z.sort,
    page: String(z.seite),
    per_page: String(PRO_SEITE),
    ...extra,
  });
  if (z.feld) p.set("field", z.feld);
  if (z.q) p.set("q", z.q);
  return `/council/cities/movements?${p.toString()}`;
}

function zielFuer(b: Bewegung, z: Zustand): string {
  const von = adresse(z).split("?")[1] ?? "";
  return `/council/ideen/bewegung?id=${b.cluster_id}${von ? `&von=${encodeURIComponent(von)}` : ""}`;
}

/** „Gerade in Bewegung": die großen — ab fünf Städten, Oldenburg noch offen,
 *  die zuletzt bewegten zuerst. Nach „meiste Städte" sortiert zeigte sie
 *  dieselben drei Karten, mit denen die Liste darunter beginnt.
 *
 *  Anzeigetafel, hell getönt, nie eine dunkle Karte im Hellmodus (Tims
 *  Regel). Sie steht nur in der ungefilterten Ansicht: Mit einem Feld oder
 *  einer Suche gewählt wäre sie eine zweite, kleinere Kopie der Liste. */
function Tafel({ zustand }: { zustand: Zustand }) {
  const { data } = useQuery({
    queryKey: ["bewegungen-tafel"],
    queryFn: () =>
      api.get<Bewegungen>(
        "/council/cities/movements?min_cities=5&oldenburg=missing,partial&sort=zuletzt&per_page=3"),
    staleTime: 60 * 60 * 1000,
  });
  if (!data || data.items.length === 0) return null;
  return (
    <section aria-labelledby="tafel-titel" className="hh-tafel grid gap-3.5 rounded-[18px] p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id="tafel-titel" className="font-display text-[19px] font-bold text-foreground">
          Gerade in Bewegung
        </h2>
        <span className="text-sm text-muted-foreground">
          Zuletzt beraten: Ideen aus fünf und mehr Räten, die Oldenburg nicht oder nur halb hat
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {data.items.map((b) => (
          <BewegungKarte
            key={b.cluster_id}
            bewegung={b}
            achse={data.axis}
            href={zielFuer(b, zustand)}
            gross
          />
        ))}
      </div>
      <ZeitleisteLegende />
    </section>
  );
}

function Chip({
  an, onClick, children, zahl,
}: { an: boolean; onClick: () => void; children: React.ReactNode; zahl?: number }) {
  return (
    <button
      type="button"
      aria-pressed={an}
      onClick={onClick}
      className={
        "inline-flex flex-none items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-sm transition-colors duration-tipp " +
        (an
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-foreground hover:border-primary/30")
      }
    >
      {children}
      {zahl !== undefined && (
        <span className={"font-mono text-xs " + (an ? "opacity-85" : "text-muted-foreground")}>
          {zahl}
        </span>
      )}
    </button>
  );
}

function Steuerung({
  zustand, setze, felder, zaehler,
}: {
  zustand: Zustand;
  setze: (z: Partial<Zustand>) => void;
  felder: Felder | undefined;
  zaehler: Record<string, number> | undefined;
}) {
  const [text, setText] = useState(zustand.q);
  useEffect(() => setText(zustand.q), [zustand.q]);
  const mitBewegungen = (felder?.fields ?? []).filter((f) => f.movements > 0)
    .sort((a, b) => b.movements - a.movements);
  const alle = mitBewegungen.reduce((n, f) => n + f.movements, 0);
  const zahlFuer = (zaehlt: string[]) =>
    zaehler
      ? (zaehlt.length ? zaehlt : Object.keys(zaehler)).reduce((n, k) => n + (zaehler[k] ?? 0), 0)
      : undefined;
  return (
    <div className="grid gap-3">
      <div
        className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 [mask-image:linear-gradient(90deg,#000_92%,transparent)] [scrollbar-width:thin]"
        role="group"
        aria-label="Themenfeld"
      >
        <Chip an={!zustand.feld} onClick={() => setze({ feld: "", seite: 1 })} zahl={alle || undefined}>
          Alle Felder
        </Chip>
        {mitBewegungen.map((f) => (
          <Chip
            key={f.field}
            an={zustand.feld === f.field}
            onClick={() => setze({ feld: f.field, seite: 1 })}
            zahl={f.movements}
          >
            {POLICY_FIELD_LABELS[f.field] ?? f.field}
          </Chip>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        <div
          role="group"
          aria-label="Stand in Oldenburg"
          className="inline-flex rounded-full border border-border bg-card p-[3px]"
        >
          {STAENDE.map((s) => (
            <button
              key={s.wert}
              type="button"
              aria-pressed={zustand.stand === s.wert}
              onClick={() => setze({ stand: s.wert, seite: 1 })}
              className={
                "rounded-full px-3 py-1 text-sm transition-colors duration-tipp " +
                (zustand.stand === s.wert
                  ? "bg-primary/10 font-semibold text-primary"
                  : "text-muted-foreground hover:text-foreground")
              }
            >
              {s.text}
              {zahlFuer(s.zaehlt) !== undefined && (
                <span className="ml-1.5 font-mono text-xs">{zahlFuer(s.zaehlt)}</span>
              )}
            </button>
          ))}
        </div>
        <form
          role="search"
          className="relative min-w-0 flex-[1_1_220px]"
          onSubmit={(e) => { e.preventDefault(); setze({ q: text.trim(), seite: 1 }); }}
        >
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Was haben andere Städte zu …?"
            aria-label="Ideen anderer Städte durchsuchen"
            className="h-10 w-full rounded-full border border-border bg-card pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </form>
        <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <span className="sr-only sm:not-sr-only">Sortieren</span>
          <select
            value={zustand.sort}
            onChange={(e) => setze({ sort: e.target.value, seite: 1 })}
            className="h-10 rounded-full border border-border bg-card px-3 text-sm text-foreground"
          >
            <option value="staedte">meiste Städte</option>
            <option value="zuletzt">zuletzt bewegt</option>
          </select>
        </label>
      </div>
    </div>
  );
}

function Leer({ gefiltert, zuruecksetzen }: { gefiltert: boolean; zuruecksetzen: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-[18px] border-2 border-dashed border-border px-4 py-8 text-center">
      <Lotti regung="sucht" className="h-20 w-20" decorative />
      <p className="max-w-prose text-sm text-muted-foreground">
        {gefiltert
          ? "Unter diesen Filtern gibt es keine Idee, die mehrere Räte hatten."
          : "Noch keine Bewegungen — sobald der Abgleich mit den anderen Städten gelaufen ist, stehen sie hier."}
      </p>
      {gefiltert && (
        <button type="button" onClick={zuruecksetzen} className="text-sm font-semibold text-primary hover:underline">
          Filter zurücksetzen
        </button>
      )}
    </div>
  );
}

function Blaettern({
  seite, gesamt, setze,
}: { seite: number; gesamt: number; setze: (z: Partial<Zustand>) => void }) {
  const seiten = Math.max(1, Math.ceil(gesamt / PRO_SEITE));
  if (seiten <= 1) return null;
  const knopf =
    "inline-flex h-10 items-center gap-1 rounded-full border border-border bg-card px-4 text-sm font-medium text-foreground disabled:opacity-40 enabled:hover:border-primary/30";
  return (
    <nav aria-label="Seiten" className="flex items-center justify-center gap-3">
      <button type="button" className={knopf} disabled={seite <= 1}
              onClick={() => setze({ seite: seite - 1 })}>
        <ChevronLeft className="h-4 w-4" aria-hidden /> Zurück
      </button>
      <span className="font-mono text-meta text-muted-foreground">
        Seite {seite} von {seiten}
      </span>
      <button type="button" className={knopf} disabled={seite >= seiten}
              onClick={() => setze({ seite: seite + 1 })}>
        Weiter <ChevronRight className="h-4 w-4" aria-hidden />
      </button>
    </nav>
  );
}

function BewegungenListe({
  zustand, setze, felder,
}: { zustand: Zustand; setze: (z: Partial<Zustand>) => void; felder: Felder | undefined }) {
  const { data, isPending } = useQuery({
    queryKey: ["bewegungen", zustand.feld, zustand.stand, zustand.q, zustand.sort, zustand.seite],
    queryFn: () => api.get<Bewegungen>(bewegungsAnfrage(zustand)),
    staleTime: 10 * 60 * 1000,
    placeholderData: (vorher) => vorher,
  });
  const gefiltert = Boolean(zustand.feld || zustand.q || zustand.stand !== "offen");
  return (
    <section aria-labelledby="bewegungen-titel" className="grid gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id="bewegungen-titel" className="font-display text-[19px] font-bold text-foreground">
          Ideen, die mehrere Räte hatten
        </h2>
        {data && (
          <span className="font-mono text-meta text-muted-foreground">
            {data.total} {data.total === 1 ? "Idee" : "Ideen"} · ab 2 Städten
          </span>
        )}
      </div>
      <Steuerung zustand={zustand} setze={setze} felder={felder} zaehler={data?.counts} />
      <ZeitleisteLegende />
      {isPending && !data ? null : data && data.items.length > 0 ? (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.items.map((b) => (
              <BewegungKarte key={b.cluster_id} bewegung={b} achse={data.axis} href={zielFuer(b, zustand)} />
            ))}
          </div>
          <Blaettern seite={zustand.seite} gesamt={data.total} setze={setze} />
        </>
      ) : (
        <Leer gefiltert={gefiltert} zuruecksetzen={() => setze({ feld: "", stand: "offen", q: "", seite: 1 })} />
      )}
    </section>
  );
}

// ---------------------------------------------------------------- Seite

export default function View() {
  const an = useFeature("ideen-anderswo");
  const router = useRouter();
  const params = useSearchParams();
  const zustand = useMemo(() => zustandAus(params), [params]);
  const setze = (neu: Partial<Zustand>) =>
    router.replace(adresse({ ...zustand, ...neu }), { scroll: false });
  const { data: felder } = useQuery({
    queryKey: ["ideen-felder"],
    queryFn: () => api.get<Felder>("/council/cities/ideas/fields"),
    staleTime: 60 * 60 * 1000,
  });
  // „A, B und C" — die letzte mit „und", wie man es schreibt.
  const staedte = useMemo(() => {
    const namen = felder?.bodies ?? [];
    if (namen.length === 0) return "anderen Städten";
    if (namen.length === 1) return namen[0];
    return `${namen.slice(0, -1).join(", ")} und ${namen[namen.length - 1]}`;
  }, [felder]);

  if (!an) return null;
  const ungefiltert = !zustand.feld && !zustand.q;

  return (
    <div className="space-y-6">
      <div className="max-w-3xl">
        <h1 className="font-display text-[28px] font-bold leading-tight text-foreground sm:text-[34px]">
          Ideen aus anderen Städten
        </h1>
        <p className="mt-2 text-lese text-foreground/90">
          {/* Die Städte kommen aus den DATEN, nicht aus diesem Satz. Fest
              aufgezählt stand hier bis zum 13.09.2026 „Osnabrück,
              Braunschweig, Münster, Potsdam und Magdeburg" — und das war
              falsch, sobald Hannover, Wolfsburg und Hildesheim dazukamen. */}
          Was Räte in {staedte} beantragt und beschlossen haben — und ob
          Oldenburg dasselbe schon hat.
        </p>
        <p className="mt-2 text-hinweis text-muted-foreground">
          Den Stand in Oldenburg prüft ein Sprachmodell an Oldenburger
          Beschlüssen; sie stehen auf jeder Ideen-Seite. Ob sich ein Antrag
          lohnt, sagt hier bewusst niemand: Das hängt an Mehrheiten und
          Haushaltslage.
        </p>
      </div>

      {ungefiltert && zustand.stand === "offen" && <Tafel zustand={zustand} />}

      <BewegungenListe zustand={zustand} setze={setze} felder={felder} />

      {/* Die einzelnen Ideen: was bisher EIN anderer Rat hatte — und jede
          Vorlage einzeln. Sie bleiben (Tims Entscheidung vom 22.09.2026),
          stehen aber unter den Bewegungen: 89 % aller Ideen stehen nur in
          einer Stadt, und eine Stadt ist eine Beobachtung, noch kein Trend. */}
      <section aria-labelledby="einzeln-titel" className="grid gap-3 border-t border-border pt-6">
        <div>
          <h2 id="einzeln-titel" className="font-display text-[19px] font-bold text-foreground">
            Einzelne Ideen
          </h2>
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            Jede Vorlage für sich — auch, was bisher nur ein anderer Rat hatte.
          </p>
        </div>
        {zustand.q ? (
          <Suchergebnis frage={zustand.q} />
        ) : zustand.feld ? (
          <Feld feld={zustand.feld} zurueck={() => setze({ feld: "", seite: 1 })} />
        ) : (
          <Uebersicht felder={felder} onFeld={(f) => setze({ feld: f, seite: 1 })} />
        )}
      </section>
    </div>
  );
}
