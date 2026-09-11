/**
 * Tippspiel: reine Helfer für `/tipp` (docs/plan-tippspiel-ratswahl.md).
 *
 * Die Punkte kommen fertig gerechnet vom Backend (`GET /api/tipp/…`,
 * `app/prediction/scoring.py`). Hier steht nur, was die Anzeige daraus
 * macht: die Startverteilung des Tippformulars, der Rest-Text der
 * segmentierten Leiste, Rang-Pfeile.
 */
import type { ApiAntwort } from "./vertrag";

export type TippSetup = ApiAntwort<"/tipp/setup">;
export type TippPartei = TippSetup["parties"][number];
export type TippObKandidatur = TippSetup["mayor_candidates"][number];
export type TippMeins = ApiAntwort<"/tipp/me">;
export type TippSitzZeile = TippMeins["seats"][number];
export type TippObZeile = TippMeins["mayor"][number];
export type TippTafel = ApiAntwort<"/tipp/stand">;
export type TippReihe = TippTafel["rows"][number];

/** Schlüssel im localStorage: der geheime Token dieses Geräts. Der Cookie
 *  trägt ihn ohnehin schon (HttpOnly) — dieser Schlüssel ist nur dafür da,
 *  dem Formular OHNE einen Serverblick zu sagen, ob überhaupt schon ein
 *  Cookie gesetzt sein könnte (kein Auslesen des Werts, nur ein Merker). */
export const BEIGETRETEN_SPEICHER = "tipp.beigetreten";

/**
 * Sitze auf 52 verteilen, proportional zu den 2021er Ergebnissen — der
 * Ausgangspunkt, den das Formular zeigt, bevor jemand etwas ändert.
 * Listen ohne 2021er Sitz starten bei 0. Hare/Niemeyer: erst abrunden,
 * dann die größten Reste auffüllen, bis die Summe stimmt.
 */
export function startverteilung(parteien: readonly TippPartei[], gesamt: number): Record<string, number> {
  const gewichte = parteien.map((p) => Math.max(0, p.seats_2021 ?? 0));
  const summeGewichte = gewichte.reduce((s, g) => s + g, 0);
  const out: Record<string, number> = {};
  if (summeGewichte <= 0) {
    parteien.forEach((p) => { out[p.slug] = 0; });
    if (parteien[0]) out[parteien[0].slug] = gesamt;
    return out;
  }
  const roh = gewichte.map((g) => (g / summeGewichte) * gesamt);
  const basis = roh.map(Math.floor);
  let rest = gesamt - basis.reduce((s, b) => s + b, 0);
  const reste = roh.map((r, i) => ({ i, frac: r - basis[i] })).sort((a, b) => b.frac - a.frac);
  for (let k = 0; k < reste.length && rest > 0; k++, rest--) basis[reste[k].i] += 1;
  parteien.forEach((p, i) => { out[p.slug] = basis[i]; });
  return out;
}

/** Summe eines Sitz-Tipps. */
export function summeSitze(tipp: Record<string, number>): number {
  return Object.values(tipp).reduce((s, n) => s + (Number.isFinite(n) ? n : 0), 0);
}

/** Was noch fehlt (positiv) oder zu viel ist (negativ). */
export function restSitze(tipp: Record<string, number>, gesamt: number): number {
  return gesamt - summeSitze(tipp);
}

/** „Noch 3 Sitze" / „2 Sitze zu viel" / „52 von 52 — passt". */
export function restSitzeText(rest: number, gesamt: number): string {
  if (rest === 0) return `${gesamt} von ${gesamt} — passt`;
  if (rest > 0) return `Noch ${rest} Sitz${rest === 1 ? "" : "e"}`;
  return `${Math.abs(rest)} Sitz${Math.abs(rest) === 1 ? "" : "e"} zu viel`;
}

/** Farbton des Rest-Texts: neutral bei 0, sonst Warnung. */
export function restSitzeTon(rest: number): "ok" | "warn" {
  return rest === 0 ? "ok" : "warn";
}

