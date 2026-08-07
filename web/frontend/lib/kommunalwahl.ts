import "server-only";

// Der Wahlprogramm-Vergleich liest seine Daten zur BAUZEIT aus dem Repo —
// wie app/changelog/page.tsx das CHANGELOG. Es gibt kein Backend, keine
// Tabelle, keinen Ladezustand: `kommunalwahl/data.json` ist zwischen zwei
// Deploys unveränderlich (Bauplan §5.1).
//
// Ebenso wichtig ist, was diese Datei NICHT tut: den Baum als Ganzes
// exportieren. `data.json` sind 347 KB; was eine Client-Komponente als Prop
// bekommt, landet im RSC-Payload und damit im Download. Deshalb gibt es hier
// nur enge, aufbereitete Schnitte je Ansicht (Bauplan §5.2).

import fs from "node:fs";
import path from "node:path";
import type {
  Alleinstellung,
  Beleg,
  KartenKante,
  KartenPunkt,
  Kennzahl,
  ListenKachel,
  ListenMarke,
  MatrixZeile,
  NahFern,
  OhneProgramm,
  Quellenart,
  Rohdaten,
  Slug,
  SprachProfil,
  ThemaKey,
  ThemenKachel,
  ThesenStat,
} from "./kommunalwahl-types";

export const WAHLTAG = "2026-09-13";

/* ── Rohdaten (nur innerhalb dieser Datei) ────────────────────────────────── */

let cache: Rohdaten | null = null;

function daten(): Rohdaten {
  if (cache) return cache;
  // Repo-Wurzel liegt zwei Ebenen über web/frontend (wie beim Changelog).
  const p = path.join(process.cwd(), "..", "..", "kommunalwahl", "data.json");
  cache = JSON.parse(fs.readFileSync(p, "utf8")) as Rohdaten;
  return cache;
}

