/**
 * Server-Sent Events lesen — an EINER Stelle.
 *
 * **Warum das eine eigene Datei ist.** Der Strom der KI-Frage ist die einzige
 * Nutzlast, die der API-Vertrag nicht beschreibt; geparst wurde er bisher von
 * Hand im Ratsgespräch. Mit Lottis Erklärung kommt ein zweiter Strom dazu, und
 * damit die Frage: zwei Parser oder einer? Zwei wären zwei Stellen, an denen
 * ein Rahmen falsch zusammengesetzt wird, wenn ein Paket mitten in einem
 * Zeichen endet — und genau das passiert über Mobilfunk regelmäßig.
 *
 * Also einer. Er kann genau zwei Dinge, und beide sind der Grund, warum man
 * das nicht nebenbei schreibt:
 *
 * 1. **Rahmen enden auf `\n\n`, Pakete nicht.** Der Rest eines unfertigen
 *    Rahmens bleibt im Puffer und wird vorne an das nächste Paket gehängt.
 * 2. **`TextDecoder` mit `stream: true`.** Ein UTF-8-Zeichen kann über die
 *    Paketgrenze laufen; ohne das Flag entsteht daraus ein Fragezeichen —
 *    im Deutschen also bei jedem zweiten Umlaut.
 *
 * Was hier NICHT hineingehört, ist die Bedeutung der Rahmen. Welcher Typ was
 * auslöst, weiß nur der Aufrufer; diese Datei kennt `data:` und sonst nichts.
 */

/** Ein Rahmen des Stroms: ein JSON-Objekt mit einem Feld `type`. */
export type SseRahmen = { type: string; [k: string]: unknown };

/**
 * Liest einen SSE-Strom bis zum Ende und ruft `onRahmen` je Rahmen.
 *
 * Ein Rahmen, der sich nicht als JSON lesen lässt, wird still übersprungen:
 * Der Strom ist kein Vertrag, und ein halber Rahmen am Ende einer
 * abgebrochenen Verbindung soll die schon empfangenen nicht entwerten.
 */
export async function leseSseStrom(
  body: ReadableStream<Uint8Array>,
  onRahmen: (rahmen: SseRahmen) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const chunks = buf.split("\n\n");
    // Der letzte Teil ist entweder leer (der Strom endete sauber auf \n\n)
    // oder ein angefangener Rahmen — beides gehört zurück in den Puffer.
    buf = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const rahmen = lesRahmen(chunk);
      if (rahmen) onRahmen(rahmen);
    }
  }
}

/** Eine `data:`-Zeile zu einem Rahmen — oder `null`, wenn da nichts Gültiges steht. */
export function lesRahmen(chunk: string): SseRahmen | null {
  const line = chunk.replace(/^data: ?/, "").trim();
  if (!line) return null;
  try {
    const obj = JSON.parse(line) as SseRahmen;
    return obj && typeof obj.type === "string" ? obj : null;
  } catch {
    return null;
  }
}
