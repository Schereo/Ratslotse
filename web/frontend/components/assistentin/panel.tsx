"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, RotateCcw, Sparkles, X } from "lucide-react";

import { Mascot } from "@/components/mascot";
import { AntwortText } from "@/components/qa-bausteine";
import { apiUrl, authHeaders } from "@/lib/api";
import {
  auswahlText, kuerze, refsAus, routeAus, trenneWeiter,
  type Bildschirm,
} from "@/lib/assistentin";
import { useAuth } from "@/lib/auth";
import { GespraecheEinwilligung } from "@/components/gespraeche-einwilligung";
import { fragenHref } from "@/lib/routes";
import type { ElementFrage } from "./index";
import { leseSseStrom } from "@/lib/sse";
import { cn } from "@/lib/utils";

/**
 * Lottis Chat-Fenster — das Gegenstück zum schwebenden Knopf.
 *
 * **Kein Sheet und kein Dialog.** Am Schreibtisch ist es ein Fenster über dem
 * Knopf, 384 px breit und **nicht modal**: Die Seite bleibt bedienbar, man
 * kann weiterlesen und weiterscrollen, während Lotti antwortet. Ein Dialog mit
 * Abdunkler wäre das Gegenteil dessen, wofür die Assistentin da ist — sie
 * erklärt, was auf der Seite steht, also darf sie die Seite nicht verdecken.
 * Auf dem Handy füllt es die Fläche zwischen Kopfleiste und Knopf; dort ist
 * ein halbes Fenster keins.
 *
 * **Der Verlauf überlebt den Seitenwechsel.** Das Fenster lebt in der
 * App-Hülle, nicht in einer Seite. Wer navigiert, behält seine Runden — nur
 * die Kontext-Pille wechselt. Innerhalb des Tabs übersteht der Verlauf auch
 * ein Neuladen (`sessionStorage`); über den Tab hinaus nicht: Gespeichert
 * wird erst mit Einwilligung, und die ist ein eigener Schritt.
 */

const SPEICHER = "ratslotse:lotti-verlauf";
const MAX_TURNS_SPEICHER = 10;
const MAX_TURNS_KONTEXT = 3;

export type LottiTurn = {
  key: number;
  question: string;
  answer: string;
  next: "ratsfrage" | null;
  glossary: string[];
  /** Kam die Antwort ohne Modell? Nur fürs Protokoll, nicht sichtbar. */
  mode: string | null;
  fehler?: boolean;
  /** Was auf dem Bildschirm stand, als die Frage gestellt wurde. */
  kontext: string;
};

function leseVerlauf(): LottiTurn[] {
  try {
    const roh = sessionStorage.getItem(SPEICHER);
    if (!roh) return [];
    const p = JSON.parse(roh);
    return Array.isArray(p) ? (p as LottiTurn[]).slice(-MAX_TURNS_SPEICHER) : [];
  } catch {
    return [];
  }
}

function merkeVerlauf(turns: LottiTurn[]): void {
  try {
    sessionStorage.setItem(SPEICHER, JSON.stringify(turns.slice(-MAX_TURNS_SPEICHER)));
  } catch { /* privates Fenster, gesperrter Speicher — dann eben nicht */ }
}

