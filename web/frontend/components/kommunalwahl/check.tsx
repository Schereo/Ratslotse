"use client";

// Der Thesen-Check (Design 4a–4c): Einstieg mit Spielregeln, Durchklicken der
// 44 Thesen mit Ampel-Antworten und ★-Gewichtung, Ergebnis mit derselben
// Formel wie die Paar-Ähnlichkeit — je Liste zählen nur Thesen, zu denen sie
// eine Position hat, n steht immer dabei.
//
// Bewusst KEIN Wahl-O-Mat-Nachbau, sondern Ratslotse-UX — und kein Wahltipp:
// Das Ergebnis ist ein Abgleich mit den Programmen, mehr nicht.
//
// Alle Antworten bleiben lokal (localStorage, Schlüssel kw-check-v1). Kein
// Konto, keine Übertragung — der Server sieht nichts davon.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Mascot } from "@/components/mascot";
import type { Beleg, CheckDaten, Pos } from "@/lib/kommunalwahl-types";
import { AMPEL, BswPill, FarbPunkt, Glyph, KiPlakette } from "./ui";

type Antwort = 1 | 0 | -1 | "skip";
type Stand = { antworten: Record<string, Antwort>; wichtig: string[]; feld: string | null };
type Phase = "start" | "fragen" | "ergebnis";

const SCHLUESSEL = "kw-check-v1";
const LEER: Stand = { antworten: {}, wichtig: [], feld: null };

function lade(): Stand {
  try {
    const roh = localStorage.getItem(SCHLUESSEL);
    if (!roh) return LEER;
    const d = JSON.parse(roh);
    return { antworten: d.antworten ?? {}, wichtig: d.wichtig ?? [], feld: d.feld ?? null };
  } catch {
    return LEER;
  }
}

const WORT: Record<string, string> = { "1": "dafür", "0": "teils", "-1": "dagegen" };

export function ThesenCheck({ daten }: { daten: CheckDaten }) {
  const [stand, setStand] = useState<Stand>(LEER);
  const [phase, setPhase] = useState<Phase>("start");
  const [index, setIndex] = useState(0);
  const [geladen, setGeladen] = useState(false);
  const [feldWahl, setFeldWahl] = useState(false);

  useEffect(() => {
    setStand(lade());
    setGeladen(true);
  }, []);

  const speichere = (neu: Stand) => {
    setStand(neu);
    try {
      localStorage.setItem(SCHLUESSEL, JSON.stringify(neu));
    } catch {
      /* privater Modus o. ä. — der Check läuft trotzdem, nur ohne Merken */
    }
  };

  // Die Fragenmenge: alle 44 oder nur ein Themenfeld.
  const fragen = useMemo(
    () => (stand.feld ? daten.thesen.filter((t) => t.thema === stand.feld) : daten.thesen),
    [daten.thesen, stand.feld],
  );

  const beantwortet = fragen.filter((t) => {
    const a = stand.antworten[t.id];
    return a === 1 || a === 0 || a === -1;
  }).length;
  const uebersprungen = fragen.filter((t) => stand.antworten[t.id] === "skip").length;

  const starte = (feld: string | null) => {
    const neu = { ...stand, feld };
    speichere(neu);
    const menge = feld ? daten.thesen.filter((t) => t.thema === feld) : daten.thesen;
    const erste = menge.findIndex((t) => stand.antworten[t.id] === undefined);
    setIndex(erste === -1 ? 0 : erste);
    setPhase("fragen");
  };

  const antworte = (tid: string, a: Antwort) => {
    speichere({ ...stand, antworten: { ...stand.antworten, [tid]: a } });
    if (index + 1 < fragen.length) setIndex(index + 1);
    else setPhase("ergebnis");
  };

  const themenFelder = useMemo(() => {
    const seen = new Map<string, string>();
    for (const t of daten.thesen) if (!seen.has(t.thema)) seen.set(t.thema, t.themaKurz);
    return [...seen.entries()];
  }, [daten.thesen]);

  if (!geladen) return null;

  if (phase === "start")
    return (
      <Einstieg
        daten={daten}
        vorhanden={beantwortet + uebersprungen}
        feldWahl={feldWahl}
        setFeldWahl={setFeldWahl}
        themenFelder={themenFelder}
        starte={starte}
      />
    );

  if (phase === "fragen")
    return (
      <FrageScreen
        daten={daten}
        fragen={fragen}
        index={index}
        stand={stand}
        beantwortet={beantwortet}
        uebersprungen={uebersprungen}
        antworte={antworte}
        zurueck={() => (index > 0 ? setIndex(index - 1) : setPhase("start"))}
        springe={setIndex}
        zumErgebnis={() => setPhase("ergebnis")}
        toggleWichtig={(tid) =>
          speichere({
            ...stand,
            wichtig: stand.wichtig.includes(tid)
              ? stand.wichtig.filter((x) => x !== tid)
              : [...stand.wichtig, tid],
          })
        }
      />
    );

  return (
    <Ergebnis
      daten={daten}
      fragen={fragen}
      stand={stand}
      beantwortet={beantwortet}
      uebersprungen={uebersprungen}
      aendern={() => {
        setIndex(0);
        setPhase("fragen");
      }}
      nachholen={() => {
        const erste = fragen.findIndex((t) => {
          const a = stand.antworten[t.id];
          return a === "skip" || a === undefined;
        });
        setIndex(erste === -1 ? 0 : erste);
        setPhase("fragen");
      }}
      loesche={() => {
        speichere(LEER);
        try {
          localStorage.removeItem(SCHLUESSEL);
        } catch {}
        setPhase("start");
      }}
    />
  );
}

