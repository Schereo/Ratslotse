"use client";

/** „Gründliche Recherche" (Design RG-10, Abschnitt 8a–8d): die UI-Bausteine
 *  des zweiten Frage-Modus. Der Job läuft SERVER-seitig weiter, wenn man den
 *  Tab wechselt oder in der App navigiert — diese Komponenten zeigen nur den
 *  Stand; die Verbindungs-Logik lebt im QaTab (council-qa.tsx).
 *
 *  Sprache laut Spezifikation 8d: „Gründliche Recherche" / „Gründlich
 *  recherchieren" — nie „Deep Research", „Agent" oder „KI-Modus". */

import { useEffect, useRef, useState } from "react";
import { CalendarDays, Check, FlaskConical, Loader2, RotateCcw, Square, X } from "lucide-react";

import { Mascot } from "@/components/mascot";
import { isNativeApp } from "@/lib/platform";
import { cn } from "@/lib/utils";

/** Künftige Beratungsstation einer zitierten Vorlage (Sitzungskalender). */
export type Planung = {
  kvonr: number; datum: string | null; gremium: string | null;
  vorlage_nr: string | null; vorlage_titel: string | null;
};

export type DeepPhase = "zerlegen" | "suchen" | "lesen" | "schreiben";

export type DeepFacette = { name: string; treffer?: number; neu?: number };

const fmtDatum = (d?: string | null) =>
  d ? new Date(`${d}T00:00:00`).toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" }) : "";

/** Umschalter-Pill ÜBER dem Composer (8a① → Tims TestFlight-Feedback 11.08.,
 *  zweite Runde): Als Kolben-Knopf IN der Composer-Zeile nahm der Schalter
 *  der Textbox zu viel Breite — als Pill über dem Eingabefeld kostet er
 *  weder Breite noch steht er unter dem Feld im Weg. */
