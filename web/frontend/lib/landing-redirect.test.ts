import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import {
  LANDING_WANTED_COOKIE, SESSION_COOKIE, backendSessionCheck, redirectSignedIn,
} from "./landing-redirect";

// Die Umleitung „angemeldet auf / → /dashboard" läuft auf dem Server, bevor
// irgendetwas von der Seite lädt. Ein Fehler hier sperrt im schlimmsten Fall
// Besuch von außen von der Startseite aus — deshalb jede Abzweigung einzeln.

/** Ein Seitenaufruf, wie ein Browser ihn schickt — `headers` ersetzt die
 *  Vorgabe, z. B. für Next' eigene Abrufe (`Sec-Fetch-Dest: empty`). */
function request(cookies: Record<string, string> = {}, init: { search?: string; headers?: Record<string, string>; method?: string } = {}) {
  const cookie = Object.entries(cookies).map(([k, v]) => `${k}=${v}`).join("; ");
  const browser = { "sec-fetch-dest": "document", accept: "text/html,application/xhtml+xml,*/*;q=0.8" };
  return new NextRequest(`http://localhost:3000/${init.search ?? ""}`, {
    method: init.method ?? "GET",
    headers: { ...(cookie ? { cookie } : {}), ...(init.headers ?? browser) },
  });
}

const passesThrough = (res: Response) => res.headers.get("x-middleware-next") === "1";

describe("redirectSignedIn", () => {
  it("lässt Besuch ohne Cookie durch, ohne das Backend zu fragen", async () => {
    const check = vi.fn(async () => true);
    expect(passesThrough(await redirectSignedIn(request(), check))).toBe(true);
    expect(check).not.toHaveBeenCalled();
  });

  it("leitet eine bestätigte Sitzung aufs Dashboard, ohne Zwischenspeicher", async () => {
    const check = vi.fn(async () => true);
    const res = await redirectSignedIn(request({ [SESSION_COOKIE]: "gueltig" }), check);
    expect(res.status).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/dashboard");
    expect(res.headers.get("cache-control")).toBe("private, no-store");
    expect(check).toHaveBeenCalledWith("gueltig");
  });

  it("zeigt die Landing, wenn das Backend die Sitzung nicht bestätigt (widerrufen, abgelaufen)", async () => {
    const res = await redirectSignedIn(request({ [SESSION_COOKIE]: "widerrufen" }), async () => false);
    expect(passesThrough(res)).toBe(true);
    expect(res.headers.get("location")).toBeNull();
  });

  it("merkt sich die Fluchttür ?start=1 als Sitzungs-Cookie und leitet nicht um", async () => {
    const check = vi.fn(async () => true);
    const res = await redirectSignedIn(request({ [SESSION_COOKIE]: "gueltig" }, { search: "?start=1" }), check);
    expect(passesThrough(res)).toBe(true);
    const setCookie = res.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain(`${LANDING_WANTED_COOKIE}=1`);
    // Sitzungs-Cookie: kein Ablaufdatum.
    expect(setCookie).not.toMatch(/expires|max-age/i);
    expect(check).not.toHaveBeenCalled();
  });

  it("bleibt bei gemerkter Fluchttür auf der Landing", async () => {
    const check = vi.fn(async () => true);
    const res = await redirectSignedIn(request({ [SESSION_COOKIE]: "gueltig", [LANDING_WANTED_COOKIE]: "1" }), check);
    expect(passesThrough(res)).toBe(true);
    expect(check).not.toHaveBeenCalled();
  });

  it("lässt Client-Navigation und Prefetch durch (dort leitet der Rückfall im Browser)", async () => {
    // Next nimmt der Middleware die RSC-Kopfzeilen weg; was bleibt, ist
    // `Sec-Fetch-Dest: empty` und `Accept: */*`.
    const check = vi.fn(async () => true);
    const varianten: Record<string, string>[] = [
      { "sec-fetch-dest": "empty", accept: "*/*" },
      { accept: "*/*" },
    ];
    for (const headers of varianten) {
      expect(passesThrough(await redirectSignedIn(request({ [SESSION_COOKIE]: "gueltig" }, { headers }), check))).toBe(true);
    }
    expect(passesThrough(await redirectSignedIn(request({ [SESSION_COOKIE]: "gueltig" }, { method: "HEAD" }), check))).toBe(true);
    expect(check).not.toHaveBeenCalled();
  });

  it("erkennt einen Seitenaufruf auch ohne Sec-Fetch-Dest am verlangten HTML", async () => {
    const res = await redirectSignedIn(
      request({ [SESSION_COOKIE]: "gueltig" }, { headers: { accept: "text/html" } }), async () => true);
    expect(res.status).toBe(307);
  });
});

describe("backendSessionCheck", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("fragt /api/auth/me mit genau dem Sitzungs-Cookie", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await backendSessionCheck("http://127.0.0.1:8000")("tok")).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/auth/me");
    expect((init.headers as Record<string, string>).cookie).toBe(`${SESSION_COOKIE}=tok`);
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("nimmt 401 und ein unerreichbares Backend als „nicht angemeldet“", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 401 })));
    expect(await backendSessionCheck("http://b")("tok")).toBe(false);
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    expect(await backendSessionCheck("http://b")("tok")).toBe(false);
  });
});
