/**
 * Ob der Lotti-Knopf auf diesem Gerät zu sehen ist.
 *
 * **Warum im Browser und nicht im Konto.** Der Knopf schwebt über dem
 * Inhalt — er stört am Rand des Bildschirms, nicht im Konto. Wem er auf dem
 * Telefon im Weg ist, dem ist er am großen Monitor vielleicht recht; eine
 * Konto-Einstellung nähme genau diese Unterscheidung weg. Dieselbe Wahl wie
 * beim Erscheinungsbild, das aus demselben Grund im Gerät wohnt.
 *
 * **Was sie NICHT tut:** Sie schaltet Lotti nicht ab. Über die ⌘K-Palette
 * („Lotti fragen") bleibt sie erreichbar — sonst wäre der versteckte Knopf
 * ein Aus-Schalter mit falschem Namen. Der Knopf „Lotti fragen" an einer
 * Markierung (`components/assistentin/markier-knopf.tsx`) folgt dagegen
 * dieser Einstellung: Wer Lotti aus dem Weg haben will, will auch keinen
 * Knopf an jeder Markierung.
 */
const SCHLUESSEL = "ratslotse:lotti-knopf-aus";

/** Wechselt die Sichtbarkeit — alle Hörer dieses Tabs ziehen nach. */
export const LOTTI_SICHT_EVENT = "ratslotse:lotti-sicht";

export function knopfVersteckt(): boolean {
  try {
    return localStorage.getItem(SCHLUESSEL) === "1";
  } catch {
    // Privater Modus oder gesperrter Speicher: Dann eben sichtbar. Ein
    // unsichtbarer Knopf ohne Weg zurück wäre der schlechtere Ausfall.
    return false;
  }
}

export function setzeKnopfVersteckt(versteckt: boolean): void {
  try {
    if (versteckt) localStorage.setItem(SCHLUESSEL, "1");
    else localStorage.removeItem(SCHLUESSEL);
  } catch {
    /* egal — die Anzeige folgt trotzdem dem Ereignis */
  }
  window.dispatchEvent(new Event(LOTTI_SICHT_EVENT));
}