function manifest(): { abgerufen: string; programme: ManifestEintrag[] } {
  const p = path.join(process.cwd(), "..", "..", "kommunalwahl", "quellen", "manifest.json");
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

type ManifestEintrag = {
  slug: Slug;
  liste: string;
  titel: string;
  url: string;
  format: string;
  seiten: number | null;
  pdf: string | null;
  pdf_sha256: string | null;
  pdf_bytes: number | null;
};

/* ── Grundbausteine ───────────────────────────────────────────────────────── */

export function stand(): string {
  // thesen.json trägt den Stand; data.json bündelt ihn nicht separat —
  // das Abrufdatum des Manifests ist dieselbe Erhebung.
  return manifest().abgerufen;
}

export function marke(slug: Slug): ListenMarke {
  const d = daten();
  const m = d.meta[slug];
  return {
    slug,
    kurz: m.kurz,
    farbe: m.farbe,
    farbeDunkel: m.farbe_dunkel,
    landesprogramm: d.quellenart[slug]?.art === "landes",
  };
}

/** Die 9 verglichenen Listen, in amtlicher Reihenfolge (Kandidatenzahl absteigend). */
export function vergleichsSlugs(): Slug[] {
  return daten().vergleich;
}

function anzahlPositionen(slug: Slug): number {
  const p = daten().positionen[slug].positionen;
  return Object.values(p).filter((v) => v.pos !== null).length;
}

const TYP_LABEL: Record<string, string> = {
  partei: "Partei",
  waehlergruppe: "Wählergruppe",
  einzelbewerber: "Einzelbewerber",
};

function quelleKurz(slug: Slug): string {
  const q = daten().quellen[slug];
  if (q.format === "pdf" && q.seiten) return `PDF · ${q.seiten} Seiten`;
  if (q.format === "web") return "Website";
  return "—";
}

/** Link an die Belegstelle im Original: PDF-Viewer springen mit #page=N. */
export function belegHref(slug: Slug, seite: number | null): string | null {
  const q = daten().quellen[slug];
  if (!q.url) return null;
  if (q.seitenlink && seite) return `${q.url}#page=${seite}`;
  return q.url;
}

function alsBeleg(slug: Slug, tid: string): Beleg | null {
  const v = daten().positionen[slug].positionen[tid];
  if (v.pos === null || !v.beleg) return null;
  const q = daten().quellen[slug];
  return {
    ...marke(slug),
    pos: v.pos,
    beleg: v.beleg,
    seite: v.seite,
    href: belegHref(slug, v.seite),
    seitenLabel: v.seite ? `S. ${v.seite}` : q.format === "web" ? "Website" : "Quelle",
  };
}

/* ── Überblick (Design 2a) ───────────────────────────────────────────────── */

export function kennzahlen(): Kennzahl[] {
  const w = daten().fakten.wahl;
  return [
    { wert: String(w.sitze), label: `Sitze (vorher ${w.sitze_vorher})` },
    { wert: String(w.kandidierende), label: "Kandidierende" },
    { wert: String(w.wahlvorschlaege_anzahl), label: "Wahlvorschläge" },
    { wert: String(w.wahlrecht.stimmen), label: "Stimmen pro Person" },
    { wert: `ab ${w.wahlrecht.mindestalter}`, label: "auch EU-Bürger:innen" },
  ];
}

/** Die 16 Segmente des Datenlage-Balkens, in amtlicher Reihenfolge. */
export function datenlageBalken(): { slug: Slug; art: Quellenart }[] {
  const d = daten();
  return d.reihenfolge.map((slug) => ({ slug, art: d.quellenart[slug].art }));
}

function matrixZeile(st: ThesenStat, lage: "strittig" | "einig"): MatrixZeile {
  const d = daten();
  const V = d.vergleich;
  return {
    id: st.id,
    these: st.these,
    hinweis: st.hinweis,
    themaLabel: d.themen[st.thema].kurz,
    n: st.n,
    lage,
    zellen: V.map((slug) => ({
      slug,
      kurz: d.meta[slug].kurz,
      farbe: d.meta[slug].farbe,
      farbeDunkel: d.meta[slug].farbe_dunkel,
      pos: d.positionen[slug].positionen[st.id].pos,
    })),
    belege: V.map((slug) => alsBeleg(slug, st.id)).filter((b): b is Beleg => b !== null),
  };
}

/** 5 strittigste + 3 einigste Thesen — aus den Daten abgeleitet, nie hart
 *  kodiert, und nur über belastbare Thesen (n ≥ min_n). */
export function streitEinigkeit(): { streit: MatrixZeile[]; einig: MatrixZeile[] } {
  const d = daten();
  const belastbar = d.thesen_stat.filter((t) => t.belastbar && t.streit !== null);
  const streit = [...belastbar]
    .sort((a, b) => (b.streit ?? 0) - (a.streit ?? 0))
    .slice(0, 5)
    .map((t) => matrixZeile(t, "strittig"));
  const einig = [...belastbar]
    .sort((a, b) => (a.streit ?? 0) - (b.streit ?? 0) || b.n - a.n)
    .slice(0, 3)
    .map((t) => matrixZeile(t, "einig"));
  return { streit, einig };
}

export function themenKacheln(): ThemenKachel[] {
  const rang = daten().themen_rang;
  const max = Math.max(...rang.map((t) => t.positionen_gesamt));
  return rang.map((t) => ({
    key: t.key,
    label: t.label,
    forderungen: t.positionen_gesamt,
    thesen: t.thesen,
    anteil: Math.round((t.positionen_gesamt / max) * 100),
  }));
}

export function listenKacheln(): ListenKachel[] {
  const d = daten();
  return d.vergleich.map((slug) => {
    const wv = d.fakten.wahlvorschlaege.find((w) => w.slug === slug)!;
    return {
      ...marke(slug),
      amtlich: wv.amtlich,
      typLabel: TYP_LABEL[wv.typ] ?? wv.typ,
      kandidaten: wv.kandidaten,
      quelleKurz: quelleKurz(slug),
      positionen: anzahlPositionen(slug),
      einzeiler: d.klartext.einzeiler[slug] ?? null,
    };
  });
}

export function nahFern(): NahFern[] {
  const d = daten();
  const V = new Set(d.vergleich);
  const paare = Object.entries(d.paare)
    .filter(([k, v]) => v.wert !== null && k.split("|").every((s) => V.has(s)))
    .map(([k, v]) => {
      const [a, b] = k.split("|");
      return { a: marke(a), b: marke(b), wert: v.wert!, n: v.n };
    })
    .sort((x, y) => y.wert - x.wert);
  return [
    ...paare.slice(0, 3).map((p) => ({ ...p, art: "nah" as const })),
    ...paare.slice(-3).map((p) => ({ ...p, art: "fern" as const })),
  ];
}

const ART_LABEL: Record<Quellenart, string> = {
  voll: "Eigenes Programm",
  landes: "Landesprogramm",
  kurz: "Nur Stichpunkte / Porträt",
  keins: "Kein Programm veröffentlicht",
};

/** Die 7 nicht verglichenen Listen — sichtbar, mit Rechercheprotokoll (E2). */
export function ohneProgramm(): OhneProgramm[] {
  const d = daten();
  const V = new Set(d.vergleich);
  return d.reihenfolge
    .filter((slug) => !V.has(slug))
    .map((slug) => {
      const wv = d.fakten.wahlvorschlaege.find((w) => w.slug === slug)!;
      const qa = d.quellenart[slug];
      return {
        slug,
        kurz: d.meta[slug].kurz,
        farbe: d.meta[slug].farbe,
        farbeDunkel: d.meta[slug].farbe_dunkel,
        amtlich: wv.amtlich,
        kandidaten: wv.kandidaten,
        art: qa.art,
        artLabel: ART_LABEL[qa.art],
        begruendung: qa.begruendung,
        protokoll: d.digests[slug]?.programm?.hinweis ?? null,
      };
    });
}

/* ── Themenseite (3a) ────────────────────────────────────────────────────── */

export function themaKeys(): ThemaKey[] {
  return daten().themen_rang.map((t) => t.key);
}

export function themaSeite(key: ThemaKey) {
  const d = daten();
  const rang = d.themen_rang.find((t) => t.key === key);
  if (!rang) return null;
  const stats = d.thesen_stat.filter((t) => t.thema === key);
  const mitKapitel = d.vergleich.filter((s) => (d.abdeckung[s]?.[key]?.praegnanz ?? 0) >= 2).length;
  const idx = d.themen_rang.findIndex((t) => t.key === key);
  const nachbar = (i: number) => {
    const t = d.themen_rang[(i + d.themen_rang.length) % d.themen_rang.length];
    return { key: t.key, label: t.kurz };
  };
  return {
    key,
    label: rang.label,
    thesen: stats.length,
    forderungen: rang.positionen_gesamt,
    mitKapitel,
    zeilen: stats.map((t) => matrixZeile(t, (t.streit ?? 0) >= 0.4 ? "strittig" : "einig")),
    forderungenJeListe: d.vergleich.map((slug) => {
      const blk = d.digests[slug]?.themen?.[key];
      return {
        ...marke(slug),
        praegnanz: blk?.praegnanz ?? 0,
        bullets: blk?.positionen ?? [],
        seiten: blk?.seiten ?? [],
        seitenHref: (blk?.seiten ?? []).map((s) => ({ seite: s, href: belegHref(slug, s) })),
      };
    }),
    zurueck: nachbar(idx - 1),
    weiter: nachbar(idx + 1),
  };
}

/* ── Listenprofil (3b) ───────────────────────────────────────────────────── */

export function listeProfil(slug: Slug) {
  const d = daten();
  if (!d.vergleich.includes(slug)) return null;
  const wv = d.fakten.wahlvorschlaege.find((w) => w.slug === slug)!;
  const g = d.digests[slug];
  const q = d.quellen[slug];
  const man = manifest().programme.find((p) => p.slug === slug) ?? null;

  const V = new Set(d.vergleich);
  const paare = Object.entries(d.paare)
    .filter(([k, v]) => v.wert !== null && k.includes(slug) && k.split("|").every((s) => V.has(s)))
    .map(([k, v]) => {
      const anderer = k.split("|").find((s) => s !== slug)!;
      return { ...marke(anderer), wert: v.wert!, n: v.n };
    })
    .sort((a, b) => b.wert - a.wert);

  return {
    ...marke(slug),
    amtlich: wv.amtlich,
    typLabel: TYP_LABEL[wv.typ] ?? wv.typ,
    kandidaten: wv.kandidaten,
    wahlbereiche: wv.wahlbereiche,
    einzeiler: d.klartext.einzeiler[slug] ?? null,
    quelle: {
      titel: g.programm.titel,
      url: q.url,
      format: q.format,
      seiten: q.seiten,
      standQuelle: g.programm.stand,
      hinweis: g.programm.hinweis,
      seitenlink: q.seitenlink,
      domain: q.url ? new URL(q.url).hostname.replace(/^www\./, "") : null,
      // Prüfbar = es gibt eine ausgewertete PDF mit hinterlegter Prüfsumme —
      // dann fragt die Seite den Quellen-Check-Endpunkt (Original verändert?).
      pruefbar: Boolean(man?.pdf_sha256 && q.format === "pdf"),
    },
    charakter: g.charakter,
    kernpunkte: g.kernpunkte ?? [],
    besonderes: g.besonderes ?? [],
    themen: d.themen_rang.map((t) => {
      const blk = g.themen?.[t.key];
      return {
        key: t.key,
        label: t.label,
        praegnanz: blk?.praegnanz ?? 0,
        bullets: blk?.positionen ?? [],
        seitenHref: (blk?.seiten ?? []).map((s) => ({ seite: s, href: belegHref(slug, s) })),
      };
    }),
    naechste: paare.slice(0, 3),
    fernste: paare.slice(-3).reverse(),
    positionen: anzahlPositionen(slug),
    thesen: d.thesen.map((t) => {
      const v = d.positionen[slug].positionen[t.id];
      return {
        id: t.id,
        these: t.these,
        themaKurz: d.themen[t.thema].kurz,
        pos: v.pos,
        beleg: v.beleg,
        seite: v.seite,
        href: v.pos !== null ? belegHref(slug, v.seite) : null,
        seitenLabel: v.seite ? `S. ${v.seite}` : q.format === "web" ? "Website" : "Quelle",
      };
    }),
  };
}

/* ── Nähe (3c) ───────────────────────────────────────────────────────────── */

export function naeheMatrix() {
  const d = daten();
  const V = d.vergleich;
  const zelle = (a: Slug, b: Slug) => {
    if (a === b) return null;
    const p = d.paare[`${a}|${b}`] ?? d.paare[`${b}|${a}`];
    return p ? { wert: p.wert, n: p.n } : null;
  };
  return {
    listen: V.map((s) => marke(s)),
    minN: d.min_n,
    zeilen: V.map((a) => ({ marke: marke(a), zellen: V.map((b) => zelle(a, b)) })),
  };
}

/** Kompakter Datensatz für die interaktive Nähe-Ansicht: Thesen und Belege
 *  als Lookup, Paar-Details nur als ID-Listen — sonst stünde jeder Thesentext
 *  36-mal im Payload. */
export function naeheDaten() {
  const d = daten();
  const V = d.vergleich;
  const thesen: Record<string, { these: string; themaKurz: string }> = {};
  for (const t of d.thesen) thesen[t.id] = { these: t.these, themaKurz: d.themen[t.thema].kurz };

  const belege: Record<string, Beleg> = {};
  const brauche = (slug: Slug, tid: string) => {
    const key = `${slug}:${tid}`;
    if (!belege[key]) {
      const b = alsBeleg(slug, tid);
      if (b) belege[key] = b;
    }
  };

  const paare: Record<
    string,
    { wert: number | null; n: number; einig: string[]; teils: string[]; dissens: string[] }
  > = {};
  for (let i = 0; i < V.length; i++) {
    for (let j = i + 1; j < V.length; j++) {
      const [a, b] = [V[i], V[j]];
      const p = d.paare[`${a}|${b}`];
      const einig: string[] = [];
      const teils: string[] = [];
      const dissens: string[] = [];
      for (const t of d.thesen) {
        const va = d.positionen[a].positionen[t.id].pos;
        const vb = d.positionen[b].positionen[t.id].pos;
        if (va === null || vb === null) continue;
        if (va === 0 && vb === 0) teils.push(t.id);
        else if (va === vb) einig.push(t.id);
        else if (Math.abs(va - vb) === 2) {
          dissens.push(t.id);
          brauche(a, t.id);
          brauche(b, t.id);
        }
      }
      paare[`${a}|${b}`] = { wert: p.wert, n: p.n, einig, teils, dissens };
    }
  }

  return { listen: V.map((s) => marke(s)), minN: d.min_n, thesen, belege, paare };
}

/* ── Ausbau: Landkarte, Alleinstellungen, Sprachprofil, Fingerabdruck ────── */

/** Die Nähe-Landkarte: MDS-Punkte plus die Kanten der nächsten Paare (≥ 70 %). */
export function landkarte(): { punkte: KartenPunkt[]; kanten: KartenKante[] } {
  const d = daten();
  const punkte = d.landkarte.map((p) => ({ ...marke(p.slug), x: p.x, y: p.y }));
  const V = new Set(d.vergleich);
  const kanten = Object.entries(d.paare)
    .filter(([k, v]) => v.wert !== null && v.wert >= 70 && k.split("|").every((s) => V.has(s)))
    .map(([k, v]) => {
      const [a, b] = k.split("|");
      return { a, b, wert: v.wert! };
    });
  return { punkte, kanten };
}

/** Die Überraschungs-Karten: Positionen, mit denen eine Liste allein steht. */
export function alleinstellungen(max = 6): Alleinstellung[] {
  const d = daten();
  return d.alleinstellungen.slice(0, max).map((a) => {
    const q = d.quellen[a.slug];
    return {
      art: a.art,
      id: a.id,
      these: a.these,
      themaLabel: d.themen[a.thema].kurz,
      marke: marke(a.slug),
      pos: a.pos,
      beleg: a.beleg,
      href: a.pos !== null ? belegHref(a.slug, a.seite) : null,
      seitenLabel: a.seite ? `S. ${a.seite}` : q.format === "web" ? "Website" : "Quelle",
      n: a.n,
      dagegen: a.dagegen.map((s) => marke(s)),
      teils: a.teils.map((s) => marke(s)),
    };
  });
}

export function sprachProfil(slug: Slug): SprachProfil | null {
  const sp = daten().sprache[slug];
  if (!sp) return null;
  return {
    woerter: sp.woerter,
    satzlaenge: sp.satzlaenge,
    lix: sp.lix,
    lixLabel: sp.lix_label,
    begriffe: sp.begriffe,
  };
}

/** Themen-Fingerabdruck: Forderungen je Feld als Anteil am stärksten Feld der
 *  Liste — ergibt eine je Liste unterscheidbare Silhouette. Die Prägnanz (0–3)
 *  taugt dafür nicht: Bei den großen Programmen steht sie fast überall auf 3,
 *  und ein durchgehend volles Muster sagt nichts. Misst weiterhin nur
 *  Aufmerksamkeit, nie Richtung (Bauplan E7 bleibt gewahrt). */
export function fingerabdruck(
  slug: Slug,
): { key: ThemaKey; kurz: string; anzahl: number; anteil: number }[] {
  const d = daten();
  const felder = d.themen_rang.map((t) => ({
    key: t.key,
    kurz: t.kurz,
    anzahl: d.abdeckung[slug]?.[t.key]?.anzahl ?? 0,
  }));
  const max = Math.max(1, ...felder.map((f) => f.anzahl));
  return felder.map((f) => ({ ...f, anteil: f.anzahl / max }));
}

/** Datensatz für den Thesen-Check (Design 4): alle 44 Thesen, alle Positionen
 *  und Belege der Vergleichslisten. Der Check rechnet im Client mit derselben
 *  Formel wie die Paar-Ähnlichkeit — Antworten bleiben auf dem Gerät. */
export function checkDaten(): import("./kommunalwahl-types").CheckDaten {
  const d = daten();
  const V = d.vergleich;
  const positionen: Record<Slug, Record<string, import("./kommunalwahl-types").Pos>> = {};
  const belege: Record<string, Beleg> = {};
  for (const slug of V) {
    positionen[slug] = {};
    for (const t of d.thesen) {
      const pos = d.positionen[slug].positionen[t.id].pos;
      positionen[slug][t.id] = pos;
      if (pos !== null) {
        const b = alsBeleg(slug, t.id);
        if (b) belege[`${slug}:${t.id}`] = b;
      }
    }
  }
  return {
    listen: V.map((s) => marke(s)),
    minN: d.min_n,
    thesen: d.thesen.map((t) => ({
      id: t.id,
      these: t.these,
      hinweis: t.hinweis,
      thema: t.thema,
      themaKurz: d.themen[t.thema].kurz,
    })),
    positionen,
    belege,
  };
}

/* ── Methodik (3d) ───────────────────────────────────────────────────────── */

export function methodik() {
  const d = daten();
  const man = manifest();
  return {
    minN: d.min_n,
    abgerufen: man.abgerufen,
    thesen: d.thesen.map((t) => ({
      ...t,
      themaLabel: d.themen[t.thema].kurz,
      stat: d.thesen_stat.find((s) => s.id === t.id)!,
    })),
    // Nur Listen mit einer tatsächlichen Quelle — Piraten/PGM/PARTEI haben
    // nichts veröffentlicht (url: null), die stehen in der Datenlage, nicht hier.
    quellen: man.programme
      .filter((p) => p.url)
      .map((p) => ({
        slug: p.slug,
        liste: p.liste,
        titel: p.titel,
        url: p.url,
        format: p.format,
        seiten: p.seiten,
        sha256: p.pdf_sha256,
        bytes: p.pdf_bytes,
      })),
  };
}
