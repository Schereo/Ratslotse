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
 *
 * NUR MIT GRAFIKKARTE (seit 11/2026, `failIfMajorPerformanceCaveat`). Bis
 * dahin fragte die Probe nur, OB es einen Kontext gibt. Software-GL gibt aber
 * auch einen her — SwiftShader in Lighthouse/PageSpeed, in VMs, bei
 * gesperrtem Grafiktreiber —, und dann übersetzte die CPU die Shader und
 * rechnete jedes Bild selbst: gemessen rund eine Sekunde lange Tasks beim
 * Laden, danach alle 100 ms ein Bild von 50–80 ms, dazu 190 KB three.js.
 * Mit dem Attribut liefert der Browser in diesem Fall `null`, und es bleibt
 * bei der gezeichneten Familie. Mit Grafikkarte ändert sich nichts — geprüft
 * in Chromium mit ANGLE/Metal und in WebKit (WKWebView) auf einem Mac.
 * Firefox setzt das Attribut nach seiner Grundeinstellung außer Kraft
 * (`webgl.disable-fail-if-major-performance-caveat`); dort nicht nachgemessen.
 */
let gemerkt: boolean | undefined;

const REQUIRE_GPU: WebGLContextAttributes = { failIfMajorPerformanceCaveat: true };

export function webglVerfuegbar(): boolean {
  if (gemerkt !== undefined) return gemerkt;
  if (typeof document === "undefined") return false;
  try {
    const leinwand = document.createElement("canvas");
    const kontext =
      leinwand.getContext("webgl2", REQUIRE_GPU) ??
      leinwand.getContext("webgl", REQUIRE_GPU);
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