/* ── 4a Einstieg ─────────────────────────────────────────────────────────── */

const REGELN = [
  ["44 Thesen, dein Tempo", "Jede These lässt sich überspringen — sie zählt dann einfach nicht."],
  ["Wichtiges zählt doppelt", "Markiere Thesen mit ★ — sie gehen mit doppeltem Gewicht ins Ergebnis."],
  ["Bleibt auf deinem Gerät", "Antworten werden nur lokal gespeichert. Kein Konto, keine Übertragung."],
  [
    "Kein Wahltipp",
    "Übereinstimmung ist keine Empfehlung — und gilt nur für Thesen, zu denen eine Liste etwas sagt (n).",
  ],
] as const;

function Einstieg({
  daten,
  vorhanden,
  feldWahl,
  setFeldWahl,
  themenFelder,
  starte,
}: {
  daten: CheckDaten;
  vorhanden: number;
  feldWahl: boolean;
  setFeldWahl: (v: boolean) => void;
  themenFelder: [string, string][];
  starte: (feld: string | null) => void;
}) {
  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col items-center px-4 pb-16 pt-10 text-center sm:pt-12">
      <Mascot pose="point" bob className="h-20 w-20 sm:h-[100px] sm:w-[100px]" />
      <p className="mt-3.5 text-xs font-semibold uppercase tracking-[0.12em] text-primary">Der Thesen-Check</p>
      <h1 className="mt-2.5 font-display text-[28px] font-bold leading-[1.08] tracking-tight [text-wrap:balance] sm:text-[40px]">
        Wo stehst du — verglichen mit den Programmen?
      </h1>
      <p className="mt-3.5 max-w-[56ch] text-[14px] leading-relaxed text-muted-foreground sm:text-[15.5px]">
        Beantworte dieselben 44 Thesen, an denen Ratslotse die Programme misst. Am Ende siehst du, wie
        oft jede Liste mit dir übereinstimmt — Satz für Satz belegt.
      </p>
      <div className="mt-6 grid w-full gap-2.5 text-left sm:grid-cols-2">
        {REGELN.map(([titel, text]) => (
          <div key={titel} className="rounded-[14px] border border-border bg-card px-4 py-3.5">
            <p className="text-[13.5px] font-bold">{titel}</p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{text}</p>
          </div>
        ))}
      </div>
      <span className="mt-4 inline-flex items-center gap-2 rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground">
        <KiPlakette />
        Die Positionen der Listen sind KI-ausgewertet — jede mit Beleg ins Original
      </span>
      {vorhanden > 0 && (
        <p className="mt-4 text-[13px] text-muted-foreground">
          Du hast schon {vorhanden} Thesen bearbeitet — es geht dort weiter, wo du warst.
        </p>
      )}
      <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => starte(null)}
          className="inline-flex rounded-[13px] bg-primary px-7 py-3 text-[15px] font-semibold text-primary-foreground"
        >
          {vorhanden > 0 ? "Weitermachen" : "Check starten"}
        </button>
        <button
          type="button"
          onClick={() => setFeldWahl(!feldWahl)}
          aria-expanded={feldWahl}
          className="inline-flex rounded-[13px] border border-border bg-card px-5 py-3 text-[15px] font-semibold"
        >
          Nur ein Themenfeld
        </button>
      </div>
      {feldWahl && (
        <div className="mt-3.5 flex flex-wrap justify-center gap-1.5">
          {themenFelder.map(([key, kurz]) => (
            <button
              key={key}
              type="button"
              onClick={() => starte(key)}
              className="rounded-full border border-border bg-card px-2.5 py-1 text-[11.5px] font-semibold text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            >
              {kurz}
            </button>
          ))}
        </div>
      )}
      <p className="mt-4 text-xs text-muted-foreground">
        Wie gerechnet wird →{" "}
        <Link href="/kommunalwahl/methodik" className="text-primary">
          Methodik
        </Link>{" "}
        · Dauer: rund 8 Minuten
      </p>
    </div>
  );
}

