"use client";

/**
 * Die Ideen-Seite: EINE Idee, wie sie durch die Räte lief — und ob Oldenburg
 * sie hat.
 *
 * Adresse `?id=<cluster_id>` statt eines Pfadsegments: Der statische Export
 * kennt keine dynamischen Pfade (`web/frontend/CLAUDE.md`). `von` trägt den
 * Zustand der Übersicht (Feld, Filter, Suche), damit „Zurück" ihn wiederfindet
 * — in der Adresse, nicht im Speicher.
 *
 * **Beleg und Verwandtes stehen getrennt.** Im Entwurf stand beides unter
 * einer Überschrift, und unter „nicht gefunden" las sich ein verwandter
 * Beschluss wie der Beweis des Gegenteils. `evidence` stützt den Stand,
 * `related` ist Lesestoff und heißt auch so (Plan §2.10).
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ChevronLeft } from "lucide-react";

import { DecisionLinkCard, POLICY_FIELD_LABELS } from "@/components/decision-ui";
import { bilanz, zeitraum } from "@/components/ideen/bewegung-karte";
import { ErgebnisPille } from "@/components/ideen/ergebnis";
import { StandPille } from "@/components/ideen/stand";
import { Jahresskala, Zeitleiste, ZeitleisteLegende } from "@/components/ideen/zeitleiste";
import { Lotti } from "@/components/lotti";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import type { ApiAntwort } from "@/lib/vertrag";
import { satz } from "@/lib/zeitleiste";

type Detail = ApiAntwort<"/council/cities/movements/detail">;
type Dokument = Detail["documents"][number];
type Beleg = Detail["oldenburg_documents"][number];

const ART: Record<string, string> = {
  motion: "Antrag", amendment: "Änderungsantrag", inquiry: "Anfrage",
  proposal: "Beschlussvorlage",
};

/** So viele Vorlagen stehen zuerst da. Die Wärmeplanung hat 27 — ungekürzt
 *  war die Seite zwölf Bildschirme lang, und die Zeitleiste oben erzählt die
 *  Folge ohnehin schon. */
const CHRONIK_ERST = 10;

const NIEDERSCHRIFT: Record<string, string> = {
  none: "Zu dieser Sitzung liegt keine Niederschrift vor.",
  withheld: "Die Stadt veröffentlicht ihre Niederschriften nicht.",
  available: "",
};

function datum(iso: string | null | undefined): string {
  if (!iso) return "ohne Datum";
  const [j, m, t] = iso.slice(0, 10).split("-");
  return t ? `${t}.${m}.${j}` : iso;
}

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[11.5px] font-medium uppercase tracking-[0.07em] text-muted-foreground">
      {children}
    </div>
  );
}

// ------------------------------------------------------------- Bühne

/** Je Stadt eine Zeile auf der gemeinsamen Achse. */
function Buehne({ detail }: { detail: Detail }) {
  const b = detail.movement;
  return (
    <section
      aria-labelledby="buehne-titel"
      className="grid gap-3.5 rounded-[18px] border border-border bg-[hsl(var(--muted)/0.5)] p-4 sm:p-5"
    >
      <h2 id="buehne-titel" className="font-display text-base font-bold text-foreground">
        Wie die Idee durch die Räte lief
      </h2>
      <div className="grid gap-1">
        {b.cities.map((c) => {
          const punkte = b.timeline.filter((p) => p.body_id === c.body_id);
          return (
            <div key={c.body_id} className="grid grid-cols-[84px_minmax(0,1fr)] items-center gap-3 sm:grid-cols-[130px_minmax(0,1fr)]">
              <span className="truncate text-[13px] font-semibold text-foreground sm:text-sm" title={c.city}>
                {c.city}
              </span>
              <Zeitleiste
                achse={detail.axis}
                punkte={punkte}
                label={`${c.city}: ${satz(punkte)}`}
              />
            </div>
          );
        })}
        <div className="grid grid-cols-[84px_minmax(0,1fr)] gap-3 sm:grid-cols-[130px_minmax(0,1fr)]">
          <span />
          <Jahresskala achse={detail.axis} />
        </div>
      </div>
      <ZeitleisteLegende />
    </section>
  );
}

