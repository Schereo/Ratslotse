/** Ein Web-Storage, der im Node-Test funktioniert.
 *
 *  Bewusst kein jsdom: Die geprüften Module brauchen vom Browser nichts außer
 *  `localStorage`/`sessionStorage`. Eine ganze DOM-Nachbildung dafür zu laden
 *  kostet Sekunden je Lauf und bringt eine zweite Fassung mit, die man pflegen
 *  müsste.
 */
export function speicherStub(): Storage & { kaputt: (an: boolean) => void } {
  let daten = new Map<string, string>();
  let gesperrt = false;
  const pruefen = () => {
    // Der echte Fall: privates Fenster oder voller Speicher. Beide Module
    // fangen das ab — geprüft wird, dass sie es wirklich tun.
    if (gesperrt) throw new DOMException("QuotaExceededError");
  };
  return {
    get length() { return daten.size; },
    key: (i: number) => [...daten.keys()][i] ?? null,
    getItem: (k: string) => { pruefen(); return daten.get(k) ?? null; },
    setItem: (k: string, v: string) => { pruefen(); daten.set(k, String(v)); },
    removeItem: (k: string) => { pruefen(); daten.delete(k); },
    clear: () => { daten = new Map(); },
    kaputt: (an: boolean) => { gesperrt = an; },
  } as Storage & { kaputt: (an: boolean) => void };
}