/* ── 4b Frage-Screen ─────────────────────────────────────────────────────── */

const ANTWORTEN: { wert: 1 | 0 | -1; label: string; rand: string; hover: string }[] = [
  { wert: 1, label: "Dafür", rand: "border-emerald-700/40", hover: "hover:bg-emerald-700/[0.08] hover:border-emerald-700" },
  { wert: 0, label: "Teils / kommt drauf an", rand: "border-amber-600/40", hover: "hover:bg-amber-600/[0.08] hover:border-amber-600" },
  { wert: -1, label: "Dagegen", rand: "border-red-700/40", hover: "hover:bg-red-700/[0.08] hover:border-red-700" },
];

function FrageScreen({
  daten,
  fragen,
  index,
  stand,
  beantwortet,
  uebersprungen,
  antworte,
  zurueck,
  springe,
  zumErgebnis,
  toggleWichtig,
}: {
  daten: CheckDaten;
  fragen: CheckDaten["thesen"];
  index: number;
  stand: Stand;
  beantwortet: number;
  uebersprungen: number;
  antworte: (tid: string, a: Antwort) => void;
  zurueck: () => void;
  springe: (i: number) => void;
  zumErgebnis: () => void;
  toggleWichtig: (tid: string) => void;
}) {
  const t = fragen[index];
  const wichtig = stand.wichtig.includes(t.id);
  const fortschritt = Math.round(((beantwortet + uebersprungen) / fragen.length) * 100);

  return (
    <div className="mx-auto w-full max-w-[820px] px-4 pb-16 pt-9 sm:pt-11">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[13px] font-bold tabular-nums">
          These {index + 1} von {fragen.length}
        </span>
        <span className="text-[11px] font-bold uppercase tracking-wider text-primary">{t.themaKurz}</span>
        <span className="ml-auto text-xs text-muted-foreground">
          {beantwortet} beantwortet · {uebersprungen} übersprungen
        </span>
      </div>
      <div className="mt-2.5 h-1.5 overflow-hidden rounded-[3px] bg-foreground/[0.08]">
        <span className="block h-full rounded-[3px] bg-primary transition-[width] duration-300" style={{ width: `${fortschritt}%` }} />
      </div>
      <p className="mt-1.5 text-right text-[11px] text-muted-foreground">
        Antworten bleiben auf diesem Gerät — später weitermachen geht jederzeit.
      </p>

      <div className="mt-7 text-center sm:mt-9">
        <p className="font-display text-[21px] font-bold leading-[1.3] tracking-tight [text-wrap:balance] sm:text-[29px]">
          {t.these}
        </p>
        {t.hinweis && (
          <p className="mx-auto mt-3 max-w-[68ch] text-[12.5px] leading-relaxed text-muted-foreground sm:text-[13.5px]">
            {t.hinweis}
          </p>
        )}
        <button
          type="button"
          onClick={() => toggleWichtig(t.id)}
          aria-pressed={wichtig}
          className={`mt-4 inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-[12.5px] font-semibold transition-colors ${
            wichtig
              ? "border-signal bg-signal/10 text-signal"
              : "border-border bg-card text-muted-foreground"
          }`}
        >
          ★ {wichtig ? "Besonders wichtig — zählt doppelt" : "Ist mir besonders wichtig"}
          {!wichtig && <span className="font-medium"> — zählt doppelt</span>}
        </button>
      </div>

      <div className="mt-7 grid gap-2.5 sm:grid-cols-3 sm:gap-3">
        {ANTWORTEN.map((a) => (
          <button
            key={a.wert}
            type="button"
            onClick={() => antworte(t.id, a.wert)}
            className={`flex items-center gap-3 rounded-2xl border-[1.5px] bg-card p-3.5 text-left transition-colors sm:flex-col sm:items-center sm:gap-2.5 sm:p-5 sm:text-center ${a.rand} ${a.hover} ${
              stand.antworten[t.id] === a.wert ? "ring-2 ring-ring" : ""
            }`}
          >
            <Glyph pos={a.wert} size={34} className="sm:!h-10 sm:!w-10" />
            <span className="text-[14.5px] font-bold sm:text-[15px]">{a.label}</span>
          </button>
        ))}
      </div>

      <div className="mt-3.5 flex items-center">
        <button type="button" onClick={zurueck} className="text-[13px] font-medium text-primary">
          ← {index === 0 ? "Zum Einstieg" : "Vorherige These"}
        </button>
        <button
          type="button"
          onClick={() => antworte(t.id, "skip")}
          className="mx-auto inline-flex rounded-full border border-border bg-card px-4 py-2 text-[13px] font-semibold text-muted-foreground"
        >
          Keine Meinung — überspringen
        </button>
        <button
          type="button"
          onClick={zumErgebnis}
          disabled={beantwortet === 0}
          className="text-[13px] font-medium text-primary disabled:invisible"
        >
          Zum Ergebnis →
        </button>
      </div>

      <div className="mx-auto mt-8 flex max-w-[640px] flex-wrap justify-center gap-1">
        {fragen.map((f, i) => {
          const a = stand.antworten[f.id];
          const farbe =
            i === index
              ? "hsl(205 92% 34%)"
              : a === 1 || a === 0 || a === -1
                ? AMPEL[String(a) as "1" | "0" | "-1"].bg
                : a === "skip"
                  ? "hsla(212,40%,20%,0.25)"
                  : "hsla(212,40%,20%,0.12)";
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => springe(i)}
              aria-label={`Zu These ${i + 1}`}
              className="h-[9px] w-[9px] rounded-full transition-transform hover:scale-125"
              style={{ background: farbe }}
            />
          );
        })}
      </div>
      <p className="mt-2.5 text-center text-[11.5px] text-muted-foreground">
        Grün/Gelb/Rot = deine Antworten · Blau = aktuelle These · Grau = offen
      </p>
    </div>
  );
}