export function LottiPanel({
  offen, onSchliessen, markierung, element, onElementVerbraucht, onModus,
}: {
  offen: boolean;
  onSchliessen: () => void;
  /** Der gerade markierte Text der Seite — er wandert in die Kontext-Pille. */
  markierung: string;
  /** Ein im Erklär-Modus angetippter Baustein. Gesetzt heißt: sofort fragen. */
  element: ElementFrage | null;
  onElementVerbraucht: () => void;
  /** „Etwas auf der Seite zeigen" — der Modus lebt eine Ebene höher. */
  onModus: () => void;
}) {
  const pathname = usePathname();
  const sp = useSearchParams();
  const router = useRouter();
  const [turns, setTurns] = useState<LottiTurn[]>([]);
  // Dieselbe Einwilligung wie „Frag den Rat" — ein Schalter am Konto, eine
  // Tabelle. `null` heißt „noch nie gefragt" und ist der einzige Zustand, in
  // dem die Karte erscheint; eine getroffene Wahl gilt auf beiden Flächen.
  const { user, refresh } = useAuth();
  const [merken, setMerken] = useState<number | null | undefined>(
    () => (user ? user.saves_conversations ?? null : undefined));
  const [gespraechId, setGespraechId] = useState<number | null>(null);
  const [frage, setFrage] = useState("");
  const [laden, setLaden] = useState(false);
  const abbruch = useRef<AbortController | null>(null);
  const eingabeRef = useRef<HTMLInputElement>(null);
  const endeRef = useRef<HTMLDivElement>(null);
  const fensterRef = useRef<HTMLDivElement>(null);
  const naechsterKey = useRef(1);

  const route = routeAus(pathname, sp.toString());
  // Die Route MUSS mit: `?id=` ist auf der Ort-Seite ein Kürzel, sonst eine
  // Nummer (lib/assistentin.ts).
  const refs = useMemo(() => refsAus(sp.toString(), route), [sp, route]);

  // Der Verlauf des Tabs — einmal beim Aufbauen, danach bei jeder Änderung.
  useEffect(() => {
    const alt = leseVerlauf();
    if (alt.length) {
      setTurns(alt);
      naechsterKey.current = Math.max(...alt.map((t) => t.key)) + 1;
    }
  }, []);
  useEffect(() => { if (turns.length) merkeVerlauf(turns); }, [turns]);

  // Beim Öffnen: Fokus ins Eingabefeld. Beim Schließen: zurück auf den Knopf —
  // sonst steht der Fokus im Nichts, und die nächste Tabulatortaste beginnt
  // wieder ganz oben auf der Seite (BITV).
  useEffect(() => {
    if (offen) {
      const id = window.setTimeout(() => eingabeRef.current?.focus(), 60);
      return () => window.clearTimeout(id);
    }
    document.querySelector<HTMLElement>("[data-lotti-knopf]")?.focus();
  }, [offen]);

  // Esc schließt — auch wenn der Fokus gerade woanders auf der Seite steht.
  useEffect(() => {
    if (!offen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onSchliessen(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [offen, onSchliessen]);

  // Ein Seitenwechsel bricht eine laufende Antwort ab: Eine Erklärung zur
  // ALTEN Seite, die auf der neuen fertig geschrieben wird, ist schlimmer als
  // keine — sie sieht aus, als gehörte sie hierher.
  useEffect(() => {
    abbruch.current?.abort();
    abbruch.current = null;
    setLaden(false);
  }, [pathname]);

  useEffect(() => {
    if (offen) endeRef.current?.scrollIntoView({ block: "end" });
  }, [offen, turns.length]);

  const fragen = useCallback(async (
    text: string, mitMarkierung: boolean, baustein: ElementFrage | null = null,
  ) => {
    const sauber = text.trim();
    if (!sauber && !mitMarkierung && !baustein) return;
    // Ohne beantwortete Einwilligung wird nicht gefragt: Der Satz über die
    // externe Verarbeitung steht in der Karte, und sie ist die einzige Stelle,
    // an der er VOR der ersten Frage steht.
    if (merken === null || merken === undefined) return;
    abbruch.current?.abort();
    const ctrl = new AbortController();
    abbruch.current = ctrl;
    setFrage("");
    setLaden(true);

    const kontext = baustein
      ? (baustein.title || "Baustein auf der Seite")
      : (mitMarkierung && markierung ? `Markiert: „${kuerze(markierung, 40)}“` : "");
    const key = naechsterKey.current++;
    setTurns((ts) => [...ts, {
      key, question: sauber, answer: "", next: null, glossary: [], mode: null, kontext,
    }]);

    const bildschirm: Bildschirm = {
      route,
      page_title: document.title.replace(/\s*[–|]\s*Ratslotse\s*$/, ""),
      heading: document.querySelector("h1")?.textContent?.trim().slice(0, 200) ?? "",
      element: baustein,
      selection: mitMarkierung ? markierung : "",
      refs,
    };

    const patch = (fn: (t: LottiTurn) => Partial<LottiTurn>) =>
      setTurns((ts) => ts.map((t) => (t.key === key ? { ...t, ...fn(t) } : t)));

    try {
      const res = await fetch(apiUrl("/council/explain"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          route: bildschirm.route,
          page_title: bildschirm.page_title,
          heading: bildschirm.heading,
          element: bildschirm.element,
          selection: bildschirm.selection,
          question: sauber,
          refs: bildschirm.refs,
          history: turns.filter((t) => t.answer && !t.fehler).slice(-MAX_TURNS_KONTEXT)
            .map((t) => ({ question: t.question.slice(0, 200), answer: t.answer.slice(0, 300) })),
          // Das laufende Gespräch. Das Feld MUSS mit, auch als `null`: Der
          // Server speichert nur, wenn der Client es überhaupt geschickt hat
          // (`model_fields_set`) — so bleibt ein alter Client stumm, statt
          // ungefragt Gespräche anzulegen.
          conversation_id: gespraechId,
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        // 400 heißt: Zu dieser Seite gibt es nichts zu sagen — der Grund steht
        // in der Antwort und ist für Menschen geschrieben.
        let msg = "Dazu kann ich gerade nichts sagen.";
        try {
          const b = await res.json();
          if (typeof b?.detail === "string") msg = b.detail;
        } catch { /* kein JSON — dann bleibt der allgemeine Satz */ }
        patch(() => ({ answer: msg, fehler: true }));
        return;
      }
      await leseSseStrom(res.body, (msg) => {
        if (msg.type === "token") patch((t) => ({ answer: t.answer + (msg.text as string) }));
        else if (msg.type === "replace") {
          const { text: rein, next } = trenneWeiter((msg.text as string) ?? "");
          patch(() => ({ answer: rein, next }));
        } else if (msg.type === "done") {
          patch((t) => ({
            next: (msg.next as "ratsfrage" | null) ?? t.next,
            glossary: (msg.glossary as string[]) ?? [],
            mode: (msg.mode as string) ?? null,
          }));
          // `null` heißt: Der Server konnte oder durfte nicht (mehr) in dieses
          // Gespräch speichern — die tote Kennung nicht weiter mitschicken,
          // die nächste Frage eröffnet frisch.
          if (msg.conversation_id != null) setGespraechId(msg.conversation_id as number);
          else if ("conversation_id" in msg) setGespraechId(null);
        } else if (msg.type === "error") {
          patch(() => ({ answer: (msg.message as string) ?? "Erklärung fehlgeschlagen.", fehler: true }));
        }
      });
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      // Die Frage ist nicht verloren — sie steht wieder im Eingabefeld
      // (Designsprache § 6: „Fehler/Limits: immer mit Ausweg").
      patch(() => ({ answer: "Das hat gerade nicht geklappt.", fehler: true }));
      setFrage(sauber);
    } finally {
      if (abbruch.current === ctrl) {
        setLaden(false);
        abbruch.current = null;
      }
    }
  }, [markierung, refs, route, turns, gespraechId, merken]);

  // Ein im Erklär-Modus angetippter Baustein fragt von selbst — der Tipp auf
  // das Abzeichen IST die Frage, ein zweiter Klick im Fenster wäre einer zu
  // viel. Danach wird er verbraucht, sonst feuerte jedes Neuzeichnen erneut.
  useEffect(() => {
    if (!element || !offen) return;
    void fragen("", false, element);
    onElementVerbraucht();
    // `fragen` hängt am Verlauf und wechselt mit jeder Runde — in der
    // Abhängigkeitsliste stünde es für „bei jeder Antwort noch einmal fragen".
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [element, offen]);

  const neuAnfangen = () => {
    abbruch.current?.abort();
    setTurns([]);
    setFrage("");
    setGespraechId(null);
    try { sessionStorage.removeItem(SPEICHER); } catch { /* egal */ }
    eingabeRef.current?.focus();
  };

  const zurRatsfrage = (t: LottiTurn) => {
    onSchliessen();
    router.push(fragenHref({ q: t.question }));
  };

  if (!offen) return null;

  const kontextZeile = [
    document.querySelector("h1")?.textContent?.trim(),
    markierung ? `markiert: „${kuerze(markierung, 40)}“` : null,
  ].filter(Boolean).join(" · ");

  return (
    <div
      id="lotti-fenster"
      ref={fensterRef}
      role="dialog"
      aria-label="Lotti fragen"
      data-lotti-fenster
      className={cn(
        "fixed z-50 flex flex-col overflow-hidden rounded-2xl border border-border",
        "bg-card shadow-lifted print:hidden",
        "animate-in fade-in-0 slide-in-from-bottom-4 duration-buehne ease-out-strong",
        // Handy: die Fläche zwischen Kopfleiste und Knopf.
        "inset-x-2 top-[calc(env(safe-area-inset-top)+4.5rem)]",
        "bottom-[calc(var(--rl-unten,0px)+var(--rl-composer,0px)+5rem)]",
        // Schreibtisch: ein Fenster über dem Knopf.
        "desk:inset-x-auto desk:top-auto desk:right-6 desk:w-96",
        "desk:bottom-[calc(var(--rl-composer,0px)+5.5rem)] desk:h-[min(40rem,100dvh-9rem)]",
      )}
    >
      {/* Kopfzeile */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Mascot
          regung={laden ? "schreibt" : "ruht"}
          decorative
          className="h-8 w-8 flex-none"
        />
        <span className="flex-1 font-display text-base font-bold text-foreground">Lotti</span>
        {turns.length > 0 && (
          <button
            type="button"
            onClick={neuAnfangen}
            aria-label="Neu anfangen"
            title="Neu anfangen"
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <RotateCcw className="h-4 w-4" aria-hidden />
          </button>
        )}
        <button
          type="button"
          onClick={onSchliessen}
          aria-label="Lotti schließen"
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring desk:hidden"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {/* Kontext-Pille: worüber reden wir gerade? */}
      {kontextZeile && (
        <p className="border-b border-border/60 bg-muted/40 px-3 py-1.5 text-meta text-muted-foreground">
          <span className="font-medium text-foreground/80">Du bist auf:</span> {kontextZeile}
        </p>
      )}

      {/* Verlauf */}
      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {merken === null && (
          <GespraecheEinwilligung
            kompakt
            onEntschieden={(ja) => { setMerken(ja ? 1 : 0); refresh(); }}
          />
        )}
        {turns.length === 0 && merken !== null && (
          <div className="flex flex-col items-center gap-2 px-2 pt-4 text-center">
            <Mascot pose="wave" decorative className="h-16 w-16" />
            <p className="text-hinweis text-muted-foreground">
              Moin! Ich erkläre dir, was du hier siehst. Markier etwas auf der
              Seite oder frag mich einfach.
            </p>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.key} className="space-y-2">
            {t.question && (
              <p className="ml-6 rounded-xl rounded-br-sm border border-primary/[0.18] bg-primary/[0.07] px-2.5 py-1.5 text-[13.5px] text-foreground">
                {t.question}
              </p>
            )}
            {t.kontext && (
              <p className="ml-6 text-right font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {t.kontext}
              </p>
            )}
            <div className="flex gap-2">
              <Mascot
                regung={t.fehler ? "ist-traurig" : "erklaert"}
                decorative
                className="mt-0.5 h-6 w-6 flex-none"
              />
              <div className="min-w-0 flex-1">
                {t.answer
                  ? (
                    <div className="text-[13.5px] leading-relaxed text-foreground/90">
                      <AntwortText text={t.answer} idToNum={new Map()} />
                    </div>
                  )
                  : <Tippt />}
                {t.answer && !t.fehler && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => zurRatsfrage(t)}
                      className={cn(
                        "inline-flex min-h-8 items-center gap-1 rounded-full px-2.5 text-[12px] font-medium transition-colors",
                        t.next === "ratsfrage"
                          ? "bg-primary text-primary-foreground hover:bg-primary/90"
                          : "border border-primary/30 bg-primary/[0.04] text-primary hover:bg-primary/10",
                      )}
                    >
                      Den Rat fragen
                      <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={endeRef} />
      </div>

      {/* Vorschlags-Chips */}
      <div className="flex flex-wrap gap-1.5 px-3 pb-1.5">
        <Chip onClick={() => void fragen("Was sehe ich hier?", false)} disabled={laden || merken == null}>
          Was sehe ich hier?
        </Chip>
        {markierung && (
          <Chip onClick={() => void fragen("Was heißt das?", true)} disabled={laden || merken == null}>
            Markiertes erklären
          </Chip>
        )}
        <Chip onClick={onModus} disabled={laden || merken == null}>
          Etwas auf der Seite zeigen
        </Chip>
      </div>

      {/* Composer */}
      <form
        onSubmit={(e) => { e.preventDefault(); void fragen(frage, !!markierung); }}
        className="flex items-center gap-2 border-t border-border px-3 py-2"
      >
        <Sparkles className="h-4 w-4 flex-none text-signal" aria-hidden />
        <input
          ref={eingabeRef}
          value={frage}
          onChange={(e) => setFrage(e.target.value)}
          placeholder="Frag mich zu dieser Seite …"
          aria-label="Frage an Lotti"
          className="min-w-0 flex-1 bg-transparent text-[13.5px] text-foreground outline-none placeholder:text-muted-foreground"
        />
        <button
          type="submit"
          disabled={laden || !frage.trim() || merken == null}
          aria-label="Fragen"
          className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors disabled:bg-primary/35"
        >
          <ArrowRight className="h-4 w-4" aria-hidden />
        </button>
      </form>

      <p className="border-t border-border/60 px-3 py-1.5 text-[11px] leading-snug text-muted-foreground">
        Erklärt aus Glossar, Seite und Haushaltsdaten. Keine Rechtsberatung,
        keine Bewertung.
      </p>
    </div>
  );
}

/** Die Tipp-Anzeige der Chat-Fenster — hier an einen echten Zustand gebunden. */
function Tippt() {
  return (
    <span className="inline-flex items-center gap-1 py-1" role="status" aria-label="Lotti schreibt">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal"
          style={{ animationDelay: `${i * 160}ms` }}
        />
      ))}
    </span>
  );
}

function Chip({ children, onClick, disabled }: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex min-h-8 items-center rounded-full border border-primary/30 bg-primary/[0.04] px-2.5 text-[12px] font-medium text-primary transition-colors hover:bg-primary/10 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

/** Der markierte Text der Seite — als Hook, damit Knopf und Fenster dieselbe
 *  Quelle haben. Läuft über `selectionchange` mit kurzer Ruhepause: Während
 *  man mit der Maus zieht, feuert das Ereignis bei jedem Pixel. */
export function useMarkierung(): string {
  const [text, setText] = useState("");
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const onChange = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const fenster = document.querySelector("[data-lotti-fenster]");
        setText(auswahlText(document.getSelection(), fenster));
      }, 250);
    };
    document.addEventListener("selectionchange", onChange);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("selectionchange", onChange);
    };
  }, []);
  return text;
}
