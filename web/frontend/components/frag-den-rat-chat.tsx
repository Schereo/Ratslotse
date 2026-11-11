"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, RotateCcw, Square } from "lucide-react";

import { AntwortText } from "@/components/qa-bausteine";
import { GespraecheEinwilligung } from "@/components/gespraeche-einwilligung";
import { reportBadgeEvent } from "@/components/badges";
import { apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { chipMerken } from "@/lib/chip-frage";
import { limitArt } from "@/lib/frage-limit";
import { fmtDatumKurz, zitatNummern } from "@/lib/qa-belege";
import { ASK_SCHRITTE, type AskSchritt } from "@/lib/qa-schritte";
import { decisionHref } from "@/lib/routes";
import { leseSseStrom } from "@/lib/sse";
import type { QaSource } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Was die Seite dem Archiv über sich sagt — derselbe `screen` wie in Lottis
 *  Fenster und auf der Fragen-Seite (`AskBody.screen`): Der Server schlägt den
 *  Gegenstand an der Kennung nach (`qa.seiten_gegenstand`), „das" in „Was
 *  kostet das?" wird zu ihm. */
export type ChatSeite = {
  route: string;
  refs: { ksinr?: number; item_number?: string; decision_id?: number };
};

type Runde = {
  key: number;
  question: string;
  answer: string;
  sources: QaSource[];
  followups: string[];
  schritt: AskSchritt | null;
  fehler?: "netz" | "server" | "limit" | "tag";
  fehlerText?: string;
  abgebrochen?: boolean;
};

const GESPRAECH_KEY = "ratslotse:qa-gespraech";

/**
 * „Frag den Rat" direkt auf der Seite eines Punkts oder Beschlusses (Tims
 * Wunsch 11.11.2026): Die Antwort entsteht hier, statt auf die Fragen-Seite
 * zu springen. Derselbe Weg wie dort (`POST /council/ask`, Strom über
 * `lib/sse.ts`), dasselbe Gespräch im Konto — „Auf der Fragen-Seite
 * weiterlesen" öffnet es dort mit allem, was nur die große Fläche kann
 * (Gründliche Recherche, Verlauf, Teilen).
 *
 * Ohne Konto bleiben Vorschläge und Feld Links auf die Fragen-Seite: Die
 * schickt zur Anmeldung und stellt die Frage danach (`fallbackHref`).
 */
export function FragDenRatChat({ seite, vorschlaege, fallbackHref, platzhalter }: {
  seite: ChatSeite;
  vorschlaege: string[];
  /** Ohne Konto: wohin eine Frage führt. */
  fallbackHref: (frage: string) => string;
  platzhalter: string;
}) {
  const { user } = useAuth();
  const [einstellung, setEinstellung] = useState<number | null | undefined>(
    () => (user ? user.saves_conversations ?? null : undefined));
  useEffect(() => { if (user) setEinstellung((e) => e ?? user.saves_conversations ?? null); }, [user]);
  const [runden, setRunden] = useState<Runde[]>([]);
  const [frage, setFrage] = useState("");
  const [laedt, setLaedt] = useState(false);
  const [gespraechId, setGespraechId] = useState<number | null>(null);
  const [wartend, setWartend] = useState<{ text: string; ausVorschlag: boolean } | null>(null);
  const abbruch = useRef<AbortController | null>(null);
  const naechster = useRef(1);
  const endeRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => () => abbruch.current?.abort(), []);

  const patchLetzte = (fn: (r: Runde) => Partial<Runde>) =>
    setRunden((rs) => rs.map((r, i) => (i === rs.length - 1 ? { ...r, ...fn(r) } : r)));

  /** `entschieden`: Die Einwilligung kam gerade erst — der Zustand, den diese
   *  Funktion sieht, ist dann noch der alte. */
  const fragen = async (roh: string, ausVorschlag: boolean, entschieden = false) => {
    const text = roh.trim();
    if (text.length < 4 || laedt) return;
    // Erst die Einwilligung (dieselbe wie auf der Fragen-Seite und in Lottis
    // Fenster): Ohne sie würde die Frage still verworfen.
    if (!entschieden && (einstellung === null || einstellung === undefined)) {
      setWartend({ text, ausVorschlag });
      return;
    }
    const verlauf = runden.filter((r) => r.answer && !r.fehler).slice(-4)
      .map((r) => ({ question: r.question.slice(0, 300), answer: r.answer.slice(0, 600) }));
    const vorherige = (runden.filter((r) => r.answer && !r.fehler).slice(-1)[0]?.answer ?? "").slice(0, 8000);
    const ctrl = new AbortController();
    abbruch.current = ctrl;
    setFrage("");
    setLaedt(true);
    setRunden((rs) => [...rs.map((r) => ({ ...r, followups: [] })), {
      key: naechster.current++, question: text, answer: "", sources: [], followups: [], schritt: "expand",
    }]);
    requestAnimationFrame(() => endeRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
    try {
      const res = await fetch(apiUrl("/council/ask"), {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text, history: verlauf, conversation_id: gespraechId,
          previous_answer: vorherige, from_suggestion: ausVorschlag,
          // `page`: Das Gespräch gehört auf die Fragen-Seite, nicht in Lottis Fenster.
          screen: { ...seite, surface: "page" },
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        let detail: unknown = null;
        try { detail = (await res.json())?.detail; } catch { /* egal */ }
        if (res.status === 429) {
          patchLetzte(() => (limitArt(detail) === "tag"
            ? { fehler: "tag", fehlerText: String(detail), schritt: null } : { fehler: "limit", schritt: null }));
        } else {
          patchLetzte(() => ({ fehler: "server", schritt: null,
            fehlerText: typeof detail === "string" ? detail : undefined }));
        }
        setFrage(text);
        return;
      }
      let fertig = false;
      let gefeiert = false;
      await leseSseStrom(res.body, (msg) => {
        if (msg.type === "step") patchLetzte(() => ({ schritt: msg.step as AskSchritt }));
        else if (msg.type === "sources") patchLetzte(() => ({ sources: (msg.sources as QaSource[]) ?? [] }));
        else if (msg.type === "token") {
          if (!gefeiert) { gefeiert = true; reportBadgeEvent("frage"); }
          patchLetzte((r) => ({ answer: r.answer + (msg.text as string) }));
        } else if (msg.type === "replace") patchLetzte(() => ({ answer: (msg.text as string) ?? "" }));
        else if (msg.type === "abbruch") patchLetzte(() => ({ abgebrochen: true }));
        else if (msg.type === "suggestions") patchLetzte(() => ({ followups: ((msg.questions as string[]) ?? []).slice(0, 3) }));
        else if (msg.type === "done") {
          fertig = true;
          patchLetzte(() => ({ schritt: null }));
          if (msg.conversation_id != null) setGespraechId(msg.conversation_id as number);
          else if ("conversation_id" in msg) setGespraechId(null);
        } else if (msg.type === "error") {
          fertig = true;
          patchLetzte(() => ({ fehler: "server", fehlerText: (msg.message as string) ?? undefined, schritt: null }));
        }
      });
      if (!fertig && !ctrl.signal.aborted) {
        patchLetzte((r) => (r.answer ? { abgebrochen: true, schritt: null } : { fehler: "netz", schritt: null }));
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      patchLetzte(() => ({ fehler: "netz", schritt: null }));
      setFrage(text);
    } finally {
      if (abbruch.current === ctrl) { abbruch.current = null; setLaedt(false); }
    }
  };

  const stopp = () => {
    abbruch.current?.abort();
    abbruch.current = null;
    setLaedt(false);
    patchLetzte((r) => ({ abgebrochen: Boolean(r.answer) || undefined, schritt: null,
      ...(r.answer ? {} : { fehler: "netz" as const }) }));
  };

  // Ohne Konto: Links wie bisher — die Fragen-Seite führt durch die Anmeldung.
  if (!user) {
    return (
      <>
        <Vorschlaege fragen={vorschlaege} href={fallbackHref} />
        <form className="flex gap-2 px-4 pb-4" onSubmit={(e) => {
          e.preventDefault();
          const q = frage.trim();
          if (q.length < 4) return;
          chipMerken(q);
          window.location.assign(fallbackHref(q));
        }}>
          <Feld wert={frage} setzen={setFrage} platzhalter={platzhalter} />
          <Senden />
        </form>
      </>
    );
  }

  const letzte = runden[runden.length - 1];
  const chips = runden.length === 0 ? vorschlaege : (!laedt && letzte?.followups.length ? letzte.followups : []);
  return (
    <>
      {runden.length > 0 && (
        <div aria-live="polite" className="space-y-4 px-4 pt-4">
          {runden.map((r) => <RundeAnsicht key={r.key} r={r}
            nochmal={() => { setRunden((rs) => rs.filter((x) => x.key !== r.key)); void fragen(r.question, false); }} />)}
          <div ref={endeRef} />
        </div>
      )}
      {wartend && (einstellung === null || einstellung === undefined) && (
        <div className="px-4 pt-4">
          <GespraecheEinwilligung kompakt onEntschieden={(merken) => {
            setEinstellung(merken ? 1 : 0);
            const w = wartend;
            setWartend(null);
            void fragen(w.text, w.ausVorschlag, true);
          }} />
        </div>
      )}
      {chips.length > 0 && (
        <ul className="space-y-2 p-4 pb-0">
          {chips.map((q) => (
            <li key={q}>
              <button type="button" onClick={() => void fragen(q, true)} disabled={laedt}
                className="flex min-h-11 w-full items-center justify-between gap-2 rounded-xl border border-primary/30 bg-primary/[0.04] px-3 py-2 text-left text-sm text-foreground hover:bg-primary/[0.08] disabled:opacity-60">
                {q} <ArrowRight className="h-4 w-4 flex-none text-primary" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <form className="flex gap-2 p-4" onSubmit={(e) => { e.preventDefault(); void fragen(frage, false); }}>
        <Feld wert={frage} setzen={setFrage} platzhalter={runden.length ? "Nachfragen …" : platzhalter} />
        {laedt ? (
          <button type="button" onClick={stopp} aria-label="Antwort anhalten"
            className="inline-flex h-11 w-11 flex-none items-center justify-center rounded-xl border border-border text-foreground hover:bg-accent">
            <Square className="h-4 w-4" aria-hidden />
          </button>
        ) : <Senden disabled={frage.trim().length < 4} />}
      </form>
      {gespraechId != null && einstellung === 1 && !laedt && (
        <p className="-mt-2 px-4 pb-3 text-sm">
          <Link href="/fragen" prefetch={false} onClick={() => {
            try { sessionStorage.setItem(GESPRAECH_KEY, String(gespraechId)); } catch { /* privat */ }
          }} className="inline-flex min-h-11 items-center gap-1 font-medium text-primary hover:underline">
            Auf der Fragen-Seite weiterlesen <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </p>
      )}
    </>
  );

}

function RundeAnsicht({ r, nochmal }: { r: Runde; nochmal: () => void }) {
  const idToNum = useMemo(() => zitatNummern(r.answer, r.sources.map((s) => s.id)), [r.answer, r.sources]);
  const belege = useMemo(() => {
    const byId = new Map(r.sources.map((s) => [s.id, s]));
    return [...idToNum.keys()].map((id) => byId.get(id)).filter((s): s is QaSource => !!s);
  }, [idToNum, r.sources]);
  return (
    <div>
      <p className="ml-auto w-fit max-w-[92%] rounded-2xl rounded-br-md bg-primary/[0.08] px-3 py-2 text-sm text-foreground">
        {r.question}
      </p>
      <div className="mt-2 text-[14.5px] leading-relaxed text-foreground">
        {r.answer ? (
          <AntwortText text={r.answer} idToNum={idToNum} quelleHref={(n) => {
            const id = [...idToNum.entries()].find(([, nr]) => nr === n)?.[0];
            return id != null ? decisionHref(id) : "#";
          }} />
        ) : r.schritt ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-muted border-t-primary" aria-hidden />
            {ASK_SCHRITTE[r.schritt] ?? "Antwort wird formuliert"} …
          </p>
        ) : null}
        {r.abgebrochen && <p className="mt-1 text-hinweis text-muted-foreground">Die Antwort ist hier abgebrochen.</p>}
        {r.fehler && (
          <div className="mt-1 text-sm text-muted-foreground">
            <p>{r.fehler === "limit" ? "Gerade kamen viele Fragen — bitte einen Moment warten."
              : r.fehler === "tag" ? (r.fehlerText || "Für heute sind keine Fragen mehr frei.")
              : r.fehlerText || "Das hat gerade nicht geklappt."}</p>
            {r.fehler !== "tag" && (
              <button type="button" onClick={nochmal}
                className="mt-1 inline-flex min-h-11 items-center gap-1.5 font-medium text-primary hover:underline">
                <RotateCcw className="h-4 w-4" aria-hidden /> Nochmal versuchen
              </button>
            )}
          </div>
        )}
      </div>
      {belege.length > 0 && !r.schritt && (
        <ol className="mt-2 space-y-1 border-t border-border pt-2">
          {belege.map((s) => (
            <li key={s.id}>
              <Link href={decisionHref(s.id)} prefetch={false}
                className="flex min-h-11 items-start gap-2 rounded-lg px-1 py-1 text-sm hover:bg-accent">
                <span className="mt-0.5 font-mono text-[11px] text-muted-foreground">{idToNum.get(s.id)}</span>
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 text-foreground">{s.title ?? "Beschluss"}</span>
                  <span className="block text-xs text-muted-foreground">{s.committee} · {fmtDatumKurz(s.session_date)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Vorschlaege({ fragen, href }: { fragen: string[]; href: (q: string) => string }) {
  return (
    <ul className="space-y-2 p-4">
      {fragen.map((q) => (
        <li key={q}>
          <Link href={href(q)} prefetch={false} onClick={() => chipMerken(q)}
            className="flex min-h-11 items-center justify-between gap-2 rounded-xl border border-primary/30 bg-primary/[0.04] px-3 py-2 text-sm text-foreground hover:bg-primary/[0.08]">
            {q} <ArrowRight className="h-4 w-4 flex-none text-primary" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Feld({ wert, setzen, platzhalter }: { wert: string; setzen: (s: string) => void; platzhalter: string }) {
  return (
    <>
      <label className="sr-only" htmlFor="seiten-frage">{platzhalter}</label>
      <input id="seiten-frage" value={wert} onChange={(e) => setzen(e.target.value)} placeholder={platzhalter}
        className={cn("min-h-11 min-w-0 flex-1 rounded-xl border border-input bg-background px-3 text-sm")} />
    </>
  );
}

function Senden({ disabled = false }: { disabled?: boolean }) {
  return (
    <button type="submit" aria-label="Frage stellen" disabled={disabled}
      className="inline-flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
      <ArrowRight className="h-4 w-4" aria-hidden />
    </button>
  );
}
