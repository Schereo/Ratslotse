/** Beschriftungen für die Client-Kennung aus `X-Client` (Backend: app/clients.py).
 *
 *  Eine Stelle für alle drei Orte im Admin-Bereich (Nutzerliste, Nutzer-Detail,
 *  Statistik), damit „ios" nicht an einer Stelle „iPhone" und an der anderen
 *  „iOS-App" heißt.
 */

export type ClientId = "web" | "ios" | "android" | "app" | "unknown";

const LABELS: Record<ClientId, string> = {
  web: "Web",
  ios: "iOS-App",
  android: "Android-App",
  // Ältere App-Stände, die sich noch nicht mit ihrer Plattform meldeten.
  app: "App",
  // Zeilen aus der Zeit vor der Messung. Bewusst NICHT als „Web" gezählt —
  // sie sind ungemessen, nicht web.
  unknown: "vor der Messung",
};

export function clientLabel(id: string): string {
  return LABELS[id as ClientId] ?? id;
}

/** Zählt `web` gegen alles Native — die Frage, die im Alltag interessiert. */
export function istApp(id: string): boolean {
  return id === "ios" || id === "android" || id === "app";
}

/** Farbe im Anteilsbalken. Blau = Browser, Orange-Familie = App — das ist die
 *  Unterscheidung, die man auf einen Blick sehen will.
 *
 *  Die App-Plattformen bekommen trotzdem eigene Abstufungen: Bekämen iOS und
 *  Android dasselbe Orange, verschmölzen sie im Balken zu einem Block, und aus
 *  zwei Werten würde optisch einer. */
const FARBEN: Record<ClientId, string> = {
  web: "bg-primary",
  ios: "bg-signal",
  android: "bg-signal/55",
  app: "bg-signal/30",
  unknown: "bg-muted-foreground/30",
};

export function clientFarbe(id: string): string {
  return FARBEN[id as ClientId] ?? "bg-muted-foreground/30";
}

/** Der meistgenutzte Client eines Kontos — oder `null`, wenn nichts Gemessenes
 *  vorliegt. `unknown` gewinnt nie: Aus einer Zeile von vor der Messung lässt
 *  sich nicht ableiten, womit jemand arbeitet. */
export function hauptClient(clients: Record<string, number>): ClientId | null {
  const gemessen = Object.entries(clients).filter(([id]) => id !== "unknown");
  if (!gemessen.length) return null;
  return gemessen.sort((a, b) => b[1] - a[1])[0][0] as ClientId;
}

/** Kurzfassung fürs Listenzeilen-Chip: „Web", „iOS-App" oder „Web + App".
 *  Zwei Clients heißen ausdrücklich beide — genau das ist die interessante
 *  Auskunft, und ein alleinstehendes „Web" würde die App-Nutzung verschweigen. */
export function clientKurz(clients: Record<string, number>): string | null {
  const gemessen = Object.entries(clients)
    .filter(([id, n]) => id !== "unknown" && n > 0)
    .sort((a, b) => b[1] - a[1]);
  if (!gemessen.length) return null;
  if (gemessen.length === 1) return clientLabel(gemessen[0][0]);
  const hatWeb = gemessen.some(([id]) => id === "web");
  const hatApp = gemessen.some(([id]) => istApp(id));
  if (hatWeb && hatApp) {
    // Der führende steht vorn — „App + Web" heißt: überwiegend App.
    return istApp(gemessen[0][0]) ? "App + Web" : "Web + App";
  }
  return gemessen.map(([id]) => clientLabel(id)).join(" + ");
}
