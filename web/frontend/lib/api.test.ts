import { beforeEach, describe, expect, it, vi } from "vitest";

// Die Hülle, durch die JEDER Backend-Aufruf geht. Sie entscheidet drei Dinge,
// die man an keiner Oberfläche sieht: welche Kopfzeilen mitreisen, was aus
// einem Fehler für ein Satz wird, und was bei einer abgelaufenen Sitzung mit
// dem getippten Text passiert.

const toasts: string[] = [];
vi.mock("sonner", () => ({ toast: { info: (m: string) => { toasts.push(m); } } }));

const gerettet = { text: null as string | null, ziel: null as string | null };
vi.mock("./draft", () => ({
  entwurfSichern: (z: string) => { gerettet.ziel = z; },
  entwurfZiel: () => gerettet.ziel,
}));

let nativ = false;
let token: string | null = null;
vi.mock("./platform", () => ({
  isNativeApp: () => nativ,
  apiBase: () => (nativ ? "https://ratslotse.de" : ""),
  clientMarke: () => "ios",
}));
vi.mock("./token", () => ({ getCachedToken: () => token }));

let a: typeof import("./api");
let letzterRuf: { url: string; init: RequestInit } | null = null;

function antwort(status: number, body?: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => {
      if (body === undefined) throw new Error("kein Körper");
      return body;
    },
  } as Response;
}

beforeEach(async () => {
  toasts.length = 0;
  gerettet.ziel = null;
  nativ = false;
  token = null;
  letzterRuf = null;
  vi.stubGlobal("window", { location: { pathname: "/fragen", search: "?q=x" } });
  vi.resetModules();
  a = await import("./api");
});

const mitAntwort = (res: Response) =>
  vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
    letzterRuf = { url, init };
    return Promise.resolve(res);
  });

describe("Adresse und Kopfzeilen", () => {
  it("hängt /api vor den Pfad und schickt Cookies mit", async () => {
    mitAntwort(antwort(200, { ok: true }));
    await a.api.get("/council/decision?id=1");
    expect(letzterRuf!.url).toBe("/api/council/decision?id=1");
    expect(letzterRuf!.init.credentials).toBe("include");
  });

  it("schickt im Web KEINEN Token und keine Client-Marke", async () => {
    // Im Browser trägt das httpOnly-Cookie die Anmeldung — ein Token im
    // JavaScript wäre eine zusätzliche Angriffsfläche ohne Gegenwert.
    mitAntwort(antwort(200, {}));
    await a.api.get("/x");
    const h = letzterRuf!.init.headers as Record<string, string>;
    expect(h.Authorization).toBeUndefined();
    expect(h["X-Client"]).toBeUndefined();
  });

  it("schickt in der App Token und Plattform", async () => {
    nativ = true; token = "jwt123";
    vi.resetModules(); a = await import("./api");
    mitAntwort(antwort(200, {}));
    await a.api.get("/x");
    const h = letzterRuf!.init.headers as Record<string, string>;
    expect(h.Authorization).toBe("Bearer jwt123");
    expect(h["X-Client"]).toBe("ios");
    expect(letzterRuf!.url).toBe("https://ratslotse.de/api/x");
  });

  it("baut die vier Verben richtig", async () => {
    for (const [name, erwartet] of [["post", "POST"], ["put", "PUT"], ["del", "DELETE"]] as const) {
      mitAntwort(antwort(200, {}));
      await (a.api as never as Record<string, (p: string, b?: unknown) => Promise<unknown>>)[name]("/x", { a: 1 });
      expect(letzterRuf!.init.method).toBe(erwartet);
      expect(letzterRuf!.init.body).toBe(JSON.stringify({ a: 1 }));
    }
  });

  it("schickt ohne Körper auch keinen mit", async () => {
    mitAntwort(antwort(200, {}));
    await a.api.post("/x");
    expect(letzterRuf!.init.body).toBeUndefined();
  });
});

describe("Antworten", () => {
  it("gibt bei 204 nichts zurück, statt am leeren Körper zu scheitern", async () => {
    mitAntwort(antwort(204));
    await expect(a.api.del("/x")).resolves.toBeUndefined();
  });

  it("reicht den Körper durch", async () => {
    mitAntwort(antwort(200, { titel: "x" }));
    await expect(a.api.get("/x")).resolves.toEqual({ titel: "x" });
  });
});