export function RechercheToggle({ aktiv, frei, onToggle }: {
  aktiv: boolean; frei: number | null; onToggle: () => void;
}) {
  const leer = frei !== null && frei <= 0;
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={leer && !aktiv}
      aria-pressed={aktiv}
      title={leer ? "Tageskontingent aufgebraucht — ab Mitternacht wieder" : "Gründliche Recherche: dauert etwa 30 Sekunden, liest deutlich mehr Beschlüsse"}
      className={cn(
        "inline-flex h-[30px] shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-[11.5px] font-semibold transition-colors",
        aktiv
          ? "border-primary bg-primary/[0.07] text-primary"
          : leer
            ? "cursor-not-allowed border-border bg-card text-muted-foreground/50"
            : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <FlaskConical className="h-3.5 w-3.5" aria-hidden />
      <span>{leer && !aktiv ? "Recherche · ab Mitternacht wieder" : "Gründlich recherchieren"}</span>
      {aktiv && <X className="h-3 w-3" aria-hidden />}
    </button>
  );
}

/** Erwartungs-Hinweis beim Aktivieren (8a①): einmal täglich ausführlich als
 *  Karte — die Kurzform („~30 Sek · noch n heute") steht daneben im Composer. */
export function RechercheHinweisKarte({ frei }: { frei: number | null }) {
  return (
    <div className="mb-1.5 flex items-start gap-2 rounded-xl border border-border bg-card px-3 py-2.5">
      <FlaskConical className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
      <p className="text-[11.5px] leading-relaxed text-muted-foreground">
        <strong className="text-foreground">Gründliche Recherche:</strong>{" "}
        zerlegt deine Frage in Facetten, liest deutlich mehr Beschlüsse und
        schreibt einen gegliederten Bericht. <strong>Dauert etwa 30 Sekunden</strong>
        {frei !== null && <> · noch {frei} von 5 heute</>}.
      </p>
    </div>
  );
}

/** Kontingent erreicht (8c⑤): freundliche Amber-Karte, die schnelle Frage
 *  bleibt als Ausweg offen und übernimmt den Fragetext. */
export function RechercheLimitKarte({ onSchnelleFrage }: { onSchnelleFrage: () => void }) {
  return (
    <div className="mb-2 flex items-start gap-2.5 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3.5 py-3">
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" aria-hidden />
      <div className="min-w-0">
        <p className="text-[13px] font-semibold text-foreground">Deine 5 Recherchen für heute sind aufgebraucht</p>
        <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
          Ab Mitternacht geht es weiter. Die schnelle Frage steht dir weiter unbegrenzt
          zur Verfügung — für den Überblick reicht sie oft.
        </p>
        <button type="button" onClick={onSchnelleFrage}
          className="mt-2 inline-flex items-center rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
          Als schnelle Frage stellen
        </button>
      </div>
    </div>
  );
}

/** Fortschritts-Karte (8a②): Phasen-Checkliste, Facetten-Chips, Balken mit
 *  grober Restzeit, Abbrechen. Lotti sucht. Erscheint anstelle der Antwort,
 *  solange der Job läuft. */
export function RechercheFortschritt({ phase, facetten, facettenFertig, dokumente, onStop }: {
  phase: DeepPhase; facetten: DeepFacette[]; facettenFertig: number;
  dokumente: number | null; onStop: () => void;
}) {
  // Grobe Fortschritts-Heuristik: zerlegen 8 %, suchen bis 55 %, lesen 62 %,
  // schreiben wächst mit der Zeit gegen 95 % (der Balken soll Leben zeigen,
  // keine Präzision behaupten).
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (phase !== "schreiben") return;
    const id = setInterval(() => setTick((t) => t + 1), 2000);
    return () => clearInterval(id);
  }, [phase]);
  // „Wir melden uns" gilt nur in der App — im Browser gibt es kein Gerät für
  // den Push. Nach dem Mount bestimmt, damit der statische Export sauber
  // hydriert.
  const [nativ, setNativ] = useState(false);
  useEffect(() => { setNativ(isNativeApp()); }, []);
  const prozent =
    phase === "zerlegen" ? 8
    : phase === "suchen" ? 10 + (facetten.length ? (facettenFertig / facetten.length) * 45 : 20)
    : phase === "lesen" ? 62
    : Math.min(95, 68 + tick);
  // Zeitangaben an echten Läufen gemessen (11.08.: 28 s und 36 s für eine
  // komplette Recherche) — vorher versprach die Karte „1–2 Minuten" und war
  // damit doppelt so pessimistisch wie die Wirklichkeit (Tims Befund).
  const restzeit = phase === "schreiben" || phase === "lesen" ? "~ noch 15 Sek" : "~ noch 30 Sek";

  const schritt = (zustand: "fertig" | "aktiv" | "offen", text: string) => (
    <span className={cn("flex items-center gap-2 text-xs",
      zustand === "aktiv" ? "font-semibold text-foreground"
        : zustand === "fertig" ? "text-muted-foreground" : "text-muted-foreground/60")}>
      {zustand === "fertig" ? <Check className="h-3.5 w-3.5 shrink-0 text-green-600" aria-hidden />
        : zustand === "aktiv" ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" aria-hidden />
          : <span aria-hidden className="mx-[1px] h-3 w-3 shrink-0 rounded-full border-2 border-dotted border-border" />}
      {text}
    </span>
  );
  const reihenfolge: DeepPhase[] = ["zerlegen", "suchen", "lesen", "schreiben"];
  const stufe = reihenfolge.indexOf(phase);
  const zustand = (i: number) => (i < stufe ? "fertig" : i === stufe ? "aktiv" : "offen") as
    "fertig" | "aktiv" | "offen";

  return (
    <div role="status" className="rounded-[14px] border-2 border-dashed border-border bg-card/60 p-3.5">
      <div className="flex gap-3">
        <Mascot pose="search" className="h-[52px] w-[52px] shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-1.5 pt-0.5">
          {schritt(zustand(0), stufe > 0 && facetten.length > 0
            ? `Frage in ${facetten.length} Facetten zerlegt` : "Frage zerlegen …")}
          {schritt(zustand(1), phase === "suchen" ? "Facetten durchsuchen …" : "Facetten durchsuchen")}
          {schritt(zustand(2), dokumente ? `${dokumente} Dokumente lesen` : "Dokumente lesen")}
          {schritt(zustand(3), "Bericht schreiben")}
        </div>
      </div>
      {facetten.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border/60 pt-2.5">
          {facetten.map((f, i) => {
            const fertig = i < facettenFertig || stufe > 1;
            const aktiv = !fertig && i === facettenFertig && phase === "suchen";
            return (
              <span key={f.name + i} className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
                fertig ? "border-green-600/25 bg-green-600/5 text-green-700 dark:text-green-500"
                  : aktiv ? "border-primary/35 bg-primary/[0.06] font-semibold text-primary"
                    : "border-border bg-card text-muted-foreground")}>
                {fertig ? <Check className="h-3 w-3" aria-hidden />
                  : aktiv ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden /> : null}
                {f.name}{fertig && f.treffer != null ? ` · ${f.treffer} Treffer` : aktiv ? " …" : ""}
              </span>
            );
          })}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2.5">
        <span className="h-[5px] flex-1 overflow-hidden rounded-full bg-primary/10">
          <span className="block h-full rounded-full bg-primary transition-[width] duration-700"
            style={{ width: `${prozent}%` }} />
        </span>
        <span className="whitespace-nowrap font-mono text-[10px] text-muted-foreground">{restzeit}</span>
        <button type="button" onClick={onStop}
          className="inline-flex items-center gap-1.5 rounded-[10px] border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted">
          <Square className="h-2.5 w-2.5 fill-current" aria-hidden /> Abbrechen
        </button>
      </div>
      <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground/70">
        Du kannst währenddessen weiterlesen oder die App schließen — der Bericht
        erscheint hier im Gespräch, sobald er fertig ist.
        {/* Nur in der App: Der Push kommt über APNs/FCM, im Browser gibt es
            kein Gerät, dem man etwas schicken könnte. Erst nach dem Mount
            prüfen, sonst weicht das Markup des statischen Exports ab. */}
        {nativ && " Wir melden uns, wenn er da ist."}
      </p>
    </div>
  );
}