/* ── 4c Ergebnis ─────────────────────────────────────────────────────────── */

type Zeile = {
  marke: CheckDaten["listen"][0];
  wert: number | null;
  n: number;
  gemeinsam: { tid: string; du: 1 | 0 | -1; liste: 1 | 0 | -1; diff: number; wichtig: boolean }[];
};

function Ergebnis({
  daten,
  fragen,
  stand,
  beantwortet,
  uebersprungen,
  aendern,
  nachholen,
  loesche,
}: {
  daten: CheckDaten;
  fragen: CheckDaten["thesen"];
  stand: Stand;
  beantwortet: number;
  uebersprungen: number;
  aendern: () => void;
  nachholen: () => void;
  loesche: () => void;
}) {
  const [offen, setOffen] = useState<string | null>(null);
  const [alleDetails, setAlleDetails] = useState(false);
  const theseVon = useMemo(() => new Map(daten.thesen.map((t) => [t.id, t])), [daten.thesen]);

  const zeilen = useMemo<Zeile[]>(() => {
    const out: Zeile[] = daten.listen.map((marke) => {
      let summe = 0;
      let gewicht = 0;
      const gemeinsam: Zeile["gemeinsam"] = [];
      for (const t of fragen) {
        const du = stand.antworten[t.id];
        if (du !== 1 && du !== 0 && du !== -1) continue;
        const liste = daten.positionen[marke.slug]?.[t.id];
        if (liste === null || liste === undefined) continue;
        const w = stand.wichtig.includes(t.id) ? 2 : 1;
        summe += (1 - Math.abs(du - liste) / 2) * w;
        gewicht += w;
        gemeinsam.push({ tid: t.id, du, liste, diff: Math.abs(du - liste), wichtig: w === 2 });
      }
      return {
        marke,
        wert: gewicht ? Math.round((100 * summe) / gewicht) : null,
        n: gemeinsam.length,
        gemeinsam,
      };
    });
    out.sort((a, b) => (b.wert ?? -1) - (a.wert ?? -1) || b.n - a.n);
    return out;
  }, [daten, fragen, stand]);

  const doppelt = stand.wichtig.filter((tid) => {
    const a = stand.antworten[tid];
    return a === 1 || a === 0 || a === -1;
  }).length;
  const nachholbar = fragen.length - beantwortet;

  return (
    <div className="mx-auto w-full max-w-[900px] px-4 pb-16 pt-9 sm:pt-11">
      <div className="flex items-end gap-5">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Dein Ergebnis</p>
          <h1 className="mt-2 font-display text-[23px] font-bold leading-[1.1] tracking-tight sm:text-4xl">
            So oft stimmen die Programme mit dir überein.
          </h1>
          <p className="mt-2.5 max-w-[72ch] text-[12.5px] leading-relaxed text-muted-foreground sm:text-[13.5px]">
            {beantwortet} von {fragen.length} Thesen beantwortet
            {doppelt > 0 && <>, {doppelt} doppelt gewichtet</>}. Gezählt werden je Liste nur Thesen, zu
            denen sie eine Position hat — deshalb steht{" "}
            <strong className="font-semibold text-foreground">n</strong> immer dabei. Das ist ein
            Abgleich, <strong className="font-semibold text-foreground">kein Wahltipp</strong>.
          </p>
        </div>
        <Mascot pose="celebrate" bob decorative className="hidden h-[84px] w-[84px] flex-none sm:block" />
      </div>

      <div className="mt-6 overflow-hidden rounded-[18px] border border-border bg-card">
        {zeilen.map((z, i) => (
          <div key={z.marke.slug} className="border-b border-border/60 last:border-b-0">
            <button
              type="button"
              onClick={() => setOffen(offen === z.marke.slug ? null : z.marke.slug)}
              aria-expanded={offen === z.marke.slug}
              className="flex w-full items-center gap-2.5 px-4 py-3 text-left sm:gap-3.5 sm:px-6"
            >
              <span className="w-5 text-[13px] font-bold tabular-nums text-muted-foreground">{i + 1}</span>
              <FarbPunkt farbe={z.marke.farbe} farbeDunkel={z.marke.farbeDunkel} size={11} />
              <span className="w-16 text-[13px] font-bold sm:w-28 sm:text-[14.5px]">{z.marke.kurz}</span>
              {z.marke.landesprogramm && (
                <span className="hidden sm:inline">
                  <BswPill kompakt />
                </span>
              )}
              <span className="inline-flex h-2 flex-1 overflow-hidden rounded-[5px] bg-foreground/[0.07] sm:h-[9px]">
                <span className="rounded-[5px] bg-primary" style={{ width: `${z.wert ?? 0}%` }} />
              </span>
              <span className="w-12 text-right text-[13px] font-bold tabular-nums sm:text-[15px]">
                {z.wert === null ? "—" : `${z.wert} %`}
              </span>
              <span className="w-14 text-[10px] tabular-nums text-muted-foreground sm:w-24 sm:text-[11px]">
                n&thinsp;=&thinsp;{z.n}
                <span className="hidden sm:inline"> gemeinsam</span>
                {z.n > 0 && z.n < daten.minN && <span className="text-amber-700 dark:text-amber-400"> · dünn</span>}
              </span>
              <span className="hidden text-[12.5px] font-semibold text-primary sm:inline">
                Warum? {offen === z.marke.slug ? "⌃" : "⌄"}
              </span>
            </button>
            {offen === z.marke.slug && (
              <WarumBlock
                z={z}
                daten={daten}
                theseVon={theseVon}
                alleDetails={alleDetails}
                setAlleDetails={setAlleDetails}
              />
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          onClick={aendern}
          className="inline-flex rounded-xl border border-border bg-card px-4 py-2 text-[13.5px] font-semibold"
        >
          Antworten ändern
        </button>
        {nachholbar > 0 && (
          <button
            type="button"
            onClick={nachholen}
            className="inline-flex rounded-xl border border-border bg-card px-4 py-2 text-[13.5px] font-semibold"
          >
            Offene nachholen ({nachholbar})
          </button>
        )}
        <button type="button" onClick={loesche} className="ml-auto text-[12.5px] font-medium text-muted-foreground">
          Ergebnis löschen
        </button>
      </div>

      <div className="mt-4 flex items-start gap-3 rounded-[14px] border border-amber-600/35 bg-amber-500/[0.07] px-4 py-3.5">
        <KiPlakette className="mt-0.5 !h-[22px] !w-[34px] text-[10px]" />
        <p className="text-[12.5px] leading-relaxed text-muted-foreground">
          <strong className="font-semibold text-foreground">Kein Wahltipp — und KI-ausgewertet.</strong>{" "}
          Die Positionen der Listen hat eine KI aus den Programmen gelesen; sie kann Fehler machen. Prüf
          die Belege, bevor du Schlüsse ziehst — und lies Werte mit kleinem n vorsichtig. Dein Ergebnis
          bleibt auf diesem Gerät.
        </p>
      </div>
    </div>
  );
}

function WarumBlock({
  z,
  daten,
  theseVon,
  alleDetails,
  setAlleDetails,
}: {
  z: Zeile;
  daten: CheckDaten;
  theseVon: Map<string, CheckDaten["thesen"][0]>;
  alleDetails: boolean;
  setAlleDetails: (v: boolean) => void;
}) {
  const gleich = z.gemeinsam
    .filter((g) => g.diff === 0)
    .sort((a, b) => Number(b.wichtig) - Number(a.wichtig))
    .slice(0, 2);
  const anders = z.gemeinsam
    .filter((g) => g.diff > 0)
    .sort((a, b) => b.diff - a.diff || Number(b.wichtig) - Number(a.wichtig))
    .slice(0, 2);

  const eintrag = (g: Zeile["gemeinsam"][0]) => {
    const t = theseVon.get(g.tid)!;
    const beleg: Beleg | undefined = daten.belege[`${z.marke.slug}:${g.tid}`];
    return (
      <div key={g.tid}>
        <p className="text-[13px] font-semibold leading-snug">
          {g.wichtig && <span className="text-signal">★ </span>}
          {t.these}
        </p>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-muted-foreground">
          <Glyph pos={g.du} size={15} /> Du: {WORT[String(g.du)]}
          <Glyph pos={g.liste} size={15} className="ml-1.5" /> {z.marke.kurz}: {WORT[String(g.liste)]}
          {beleg?.href && (
            <a href={beleg.href} target="_blank" rel="noopener noreferrer" className="text-primary">
              {beleg.seitenLabel} ↗
            </a>
          )}
        </p>
        {beleg && <p className="mt-1 text-xs leading-relaxed text-muted-foreground">»{beleg.beleg}«</p>}
      </div>
    );
  };

  return (
    <div className="border-t border-border/60 bg-background/50 px-4 py-4 sm:px-6">
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-[11.5px] font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
            Ihr stimmt überein — z. B.
          </p>
          {gleich.length ? (
            <div className="flex flex-col gap-3">{gleich.map(eintrag)}</div>
          ) : (
            <p className="text-[12.5px] text-muted-foreground">Keine These mit gleicher Position.</p>
          )}
        </div>
        <div>
          <p className="mb-2 text-[11.5px] font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300">
            Hier nicht — z. B.
          </p>
          {anders.length ? (
            <div className="flex flex-col gap-3">{anders.map(eintrag)}</div>
          ) : (
            <p className="text-[12.5px] text-muted-foreground">Kein Widerspruch bei den gemeinsamen Thesen.</p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={() => setAlleDetails(!alleDetails)}
        className="mt-3.5 text-xs font-semibold text-primary"
      >
        {alleDetails ? "Details einklappen ⌃" : `Alle ${z.n} gemeinsamen Thesen im Detail ⌄`}
      </button>
      {alleDetails && (
        <div className="mt-3 flex flex-col gap-1.5">
          {z.gemeinsam.map((g) => {
            const t = theseVon.get(g.tid)!;
            const beleg = daten.belege[`${z.marke.slug}:${g.tid}`];
            return (
              <p key={g.tid} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                <Glyph pos={g.du} size={13} />
                <Glyph pos={g.liste} size={13} />
                <span className="font-semibold text-foreground">{g.tid}</span>
                <span className="min-w-0 flex-1">{t.these}</span>
                {beleg?.href && (
                  <a href={beleg.href} target="_blank" rel="noopener noreferrer" className="flex-none text-primary">
                    {beleg.seitenLabel} ↗
                  </a>
                )}
              </p>
            );
          })}
          <p className="mt-1 text-[11px] text-muted-foreground">
            Erste Glyphe = deine Antwort, zweite = Position der Liste.
          </p>
        </div>
      )}
    </div>
  );
}