describe("Fehler werden deutsche Sätze", () => {
  it("nimmt ein `detail` als Zeichenkette unverändert", async () => {
    mitAntwort(antwort(400, { detail: "Das Thema gibt es schon." }));
    await expect(a.api.get("/x")).rejects.toThrow("Das Thema gibt es schon.");
  });

  it("übersetzt den ersten Pydantic-Fehler statt rohes JSON zu zeigen", async () => {
    // Vorher stand „[{"type":"value_error","loc":…" in der Oberfläche — im
    // Simulator an einer ungültigen E-Mail gesehen.
    mitAntwort(antwort(422, { detail: [{ loc: ["body", "email"], type: "value_error" }] }));
    await expect(a.api.post("/auth/register")).rejects.toThrow("Diese E-Mail-Adresse ist ungültig.");
  });

  it.each([
    [[{ loc: ["body", "password"], type: "too_short" }], "Passwort ist zu kurz."],
    [[{ loc: ["body", "description"], type: "too_long" }], "Beschreibung ist zu lang."],
    [[{ loc: ["body", "name"], type: "missing" }], "Name fehlt."],
    [[{ loc: ["body", "question"], type: "value_error" }], "Frage ist ungültig."],
    [[{ loc: ["body", "unbekannt"], type: "value_error" }], "unbekannt ist ungültig."],
    [[{}], "Eingabe ungültig."],
    [[], "Eingabe ungültig."],
  ])("%#: %s", async (detail, satz) => {
    mitAntwort(antwort(422, { detail }));
    await expect(a.api.post("/x")).rejects.toThrow(satz);
  });

  it("überspringt „body“ und nimmt den echten Feldnamen", async () => {
    mitAntwort(antwort(422, { detail: [{ loc: ["body"], type: "missing" }] }));
    await expect(a.api.post("/x")).rejects.toThrow("Es fehlt eine Angabe.");
  });

  it("fällt auf den Status zurück, wenn der Körper unlesbar ist", async () => {
    mitAntwort(antwort(500));
    await expect(a.api.get("/x")).rejects.toThrow("Fehler 500");
  });

  it("trägt den Status am Fehler", async () => {
    mitAntwort(antwort(404, { detail: "weg" }));
    await expect(a.api.get("/x")).rejects.toMatchObject({ status: 404, name: "Error" });
    await a.api.get("/x").catch((e) => expect(e).toBeInstanceOf(a.ApiError));
  });
});

describe("Abgelaufene Sitzung", () => {
  it("rettet den getippten Text und sagt das auch", async () => {
    mitAntwort(antwort(401, { detail: "abgelaufen" }));
    const rufe: number[] = [];
    a.setUnauthorizedHandler(() => rufe.push(1));
    await a.api.get("/council/ask").catch(() => {});
    expect(gerettet.ziel).toBe("/fragen?q=x");
    expect(toasts[0]).toContain("dein Text ist gesichert");
    expect(rufe).toHaveLength(1);
  });

  it("greift NICHT auf den Anmelde-Endpunkten", async () => {
    // Ein falsches Passwort ist keine abgelaufene Sitzung — der Nutzer soll
    // die Fehlermeldung des Formulars sehen, nicht rausgeworfen werden.
    mitAntwort(antwort(401, { detail: "falsch" }));
    const rufe: number[] = [];
    a.setUnauthorizedHandler(() => rufe.push(1));
    await a.api.post("/auth/login").catch(() => {});
    expect(rufe).toHaveLength(0);
    expect(toasts).toHaveLength(0);
  });

  it("lässt sich abmelden", async () => {
    mitAntwort(antwort(401, {}));
    const rufe: number[] = [];
    a.setUnauthorizedHandler(() => rufe.push(1));
    a.setUnauthorizedHandler(null);
    await a.api.get("/x").catch(() => {});
    expect(rufe).toHaveLength(0);
  });
});

describe("apiUrl und authHeaders", () => {
  it("apiUrl baut dieselbe Adresse wie der Wrapper", async () => {
    expect(a.apiUrl("/council/ask")).toBe("/api/council/ask");
    nativ = true;
    vi.resetModules(); a = await import("./api");
    expect(a.apiUrl("/council/ask")).toBe("https://ratslotse.de/api/council/ask");
  });

  it("authHeaders ist im Web leer und trägt in der App den Token", async () => {
    expect(a.authHeaders()).toEqual({});
    nativ = true; token = "t";
    vi.resetModules(); a = await import("./api");
    expect(a.authHeaders()).toEqual({ "X-Client": "ios", Authorization: "Bearer t" });
  });
});

describe("qs", () => {
  it("baut eine Abfrage und kodiert beide Seiten", () => {
    expect(a.qs({ q: "a b", n: 3 })).toBe("?q=a%20b&n=3");
    expect(a.qs({ "a&b": "c=d" })).toBe("?a%26b=c%3Dd");
  });

  it("lässt Leeres und Undefiniertes weg", () => {
    expect(a.qs({ a: undefined, b: "", c: "x" })).toBe("?c=x");
  });

  it("gibt bei nichts auch nichts zurück — nicht „?“", () => {
    // Ein nacktes „?" am Ende macht aus zwei gleichen Adressen zwei
    // verschiedene Cache-Schlüssel.
    expect(a.qs({})).toBe("");
    expect(a.qs({ a: undefined })).toBe("");
  });

  it("behält die Null als Wert — sie ist keine Leere", () => {
    expect(a.qs({ n: 0 })).toBe("?n=0");
  });
});