// ------------------------------------------------------------ Chronik

function Eintrag({ d }: { d: Dokument }) {
  const art = [ART[d.kind] ?? "Vorlage", d.originator].filter(Boolean).join(" · ");
  return (
    <li className="grid gap-1.5 border-t border-border/70 px-4 py-3.5 first:border-t-0 sm:grid-cols-[104px_minmax(0,1fr)] sm:gap-4">
      <div className="font-mono text-meta text-muted-foreground">
        <span className="block font-sans text-sm font-semibold text-foreground">{d.city}</span>
        {datum(d.date)}
      </div>
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <ErgebnisPille outcome={d.outcome} />
          <span className="font-mono text-meta text-muted-foreground">{art}</span>
        </div>
        <h3 className="text-quelle font-semibold text-foreground">
          {d.web ? (
            <a
              href={d.web}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary hover:underline"
            >
              {d.name}
              <ArrowUpRight className="ml-1 inline h-3.5 w-3.5 align-[-2px] text-muted-foreground" aria-label="(extern)" />
            </a>
          ) : (
            d.name
          )}
        </h3>
        {d.summary && <p className="text-lese text-foreground/90">{d.summary}</p>}
        {d.protocol ? (
          <div className="border-l-2 border-border pl-3">
            {/* Paraphrase kursiv, ohne Anführungszeichen (Designsprache § 1). */}
            <p className="text-lese italic text-foreground/90">{d.protocol.why}</p>
            <p className="mt-1 font-mono text-meta text-muted-foreground">
              aus der Niederschrift
              {d.protocol.organization ? ` · ${d.protocol.organization}` : ""}
              {d.protocol.date ? ` · ${datum(d.protocol.date)}` : ""}
              {d.protocol.vote ? ` · ${d.protocol.vote}` : ""}
            </p>
          </div>
        ) : (
          NIEDERSCHRIFT[d.protocol_source] && (
            <p className="text-meta text-muted-foreground">{NIEDERSCHRIFT[d.protocol_source]}</p>
          )
        )}
      </div>
    </li>
  );
}

// --------------------------------------------------------- Seitenspalte

function BelegListe({ belege }: { belege: Beleg[] }) {
  return (
    <div className="space-y-1.5">
      {belege.map((b) =>
        b.decision_id ? (
          <DecisionLinkCard
            key={`${b.decision_id}-${b.kvonr}`}
            id={b.decision_id}
            title={b.title}
            session_date={b.date}
          />
        ) : (
          <p key={`${b.kvonr}-${b.title}`} className="text-sm text-foreground/90">{b.title}</p>
        ),
      )}
    </div>
  );
}

function Rueckmeldung({ id }: { id: number }) {
  const [gesagt, setGesagt] = useState("");
  const [fehler, setFehler] = useState(false);
  async function sagen(verdict: "right" | "wrong") {
    setGesagt(verdict);
    setFehler(false);
    try {
      await api.post(`/council/cities/movements/feedback?id=${id}&verdict=${verdict}`);
    } catch {
      // Ohne Konto geht es nicht — eine Rückmeldung, die sich nicht zählen
      // lässt, ist kein Maßstab. Ein Hinweis statt eines stillen Fehlschlags.
      setGesagt("");
      setFehler(true);
    }
  }
  return (
    <div className="flex flex-wrap items-center gap-3 text-meta">
      <span className="text-muted-foreground">Stimmt das?</span>
      {(["right", "wrong"] as const).map((wert) => (
        <button
          key={wert}
          type="button"
          aria-pressed={gesagt === wert}
          onClick={() => sagen(wert)}
          className={gesagt === wert ? "font-semibold text-primary" : "text-muted-foreground hover:text-foreground"}
        >
          {wert === "right" ? "Ja" : "Nein"}
        </button>
      ))}
      {fehler && <span className="text-muted-foreground">Dafür braucht es ein Konto.</span>}
    </div>
  );
}