/** Abbruch mit Teilergebnis (8c⑥): fertige Facetten → Teilbericht anbieten.
 *  Kostet laut Karte ausdrücklich kein Kontingent. */
export function RechercheGestoppt({ fertig, gesamt, teilberichtMoeglich, onTeilbericht, onVerwerfen }: {
  fertig: number; gesamt: number; teilberichtMoeglich: boolean;
  onTeilbericht: () => void; onVerwerfen: () => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-3.5 py-3">
      <p className="text-[13px] font-semibold text-foreground">Recherche abgebrochen</p>
      <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
        {teilberichtMoeglich
          ? <>{fertig} von {gesamt} Facetten waren fertig — die stehen dir als Teilbericht
            zur Verfügung. Das zählt <strong>nicht</strong> gegen dein Tageskontingent.</>
          : <>Es war noch keine Facette fertig. Das zählt <strong>nicht</strong> gegen
            dein Tageskontingent.</>}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {teilberichtMoeglich && (
          <button type="button" onClick={onTeilbericht}
            className="inline-flex items-center rounded-[10px] bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
            Teilbericht zeigen
          </button>
        )}
        <button type="button" onClick={onVerwerfen}
          className="inline-flex items-center rounded-[10px] border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          Verwerfen
        </button>
      </div>
    </div>
  );
}

/** Fehler (8c⑦): Funde sind serverseitig gesichert, „Fortsetzen" startet die
 *  Recherche neu (kostet kein Kontingent — Fehler zählen nicht). */
export function RechercheFehlerKarte({ onFortsetzen, onSchnelleFrage }: {
  onFortsetzen: () => void; onSchnelleFrage: () => void;
}) {
  return (
    <div className="rounded-xl border border-signal/30 bg-signal/5 px-3.5 py-3">
      <p className="text-[13px] font-semibold text-foreground">Die Recherche ist abgebrochen</p>
      <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
        Unterwegs ist die Verbindung abgerissen. Deine Frage ist nicht verloren —
        die Recherche kann neu starten. Kein Verbrauch vom Kontingent.
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" onClick={onFortsetzen}
          className="inline-flex items-center gap-1.5 rounded-[10px] bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
          <RotateCcw className="h-3 w-3" aria-hidden /> Fortsetzen
        </button>
        <button type="button" onClick={onSchnelleFrage}
          className="inline-flex items-center rounded-[10px] border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          Als schnelle Frage
        </button>
      </div>
    </div>
  );
}

/** Sprungmarken-Chips über dem Bericht (8b): aus den „## "-Abschnitten,
 *  Pflicht ab 4 Abschnitten (darunter rendert der Aufrufer sie nicht).
 *  Mobil sticky mit aktiver Markierung; die Anker setzt AnswerWithCitations
 *  über das ankerPrefix. */
