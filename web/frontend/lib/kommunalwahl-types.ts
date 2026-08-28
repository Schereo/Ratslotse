/** Der Datenbestand aus `kommunalwahl/data.json` (PR #356) — nur die Felder,
 *  die die Oberfläche tatsächlich liest.
 *
 *  Bewusst nicht in `lib/types.ts`: Das ist die Vertragsdatei zum FastAPI-Backend.
 *  Der Wahlprogramm-Bestand kommt zur Bauzeit aus dem Repo und hat mit der API
 *  nichts zu tun.
 */

/** Position zu einer These. `null` heißt: Das Programm sagt dazu nichts —
 *  das ist eine Aussage über das Programm, keine fehlende Angabe. */
export type Pos = 1 | 0 | -1 | null;

export type Slug = string;
export type ThemaKey = string;

export type Meta = { farbe: string; farbe_dunkel: string; kurz: string };

export type Wahlvorschlag = {
  slug: Slug;
  kurz: string;
  amtlich: string;
  typ: "partei" | "waehlergruppe" | "einzelbewerber";
  kandidaten: number;
  wahlbereiche: number;
};

export type Fakten = {
  wahl: {
    termin: string;
    termin_text: string;
    sitze: number;
    sitze_vorher: number;
    kandidierende: number;
    wahlvorschlaege_anzahl: number;
    wahlrecht: { stimmen: number; mindestalter: number; eu_buerger: boolean; hinweis: string };
  };
  wahlvorschlaege: Wahlvorschlag[];
};

export type These = {
  id: string;
  thema: ThemaKey;
  these: string;
  hinweis: string | null;
};

export type ThesenStat = These & {
  n: number;
  dafuer: number;
  teils: number;
  dagegen: number;
  streit: number | null;
  /** n ≥ min_n — ohne diese Schranke führt eine These mit n = 2 die Streitliste an. */
  belastbar: boolean;
};

export type Position = { pos: Pos; beleg: string | null; seite: number | null };

export type Quelle = {
  url: string | null;
  titel: string | null;
  format: "pdf" | "web" | null;
  seiten: number | null;
  stand: string | null;
  archiv_pdf: string | null;
  /** PDF-Viewer springen mit `#page=N` an die Belegstelle. Bei Webquellen false. */
  seitenlink: boolean;
};

/** `voll` = eigenes Kommunalwahlprogramm · `landes` = Landesrahmen ohne
 *  Oldenburg-Bezug (BSW) · `kurz` = nur Stichpunkte · `keins` = nichts gefunden. */
export type Quellenart = "voll" | "landes" | "kurz" | "keins";

export type Digest = {
  slug: Slug;
  programm: {
    gefunden: boolean;
    titel: string | null;
    url: string | null;
    format: string | null;
    seiten: number | null;
    stand: string | null;
    hinweis: string | null;
  };
  charakter: string | null;
  kernpunkte: string[];
  besonderes: string[];
  themen: Record<ThemaKey, { positionen: string[]; seiten: number[]; praegnanz: 0 | 1 | 2 | 3 }>;
};

export type Paar = {
  wert: number | null;
  n: number;
  themen: Record<ThemaKey, { wert: number | null; n: number }>;
};

export type Rohdaten = {
  fakten: Fakten;
  meta: Record<Slug, Meta> & { _hinweis?: string };
  themen: Record<ThemaKey, { label: string; kurz: string }>;
  themen_rang: {
    key: ThemaKey; label: string; kurz: string;
    erwaehnt: number; schwerpunkt: number; positionen_gesamt: number; thesen: number;
  }[];
  quellenart: Record<Slug, { art: Quellenart; begruendung: string }>;
  thesen_stat: ThesenStat[];
  quellen: Record<Slug, Quelle>;
  thesen: These[];
  digests: Record<Slug, Digest>;
  positionen: Record<Slug, { slug: Slug; positionen: Record<string, Position> }>;
  paare: Record<string, Paar>;
  abdeckung: Record<Slug, Record<ThemaKey, { praegnanz: number; anzahl: number }>>;
  min_n: number;
  min_n_thema: number;
  reihenfolge: Slug[];
  /** Die 9 verglichenen Listen. Kommt aus `analyse.py`, damit Frontend und
   *  Auswertung dieselbe Menge meinen. */
  vergleich: Slug[];
  klartext: { einzeiler: Record<Slug, string>; geprueft: boolean };
  /** MDS-Koordinaten der Nähe-Landkarte (Ausbau 08.08.). */
  landkarte: { slug: Slug; x: number; y: number }[];
  /** Positionen, mit denen eine Liste allein steht. */
  alleinstellungen: {
    art: "allein_gegen_alle" | "einzige_aussage";
    id: string;
    thema: ThemaKey;
    these: string;
    slug: Slug;
    pos: 1 | -1;
    beleg: string | null;
    seite: number | null;
    n: number;
    dagegen: Slug[];
    teils: Slug[];
  }[];
  /** Sprachstatistik je Vergleichsliste. */
  sprache: Record<
    Slug,
    {
      woerter: number;
      satzlaenge: number;
      lix: number;
      lix_label: string;
      begriffe: { wort: string; haeufigkeit: number; gewicht: number }[];
    }
  >;
};