function UndInOldenburg({ detail }: { detail: Detail }) {
  const u = detail.movement.oldenburg;
  const schonGezeigt = new Set([...(u?.evidence ?? []), ...(u?.related ?? [])].map((b) => b.kvonr));
  const eigene = detail.oldenburg_documents.filter((b) => !schonGezeigt.has(b.kvonr));
  return (
    <section aria-labelledby="ol-titel" className="hh-tafel grid gap-3 rounded-[18px] p-4">
      <h2 id="ol-titel" className="flex items-center gap-2 font-display text-base font-bold text-foreground">
        <span aria-hidden className="h-2 w-2 rounded-[2px] bg-signal" />
        Und in Oldenburg?
      </h2>
      {u ? (
        <>
          <div><StandPille status={u.status} /></div>
          {u.situation && <p className="text-lese text-foreground">{u.situation}</p>}
          {u.confidence === "low" && (
            <p className="text-hinweis text-muted-foreground">
              Das Urteil ist unsicher — die Belege beantworten die Frage nur zum Teil.
            </p>
          )}
          {u.evidence.length > 0 && (
            <div className="grid gap-1.5">
              <Kicker>Worauf sich das stützt</Kicker>
              <BelegListe belege={u.evidence} />
            </div>
          )}
          {u.related.length > 0 && (
            <div className="grid gap-1.5">
              <Kicker>Verwandtes aus Oldenburg</Kicker>
              <p className="text-meta text-muted-foreground">Berührt die Sache, belegt den Stand aber nicht.</p>
              <BelegListe belege={u.related} />
            </div>
          )}
          <Rueckmeldung id={detail.movement.cluster_id} />
        </>
      ) : (
        <p className="text-lese text-muted-foreground">
          Ob Oldenburg das schon hat, ist noch nicht geprüft.
        </p>
      )}
      {eigene.length > 0 && (
        <div className="grid gap-1.5">
          <Kicker>Oldenburger Vorlagen zur selben Idee</Kicker>
          <BelegListe belege={eigene} />
        </div>
      )}
    </section>
  );
}

function RaeteBilanz({ detail }: { detail: Detail }) {
  // Eine Liste und kein Balken: „Keine Stimm-/Abstimmungsgrafiken"
  // (Designsprache § 8) — und acht Städte sind in Worten schneller gelesen.
  const zaehler = new Map<string, number>();
  for (const p of detail.movement.timeline) zaehler.set(p.outcome, (zaehler.get(p.outcome) ?? 0) + 1);
  const reihe = ["accepted", "amended", "rejected", "postponed", "referred", "noted", "withdrawn", "none"]
    .filter((k) => zaehler.get(k));
  return (
    <section aria-labelledby="bilanz-titel" className="grid gap-2 rounded-[14px] border border-border bg-card p-4 shadow-sm">
      <h2 id="bilanz-titel" className="font-display text-base font-bold text-foreground">
        So haben die Räte entschieden
      </h2>
      <ul className="grid gap-1.5">
        {reihe.map((k) => (
          <li key={k} className="flex items-center justify-between gap-3 text-sm">
            <ErgebnisPille outcome={k} />
            <span className="font-mono tabular-nums text-foreground">{zaehler.get(k)}</span>
          </li>
        ))}
      </ul>
      <p className="text-meta text-muted-foreground">
        Je Vorlage, nicht je Stadt: Eine Stadt kann dieselbe Idee mehrmals beraten haben.
      </p>
    </section>
  );
}

function Hinweis() {
  return (
    <p className="rounded-[14px] border border-dashed border-border p-3.5 text-hinweis text-muted-foreground">
      Die Vorlagen stammen aus den Ratsinformationssystemen der Städte. Den
      Stand in Oldenburg beurteilt ein Sprachmodell an Oldenburger
      Ratsunterlagen — nachprüfbar an den Belegen oben. Ein „Warum" steht nur,
      wo die Niederschrift selbst eine Begründung nennt.
    </p>
  );
}