export function Sprungmarken({ abschnitte, ankerPrefix }: {
  abschnitte: string[]; ankerPrefix: string;
}) {
  const [aktiv, setAktiv] = useState(0);
  const refWrap = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const koepfe = abschnitte
      .map((_, i) => document.getElementById(`${ankerPrefix}-${i}`))
      .filter((el): el is HTMLElement => el !== null);
    if (koepfe.length === 0) return;
    // Scroll-Spy: aktiv ist der LETZTE Kopf über der Lesekante (~140 px unter
    // dem Viewport-Top) — „oberster sichtbarer Kopf" markierte beim Sprung in
    // einen mittleren Abschnitt fälschlich den nächsten, weil der eigene Kopf
    // bereits oben hinausgescrollt war. Der Observer dient nur als Trigger.
    const update = () => {
      let idx = 0;
      koepfe.forEach((el, i) => {
        if (el.getBoundingClientRect().top <= 140) idx = i;
      });
      setAktiv(idx);
    };
    const io = new IntersectionObserver(update, { rootMargin: "-64px 0px -50% 0px" });
    koepfe.forEach((el) => io.observe(el));
    // Observer + Scroll-Listener doppelt: gedrosselte WebViews (App im
    // Hintergrund, eingebettete Panes) lassen IO-Callbacks aussetzen.
    window.addEventListener("scroll", update, { passive: true });
    update();
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", update);
    };
  }, [abschnitte, ankerPrefix]);

  return (
    <div ref={refWrap}
      className="sticky top-[65px] z-10 -mx-1 flex flex-wrap items-center gap-1.5 bg-background/95 px-1 py-1.5 backdrop-blur-sm print:hidden md:top-0 lg:static lg:bg-transparent lg:backdrop-blur-none">
      <span className="mr-0.5 font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        Im Bericht
      </span>
      {abschnitte.map((a, i) => (
        <button key={i} type="button" title={a}
          onClick={() => document.getElementById(`${ankerPrefix}-${i}`)
            ?.scrollIntoView({ behavior: "smooth", block: "start" })}
          className={cn(
            // Kein shrink-0: Ein langer Abschnittstitel („Institutionelle
            // Kulturförderung: MACHIWERK – Oldenburger Fonds für innovative
            // Kulturprojekte") wurde sonst zu einem Chip breiter als das
            // Telefon — und schob die ganze Seite seitlich aus dem Bild.
            // truncate am inneren span: text-ellipsis greift nicht auf dem
            // nackten Textknoten eines Flex-Buttons.
            "inline-flex max-w-full items-center overflow-hidden rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
            i === aktiv
              ? "border-primary/30 bg-primary/[0.06] font-semibold text-primary"
              : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground")}>
          <span className="truncate">{a}</span>
        </button>
      ))}
    </div>
  );
}

/** „Wie es weitergeht" (8b): künftige Beratungsstationen der zitierten
 *  Vorlagen — deterministisch aus dem Sitzungskalender, nie vom Modell. */
export function WieEsWeitergeht({ planungen }: { planungen: Planung[] }) {
  if (planungen.length === 0) return null;
  return (
    <div className="rounded-xl border border-border bg-card px-3.5 py-3">
      <p className="font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-primary">
        Wie es weitergeht
      </p>
      <div className="mt-2 flex flex-col gap-2">
        {planungen.slice(0, 5).map((p, i) => (
          <div key={`${p.kvonr}-${p.datum}-${i}`} className="flex items-start gap-2.5">
            <CalendarDays className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] leading-snug text-foreground">
                {p.vorlage_titel || p.vorlage_nr || "Vorlage"}
              </p>
              <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {p.gremium}{p.datum ? ` · ${fmtDatum(p.datum)}` : ""}
              </p>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10.5px] leading-relaxed text-muted-foreground/70">
        Termine aus dem Sitzungskalender — Ratslotse erinnert dich, wenn du das Thema abonnierst.
      </p>
    </div>
  );
}

/** Abschnittstitel („## …") aus dem Berichtstext ziehen — dieselbe Erkennung
 *  wie AnswerWithCitations, damit Chips und Anker deckungsgleich sind. */
export function berichtAbschnitte(text: string): string[] {
  return text.split("\n")
    .filter((z) => z.trim().startsWith("## "))
    .map((z) => z.trim().replace(/^##\s+/, "").replace(/\[[^\]]*\]/g, "").trim());
}