/** Die segmentierte Leiste aus 1d: ein Segment je Liste MIT Sitzen, Breite
 *  in Prozent der Sitzzahl (nicht des Tipp-Rests — eine Leiste, die bei
 *  einem Tipp über der Sitzzahl aus dem Rahmen liefe, wäre kein Fortschritt
 *  mehr, deshalb wird auf `gesamt` gedeckelt). */
export function tippSegmente(
  tipp: Record<string, number>,
  parteien: readonly TippPartei[],
  gesamt: number,
): { slug: string; farbe: string; breite: string }[] {
  let verbraucht = 0;
  const out: { slug: string; farbe: string; breite: string }[] = [];
  for (const p of parteien) {
    const wert = Math.max(0, tipp[p.slug] ?? 0);
    if (wert <= 0) continue;
    const anteil = Math.min(wert, Math.max(0, gesamt - verbraucht));
    verbraucht += wert;
    if (anteil <= 0) continue;
    out.push({ slug: p.slug, farbe: p.color, breite: `${(100 * anteil) / gesamt}%` });
  }
  return out;
}

/** Summe eines OB-Tipps (Prozente). */
export function summeOb(tipp: Record<string, number>): number {
  return Object.values(tipp).reduce((s, n) => s + (Number.isFinite(n) ? n : 0), 0);
}

/** Rest bis 100 % — negativ heißt „schon drüber". Eine Nachkommastelle,
 *  wie die Prozentfelder selbst (Schrittweite 0,5). */
export function restOb(tipp: Record<string, number>): number {
  return Math.round((100 - summeOb(tipp)) * 10) / 10;
}

export function restObText(rest: number): string {
  const text = Math.abs(rest).toFixed(1).replace(".", ",");
  if (Math.abs(rest) < 0.05) return "100,0 % — passt";
  return rest > 0 ? `Noch ${text} %` : `${text} % zu viel`;
}

/** Blockiert das Abgeben nur dort, wo der Server den Tipp ohnehin ablehnen
 *  würde — Summe über 100 % (`_validate_mayor` im Backend lässt bis 100,5 %
 *  Rundungstoleranz durch). Unter 100 % ist ein gültiger Tipp: Die
 *  OB-Prozente sind bewusst „ohne Summenzwang", niemand muss alle neun
 *  Kandidaturen ausfüllen. Vorher stand hier `Math.abs(rest) < 0.05`, was
 *  jeden nicht auf genau 100 % aufgefüllten Tipp blockierte — ein Tipp mit
 *  nur einer eingetragenen Kandidatur ließ sich dadurch nie abgeben.*/
export function restObTon(rest: number): "ok" | "warn" {
  return rest < -0.5 ? "warn" : "ok";
}

/** Rang-Pfeil gegenüber dem vorherigen Stand — `null` ohne Vergleich (erster
 *  Stand des Abends) oder ohne eigenen Rang (kein Tipp/außer Konkurrenz). */
export function rangPfeil(rang: number | null, rangVorher: number | null): { richtung: "auf" | "ab" | "gleich"; um: number } | null {
  if (rang === null || rangVorher === null) return null;
  const diff = rangVorher - rang; // positiv: nach oben gerückt
  if (diff === 0) return { richtung: "gleich", um: 0 };
  return { richtung: diff > 0 ? "auf" : "ab", um: Math.abs(diff) };
}

/** Der Pfeil aus `rangPfeil` als Satz: „3 Plätze vorgerückt" / „unverändert".
 *  „Platz" pluralisiert unregelmäßig (Umlaut) — keine Endung anhängen. */
export function rangDeltaText(pfeil: ReturnType<typeof rangPfeil>): string {
  if (!pfeil) return "";
  if (pfeil.richtung === "gleich") return "unverändert";
  const einheit = pfeil.um === 1 ? "Platz" : "Plätze";
  return pfeil.richtung === "auf" ? `${pfeil.um} ${einheit} vorgerückt` : `${pfeil.um} ${einheit} zurückgefallen`;
}

export function punkteText(n: number): string {
  return `${n} Punkt${n === 1 ? "" : "e"}`;
}

/** „HH:MM" aus einem ISO-Zeitstempel, deutsche Zeit — fürs „Nachgetippt …"-Etikett. */
export function uhrzeitKurz(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
}