function Aehnliche({ detail, von }: { detail: Detail; von: string }) {
  if (detail.similar.length === 0) return null;
  return (
    <section aria-labelledby="aehnlich-titel" className="grid gap-2">
      <Kicker>
        <span id="aehnlich-titel">Im selben Themenfeld</span>
      </Kicker>
      <ul className="grid gap-1.5">
        {detail.similar.map((a) => (
          <li key={a.cluster_id}>
            <Link
              href={`/council/ideen/bewegung?id=${a.cluster_id}${von ? `&von=${encodeURIComponent(von)}` : ""}`}
              className="text-sm font-medium text-primary hover:underline"
            >
              {a.label}
            </Link>
            <span className="ml-2 font-mono text-meta text-muted-foreground">{a.cities} Städte</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------- Seite

export default function View() {
  const an = useFeature("ideen-anderswo");
  const params = useSearchParams();
  const id = Number(params?.get("id") ?? "");
  const von = params?.get("von") ?? "";
  const [alle, setAlle] = useState(false);
  const { data, isPending, isError } = useQuery({
    queryKey: ["bewegung", id],
    queryFn: () => api.get<Detail>(`/council/cities/movements/detail?id=${id}`),
    enabled: Number.isFinite(id) && id > 0,
    staleTime: 10 * 60 * 1000,
  });
  const dokumente = useMemo(
    () => [...(data?.documents ?? [])].sort((a, b) => (a.date ?? "9999").localeCompare(b.date ?? "9999")),
    [data],
  );

  if (!an) return null;
  const zurueck = von ? `/council/ideen?${von}` : "/council/ideen";

  const kopfLink = (
    <Link href={zurueck} className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline">
      <ChevronLeft className="h-4 w-4" aria-hidden /> Alle Ideen
    </Link>
  );

  if (isError || (!isPending && !data) || !(id > 0)) {
    return (
      <div className="grid gap-4">
        {kopfLink}
        <div className="flex flex-col items-center gap-3 rounded-[18px] border-2 border-dashed border-border px-4 py-8 text-center">
          <Lotti regung="sucht" className="h-20 w-20" decorative />
          <p className="text-sm text-muted-foreground">Diese Idee gibt es nicht (mehr).</p>
        </div>
      </div>
    );
  }
  if (!data) return null;

  const b = data.movement;
  const feld = b.field ? POLICY_FIELD_LABELS[b.field] ?? b.field : null;
  return (
    <div className="grid gap-6">
      {kopfLink}
      <header className="grid max-w-3xl gap-2.5">
        {feld && <Kicker>{feld}</Kicker>}
        <h1 className="font-display text-[26px] font-bold leading-tight text-foreground [text-wrap:balance] sm:text-[34px]">
          {b.label}
        </h1>
        <p className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-sm text-muted-foreground">
          <span><b className="font-medium text-foreground">{b.cities.length}</b> Städte</span>
          <span>{bilanz(b)}</span>
          {zeitraum(b) && <span>{zeitraum(b)}</span>}
        </p>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_330px]">
        <div className="grid min-w-0 gap-6">
          <Buehne detail={data} />
          <section aria-labelledby="chronik-titel" className="grid gap-3">
            <h2 id="chronik-titel" className="font-display text-base font-bold text-foreground">
              Alle Vorlagen, nach Datum
            </h2>
            <ol className="overflow-hidden rounded-[14px] border border-border bg-card shadow-sm">
              {(alle ? dokumente : dokumente.slice(0, CHRONIK_ERST)).map((d) => (
                <Eintrag key={d.paper_id} d={d} />
              ))}
            </ol>
            {!alle && dokumente.length > CHRONIK_ERST && (
              <button
                type="button"
                onClick={() => setAlle(true)}
                className="justify-self-start text-sm font-semibold text-primary hover:underline"
              >
                Alle {dokumente.length} Vorlagen zeigen
              </button>
            )}
          </section>
        </div>
        <aside className="grid gap-4 lg:sticky lg:top-[calc(env(safe-area-inset-top,0px)+16px)]">
          <UndInOldenburg detail={data} />
          <RaeteBilanz detail={data} />
          <Hinweis />
          <Aehnliche detail={data} von={von} />
        </aside>
      </div>
    </div>
  );
}
