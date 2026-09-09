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
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, Building2, ChevronLeft, Search } from "lucide-react";

import { DecisionLinkCard, POLICY_FIELD_LABELS } from "@/components/decision-ui";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import type { ApiAntwort } from "@/lib/vertrag";
import { useQuery } from "@tanstack/react-query";

type Felder = ApiAntwort<"/council/cities/ideas/fields">;
type Ideen = ApiAntwort<"/council/cities/ideas">;
type Suche = ApiAntwort<"/council/cities/search">;
type Idee = Ideen["items"][number];

/** Was das Urteil auf der Karte sagt.
 *
 *  Die Töne kommen aus derselben Palette wie „vertagt" und „umstritten"
 *  (`council-goals.tsx`, `decision-ui.tsx`) — Anzeigetafel-Tönung, nie eine
 *  dunkle Karte im Hellmodus. `bg-warning` gibt es in diesem Projekt nicht;
 *  die erste Fassung hier benutzte es und die Marke blieb ungetönt. */
const STATUS: Record<string, { text: string; ton: string }> = {
  missing: { text: "In Oldenburg nicht gefunden", ton: "bg-primary/10 text-primary" },
  partial: {
    text: "Teilweise vorhanden",
    ton: "bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300",
  },
  present: { text: "Oldenburg hat das", ton: "bg-muted text-muted-foreground" },
};

/**
 * Was die Idee den Rat kosten würde — von der Frage bis zum Haushaltsposten.
 *
 * Knapp ein Drittel der Ideen sind Anfragen. „Eine Anfrage zu Fußwegbreiten
 * stellen" ist eine andere Sorte Vorschlag als „ein Darlehensprogramm
 * einführen", und wer die Liste liest, will das auf einen Blick sehen.
 */
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

function Uebersicht() {
  const router = useRouter();
  const { data, isPending } = useQuery({
    queryKey: ["ideen-felder"],
    queryFn: () => api.get<Felder>("/council/cities/ideas/fields"),
    staleTime: 60 * 60 * 1000,
  });

  if (isPending) return null;
  const felder = data?.fields ?? [];
  if (!felder.length) {
    return (
      <p className="text-sm text-muted-foreground">
        Noch keine Ideen eingelesen. Sobald der wöchentliche Abgleich mit den
        anderen Städten gelaufen ist, steht hier etwas.
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {felder.map((f) => (
        <button
          key={f.field}
          type="button"
          onClick={() => router.push(`/council/ideen?feld=${f.field}`)}
          className="text-left"
        >
          <Card className="card-interactive h-full p-4">
            <div className="text-sm font-semibold text-foreground">
              {POLICY_FIELD_LABELS[f.field] ?? f.field}
            </div>
            {/* Die große Zahl ist eine TATSACHE: Ideen, die mehrere andere
                Städte haben und Oldenburg nicht. Vorher stand hier „Ideen,
                die sich lohnen könnten" — gezählt aus einem Werturteil, das
                das Modell zu 46–58 % traf. */}
            <div className="mt-2 text-2xl font-semibold tabular-nums text-primary">
              {f.multi_city}
            </div>
            <div className="text-xs text-muted-foreground">
              {f.multi_city === 1
                ? "Idee aus mehreren Städten, die Oldenburg fehlt"
                : "Ideen aus mehreren Städten, die Oldenburg fehlen"}
            </div>
            <div className="mt-2 text-xs text-muted-foreground/80">
              {f.missing + f.partial} fehlen ganz oder halb · {f.present} hat Oldenburg schon
            </div>
          </Card>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------ Eine Karte

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
      </div>

      <h3 className="mt-1.5 text-sm font-semibold text-foreground">{idee.name}</h3>
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
      </div>

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

function Feld({ feld }: { feld: string }) {
  const router = useRouter();
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
        onClick={() => router.push("/council/ideen")}
        className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-3 w-3" aria-hidden />
        Alle Themenfelder
      </button>
      <h2 className="mt-2 text-lg font-semibold text-foreground">{label}</h2>
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

/**
 * Eine Zeile, keine eigene Seite.
 *
 * Der Volltextindex hat kein Fenster nach vorn: Wer eine Sache im Kopf hat,
 * soll nicht erst das richtige Themenfeld raten müssen. Die Ergebnisse sehen
 * aus wie die Ideen darunter — es ist dieselbe Karte.
 */
function Suchzeile({ onTreffer }: { onTreffer: (q: string) => void }) {
  const [text, setText] = useState("");
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onTreffer(text.trim()); }}
      className="flex items-center gap-2"
    >
      <div className="relative flex-1">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Was haben andere Städte zu …?"
          aria-label="Ideen anderer Städte durchsuchen"
          className="h-10 w-full rounded-lg border border-border bg-card pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
    </form>
  );
}

function Suchergebnis({ frage, zurueck }: { frage: string; zurueck: () => void }) {
  const { data, isPending } = useQuery({
    queryKey: ["ideen-suche", frage],
    queryFn: () => api.get<Suche>(`/council/cities/search?q=${encodeURIComponent(frage)}`),
    staleTime: 60 * 60 * 1000,
  });
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
      <h2 className="mt-2 text-lg font-semibold text-foreground">„{frage}"</h2>
      {!isPending && (
        <p className="text-xs text-muted-foreground">
          {data?.total ?? 0} Treffer in den Ratsinformationssystemen der anderen Städte.
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

// ---------------------------------------------------------------- Seite

export default function View() {
  const an = useFeature("ideen-anderswo");
  const params = useSearchParams();
  const feld = useMemo(() => params?.get("feld") ?? null, [params]);
  const [frage, setFrage] = useState("");

  if (!an) return null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Ideen aus anderen Städten</h1>
        <p className="mt-1 max-w-prose text-sm text-muted-foreground">
          Was Räte in Osnabrück, Braunschweig, Münster, Potsdam und Magdeburg
          beschlossen haben — und ob Oldenburg dasselbe schon hat. Das prüft
          ein Sprachmodell an Oldenburger Beschlüssen; sie stehen unter jeder
          Idee. Ob sich ein Antrag lohnt, sagt hier bewusst niemand: Das hängt
          an Mehrheiten und Haushaltslage.
        </p>
      </div>
      <Suchzeile onTreffer={setFrage} />
      {frage
        ? <Suchergebnis frage={frage} zurueck={() => setFrage("")} />
        : feld
          ? <Feld feld={feld} />
          : <Uebersicht />}
    </div>
  );
}
