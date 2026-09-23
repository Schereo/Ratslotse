/**
 * Wann Lotti von selbst anklopfen darf — und wann nicht.
 *
 * **Der Auftrag** (Tim, 21.09.2026): „Vielleicht kann man Lotti auch selten
 * mal einblenden mit ‚Hast du eine Frage zu dem, was du siehst?'" Das Wort,
 * an dem alles hängt, ist **selten**. Ein Hilfe-Knopf, den niemand entdeckt,
 * bringt nichts; eine Blase, die bei jedem dritten Seitenaufruf erscheint,
 * ist Werbung im eigenen Produkt.
 *
 * **Warum die Grenzen hier stehen und nicht in der Komponente.** Sie sind die
 * eigentliche Entscheidung, und jede einzelne lässt sich hier in einer Zeile
 * prüfen (`anstupser.test.ts`). In einer Komponente wären sie über Effekte
 * verteilt und im Browsertest kaum herstellbar — „dreimal in 30 Tagen" müsste
 * man dort mit einer gestellten Uhr über einen Monat spielen.
 *
 * **Das Fenster öffnet sich weiterhin nie von selbst.** Die Blase ist ein
 * Angebot mit zwei Knöpfen; erst ein „Ja" öffnet.
 */

const TAG = 86_400_000;

/** Was sich der Browser merkt. Bewusst klein: vier Werte, kein Protokoll. */
export type AnstupserStand = {
  /** Zeitpunkt des letzten Anstupsers (ms). */
  zuletzt: number;
  /** Die Zeitpunkte der letzten 30 Tage — für den Monatsdeckel. */
  tage30: number[];
  /** Wie oft weggeklickt wurde, seit zuletzt angenommen wurde. */
  abgelehnt: number;
  /** Zeitpunkt des letzten „Ja" (ms), 0 = noch nie. */
  angenommen: number;
};

export const LEER: AnstupserStand = { zuletzt: 0, tage30: [], abgelehnt: 0, angenommen: 0 };

/** Was die Oberfläche über den Moment weiß. */
export type AnstupserKontext = {
  /** Darf auf dieser Seite überhaupt angeklopft werden? (`PageKnowledge.nudge`) */
  seiteErlaubt: boolean;
  /** Sichtbare Lesezeit auf dieser Seite, in Millisekunden. */
  lesezeitMs: number;
  /** Millisekunden seit der letzten Interaktion (Scrollen, Klicken). */
  seitInteraktionMs: number;
  /** Der wievielte Seitenaufruf dieser Sitzung ist das? (1-basiert) */
  seitenInSitzung: number;
  /** War Lottis Fenster in dieser Sitzung schon offen? */
  fensterWarOffen: boolean;
  /** Wurde Lotti heute schon benutzt? */
  heuteBenutzt: boolean;
  /** Steht der Fokus in einem Eingabefeld oder ist Text markiert? */
  beschaeftigt: boolean;
};

/** Die Grenzen, an einer Stelle und benannt. */
export const GRENZEN = {
  /** Erst nach so viel sichtbarer Lesezeit. */
  lesezeitMs: 45_000,
  /** … und nur, wenn kurz vorher etwas passiert ist — sonst ist niemand da. */
  interaktionMs: 10_000,
  /** Die ersten beiden Seiten einer Sitzung bleiben in Ruhe. */
  ersteSeiten: 2,
  /** Höchstens einmal am Tag. */
  proTagMs: TAG,
  /** Höchstens dreimal in 30 Tagen. */
  pro30Tage: 3,
  /** Nach zwei „×" zwei Monate Ruhe. */
  abgelehntBis: 2,
  pauseNachAblehnungMs: 60 * TAG,
  /** Nach einem „Ja" zwei Wochen Ruhe — die Person kennt Lotti jetzt. */
  pauseNachJaMs: 14 * TAG,
} as const;

/**
 * Darf Lotti jetzt anklopfen?
 *
 * Alle Bedingungen müssen gelten. Die Reihenfolge ist die vom Billigen zum
 * Teuren, aber das ist Kosmetik — entscheidend ist, dass **jede** greift.
 */
export function darfAnstupsen(
  stand: AnstupserStand, kontext: AnstupserKontext, jetzt: number,
): boolean {
  if (!kontext.seiteErlaubt) return false;
  if (kontext.beschaeftigt) return false;
  if (kontext.fensterWarOffen || kontext.heuteBenutzt) return false;
  if (kontext.seitenInSitzung <= GRENZEN.ersteSeiten) return false;
  if (kontext.lesezeitMs < GRENZEN.lesezeitMs) return false;
  if (kontext.seitInteraktionMs > GRENZEN.interaktionMs) return false;
  if (jetzt - stand.zuletzt < GRENZEN.proTagMs) return false;
  if (jetzt - stand.angenommen < GRENZEN.pauseNachJaMs) return false;
  if (stand.abgelehnt >= GRENZEN.abgelehntBis
      && jetzt - stand.zuletzt < GRENZEN.pauseNachAblehnungMs) return false;
  if (imFenster(stand.tage30, jetzt).length >= GRENZEN.pro30Tage) return false;
  return true;
}

/** Die Zeitpunkte der letzten 30 Tage — ältere fallen heraus. */
export function imFenster(tage30: number[], jetzt: number): number[] {
  return (tage30 ?? []).filter((t) => jetzt - t < 30 * TAG);
}

/** Der Stand nach einem gezeigten Anstupser. */
export function nachAnzeige(stand: AnstupserStand, jetzt: number): AnstupserStand {
  return { ...stand, zuletzt: jetzt, tage30: [...imFenster(stand.tage30, jetzt), jetzt] };
}

/** Der Stand nach einem „Ja" — der Ablehnungs-Zähler beginnt von vorn. */
export function nachJa(stand: AnstupserStand, jetzt: number): AnstupserStand {
  return { ...stand, angenommen: jetzt, abgelehnt: 0 };
}

/** Der Stand nach einem „×". */
export function nachNein(stand: AnstupserStand): AnstupserStand {
  return { ...stand, abgelehnt: stand.abgelehnt + 1 };
}

const SCHLUESSEL = "ratslotse:lotti-anstupser";

export function leseStand(): AnstupserStand {
  try {
    const roh = localStorage.getItem(SCHLUESSEL);
    if (!roh) return LEER;
    const p = JSON.parse(roh) as Partial<AnstupserStand>;
    return {
      zuletzt: Number(p.zuletzt) || 0,
      tage30: Array.isArray(p.tage30) ? p.tage30.filter((t) => typeof t === "number") : [],
      abgelehnt: Number(p.abgelehnt) || 0,
      angenommen: Number(p.angenommen) || 0,
    };
  } catch {
    // Privates Fenster, gesperrter Speicher: Dann gilt der leere Stand — und
    // die übrigen Grenzen (Lesezeit, erste Seiten, Fenster war offen) halten
    // trotzdem. Ohne Gedächtnis wird häufiger angeklopft; das ist der Preis
    // dafür, dass die Marke nie eine Kennung sein darf.
    return LEER;
  }
}

export function merkeStand(stand: AnstupserStand): void {
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify(stand));
  } catch { /* s. o. */ }
}