/* ── Aufbereitete Formen, die die Ansichten bekommen ───────────────────────── */

export type ListenMarke = {
  slug: Slug;
  kurz: string;
  farbe: string;
  farbeDunkel: string;
  /** BSW: Landesrahmenprogramm ohne Oldenburg-Bezug — trägt überall eine
   *  Markierung, nicht nur auf der Parteikarte (Bauplan E1). */
  landesprogramm: boolean;
};

export type ListenKachel = ListenMarke & {
  amtlich: string;
  typLabel: string;
  kandidaten: number;
  quelleKurz: string;
  positionen: number;
  einzeiler: string | null;
};

export type Beleg = ListenMarke & {
  pos: Exclude<Pos, null>;
  beleg: string;
  seite: number | null;
  /** Fertiger Link ins Originalprogramm, bei PDF mit `#page=N`. */
  href: string | null;
  seitenLabel: string;
};

export type MatrixZeile = {
  id: string;
  these: string;
  hinweis: string | null;
  themaLabel: string;
  n: number;
  lage: "strittig" | "einig";
  /** Eine Zelle je Vergleichsliste, in fester Reihenfolge. */
  zellen: { slug: Slug; kurz: string; farbe: string; farbeDunkel: string; pos: Pos }[];
  belege: Beleg[];
};

export type ThemenKachel = {
  key: ThemaKey;
  label: string;
  forderungen: number;
  thesen: number;
  /** Anteil am stärksten belegten Themenfeld, für den Balken. */
  anteil: number;
};

export type NahFern = {
  a: ListenMarke;
  b: ListenMarke;
  wert: number;
  n: number;
  art: "nah" | "fern";
};

export type OhneProgramm = {
  slug: Slug;
  kurz: string;
  farbe: string;
  farbeDunkel: string;
  amtlich: string;
  kandidaten: number;
  art: Quellenart;
  artLabel: string;
  begruendung: string;
  /** Das Rechercheprotokoll — der Beleg dafür, dass hier nichts übersehen wurde. */
  protokoll: string | null;
};

export type Kennzahl = { wert: string; label: string };

/** Ein Punkt der Nähe-Landkarte (MDS über die 36 Paarabstände, [-1..1]). */
export type KartenPunkt = ListenMarke & { x: number; y: number };

/** Eine Kante der Landkarte: Paare, die sich besonders nah sind. */
export type KartenKante = { a: Slug; b: Slug; wert: number };

/** Eine Position, mit der eine Liste allein steht (Überraschungs-Karte). */
export type Alleinstellung = {
  art: "allein_gegen_alle" | "einzige_aussage";
  id: string;
  these: string;
  themaLabel: string;
  marke: ListenMarke;
  pos: 1 | -1;
  beleg: string | null;
  href: string | null;
  seitenLabel: string;
  n: number;
  dagegen: ListenMarke[];
  teils: ListenMarke[];
};

/** Datensatz für den Thesen-Check (Design 4a–4c): alle Thesen, alle
 *  Positionen der 9 Listen und alle Belege als Lookup — der Check rechnet
 *  vollständig im Client, Antworten verlassen das Gerät nie. */
export type CheckDaten = {
  listen: ListenMarke[];
  minN: number;
  thesen: { id: string; these: string; hinweis: string | null; thema: ThemaKey; themaKurz: string }[];
  /** slug → thesenId → Position (null = keine Aussage). */
  positionen: Record<Slug, Record<string, Pos>>;
  /** `${slug}:${thesenId}` → Beleg (nur für vergebene Positionen). */
  belege: Record<string, Beleg>;
};

/** Sprachstatistik eines Programms (Fakten, keine Wertung). */
export type SprachProfil = {
  woerter: number;
  satzlaenge: number;
  lix: number;
  lixLabel: string;
  begriffe: { wort: string; haeufigkeit: number; gewicht: number }[];
};

/** Kompakter Schnitt für die interaktive Nähe-Ansicht (`naeheDaten()` in
 *  lib/kommunalwahl.ts). Thesen/Belege als Lookup, Paare nur als ID-Listen —
 *  hier dupliziert statt per ReturnType importiert, damit die Client-Komponente
 *  nichts aus dem server-only-Modul zieht. */
export type NaeheDaten = {
  listen: ListenMarke[];
  minN: number;
  thesen: Record<string, { these: string; themaKurz: string }>;
  belege: Record<string, Beleg>;
  paare: Record<
    string,
    { wert: number | null; n: number; einig: string[]; teils: string[]; dissens: string[] }
  >;
};
