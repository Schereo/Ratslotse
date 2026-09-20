/** Kann dieser Browser überhaupt WebGL? — einmal geprüft, dann gemerkt.
 *
 * Die 3D-Lotti-Szene der Startseite (`components/lotti-szene.tsx`) baut
 * einen `THREE.WebGLRenderer`, und der wirft, wenn der Browser keinen
 * WebGL-Kontext hergibt: Hardware-Beschleunigung aus, ein Browser ohne
 * WebGL, ein Kontext-Limit erreicht. Bis 09/2026 flog diese Ausnahme aus
 * einem `useEffect` bis zur Fehlergrenze der Route, und der Besucher sah
 * statt der Startseite „Etwas ist schiefgelaufen" — fünfmal seit dem
 * 06.09.2026 in der Fehlerliste, immer auf `/`. Die gezeichnete Familie
 * stand die ganze Zeit als Ersatz bereit; sie wurde nur nie gefragt.
 *
 * Die Probe kostet einen eigenen Kontext. Browser erlauben nur eine Handvoll
 * davon je Seite (Chrome: 16), deshalb wird er gleich wieder freigegeben.
 */
let gemerkt: boolean | undefined;

export function webglVerfuegbar(): boolean {
  if (gemerkt !== undefined) return gemerkt;
  if (typeof document === "undefined") return false;
  try {
    const leinwand = document.createElement("canvas");
    const kontext =
      leinwand.getContext("webgl2") ?? leinwand.getContext("webgl");
    if (!kontext) {
      gemerkt = false;
      return false;
    }
    (kontext as WebGLRenderingContext)
      .getExtension("WEBGL_lose_context")
      ?.loseContext();
    gemerkt = true;
  } catch {
    gemerkt = false;
  }
  return gemerkt;
}

/** Nur für Tests: das Gemerkte vergessen. */
export function webglProbeZuruecksetzen(): void {
  gemerkt = undefined;
}
