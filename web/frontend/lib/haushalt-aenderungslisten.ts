// Typen und Rechenwege für „Was in den Listen stand" — die Inhalts-Ebene
// unter dem Streit-Abschnitt (/haushalt/mitreden#streit).
//
// Die Daten kommen aus `/council/haushalt/aenderungslisten`: je Dokument
// (Verw. I–III, Beschluss-Datei des AFB) die Positionen des
// Haushaltsjahrgangs und die Zusammenstellungen aller Planjahre. Jede
// Positionsliste wurde beim Einlesen gegen ihre eigene Zusammenstellung
// bewiesen (council/aenderungslisten.py) — hier wird nur noch angeordnet.

import type { Herkunft } from "@/lib/herkunft";

export type { Herkunft };

export type AenderungsZeile = {
  jahrgang: number;
  liste: string;
  jahr: number;
  lfd: number;
  /** `null` = die Position gilt pauschal „alle" Teilhaushalte (2019). */
  thh: number | null;
  seite_entwurf: number | null;
  produkt: string | null;
  bezeichnung: string;
  /** Euro, negativ = Minderung; `null` = kein Betrag in dieser Spalte. */
  ertrag: number | null;
  aufwand: number | null;
  /** Die Erläuterungs-Spalte des Dokuments — was diese Änderung ist.
   *  `null` = Zelle leer oder Zuordnung nicht eindeutig (dann lieber gar
   *  kein Text als einer von der falschen Zeile). */
  erlaeuterung: string | null;
  dokument_id: number;
  herkunft_id: number | null;
};

export type AenderungsSumme = {
  jahrgang: number;
  liste: string;
  jahr: number;
  typ: string; // "entwurf" | "liste" | "endsumme"
  label: string;
  ertraege: number;
  aufwendungen: number;
  saldo: number;
  /** 1 = die Zeile, die die Positionen dieses Dokuments summiert. */
  eigene: number;
  dokument_id: number;
  herkunft_id: number | null;
};

export type AenderungslistenDaten = {
  zeilen: AenderungsZeile[];
  summen: AenderungsSumme[];
  herkunft: Record<string, Herkunft>;
};

export function herkunftVon(
  daten: AenderungslistenDaten | null, id: number | null | undefined,
): Herkunft | null {
  return daten && id != null ? daten.herkunft[String(id)] ?? null : null;
}

/** Anzeige-Namen der Dokumente. Die Schlüssel kommen aus
 *  `council/aenderungslisten.py: liste_aus_label` — wer dort einen neuen
 *  ergänzt, zieht ihn hier nach (eine unbekannte Liste erscheint sonst
 *  gar nicht, s. `listenFuerJahr`). */
export const LISTEN_NAME: Record<string, string> = {
  verwaltung_1: "Änderungsliste der Verwaltung I",
  verwaltung_2: "Änderungsliste der Verwaltung II",
  verwaltung_3: "Änderungsliste der Verwaltung III",
  afb_beschlossen: "Beschlossene Änderungen (Finanzausschuss)",
};

/** Verw. I → II → III → Beschluss: die Reihenfolge des Verfahrens. */
const REIHENFOLGE = ["verwaltung_1", "verwaltung_2", "verwaltung_3", "afb_beschlossen"];

export type ListeImJahr = {
  schluessel: string;
  name: string;
  /** Die Positionen des Haushaltsjahrgangs selbst. */
  zeilen: AenderungsZeile[];
  /** Was die Liste im Haushaltsjahrgang unterm Strich bewegt — die „eigene"
   *  Zeile der Zusammenstellung; bei den Beschluss-Dateien, die mehr
   *  einrechnen als sie ausweisen, Endsumme minus Entwurf. `null`, wenn
   *  beides fehlt (dann trägt die Karte keine Summenzeile statt einer
   *  gerechneten, die das Dokument nicht deckt). */
  saldo: { ertraege: number; aufwendungen: number; saldo: number } | null;
  /** Bis zu welchem Planjahr die Liste außerdem ändert — `null`, wenn sie
   *  nur den Jahrgang selbst betrifft. */
  bisPlanjahr: number | null;
  herkunft: Herkunft | null;
};

export function listenFuerJahr(
  daten: AenderungslistenDaten | null, jahr: number | null,
): ListeImJahr[] {
  if (!daten || jahr == null) return [];
  const aus: ListeImJahr[] = [];
  for (const schluessel of REIHENFOLGE) {
    const zeilen = daten.zeilen.filter(
      (z) => z.jahrgang === jahr && z.liste === schluessel);
    if (!zeilen.length) continue;
    const summen = daten.summen.filter(
      (s) => s.jahrgang === jahr && s.liste === schluessel);
    const imJahr = summen.filter((s) => s.jahr === jahr);
    const eigene = imJahr.find((s) => s.eigene === 1);
    const entwurf = imJahr.find((s) => s.typ === "entwurf");
    const ende = imJahr.find((s) => s.typ === "endsumme");
    const saldo = eigene
      ? { ertraege: eigene.ertraege, aufwendungen: eigene.aufwendungen, saldo: eigene.saldo }
      : entwurf && ende
        ? {
            ertraege: ende.ertraege - entwurf.ertraege,
            aufwendungen: ende.aufwendungen - entwurf.aufwendungen,
            saldo: ende.saldo - entwurf.saldo,
          }
        : null;
    const bis = Math.max(...summen.map((s) => s.jahr));
    aus.push({
      schluessel,
      name: LISTEN_NAME[schluessel] ?? schluessel,
      zeilen,
      saldo,
      bisPlanjahr: bis > jahr ? bis : null,
      herkunft: herkunftVon(daten, zeilen[0].herkunft_id),
    });
  }
  return aus;
}

/** Die politischen Zeilen des Jahrgangs — Summen mit Urheber-Label statt
 *  „Änderungsliste …" davor. Es gibt sie nur in den Beschluss-Dateien, und
 *  sie sind der einzige digitale Beleg der Fraktionslisten (die selbst
 *  Tischvorlagen blieben). */
export function politikZeilen(
  daten: AenderungslistenDaten | null, jahr: number | null,
): AenderungsSumme[] {
  if (!daten || jahr == null) return [];
  return daten.summen.filter(
    (s) => s.jahrgang === jahr && s.jahr === jahr && s.typ === "liste"
      && !s.label.includes("nderungsliste"));
}

/** Vorzeichenfester Euro-Betrag fürs Listen-Raster: „+1,73 Mio. €“,
 *  „−218.299 €“, „—“ für „kein Betrag in dieser Spalte“. */
export function deltaBetrag(euro: number | null): string {
  if (euro == null) return "—";
  const abs = Math.abs(euro);
  const zahl = abs >= 1_000_000
    ? `${(abs / 1e6).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} Mio. €`
    : `${Math.round(abs).toLocaleString("de-DE")} €`;
  return `${euro < 0 ? "−" : "+"}${zahl}`;
}
