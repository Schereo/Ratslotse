import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";

// `api.get` wird ersetzt: Geprüft wird, WIE OFT gefragt wird, nicht das Netz.
const get = vi.fn();
vi.mock("@/lib/api", () => ({ api: { get: (path: string) => get(path) } }));

import { SHARED_TTL_MS, cachedShared, fetchShared, preloadShared } from "@/lib/shared-fetch";

const neu = () => new QueryClient({
  // Dieselbe Wiederholungsregel wie in app/providers.tsx — der geteilte
  // Abruf muss sie ausdrücklich abschalten.
  defaultOptions: { queries: { staleTime: 30_000, retry: (n) => n < 1 } },
});

beforeEach(() => {
  get.mockReset();
  vi.useRealTimers();
});

describe("geteilte Abrufe", () => {
  it("fasst gleichzeitige Abrufe derselben Adresse zu einem zusammen", async () => {
    get.mockResolvedValue({ documents: [1] });
    const c = neu();
    const [a, b] = await Promise.all([
      fetchShared(c, "/council/budget/documents"),
      fetchShared(c, "/council/budget/documents"),
    ]);
    expect(get).toHaveBeenCalledTimes(1);
    expect(a).toEqual({ documents: [1] });
    expect(b).toBe(a);
  });

  it("holt ein Vorladen ab, statt neu zu fragen", async () => {
    get.mockResolvedValue({ ok: true });
    const c = neu();
    preloadShared(c, "/council/budget/data-status");
    await expect(fetchShared(c, "/council/budget/data-status")).resolves.toEqual({ ok: true });
    expect(get).toHaveBeenCalledTimes(1);
    expect(cachedShared(c, "/council/budget/data-status")).toEqual({ ok: true });
  });

  it("bewahrt keinen Fehler auf und wiederholt nicht von selbst", async () => {
    get.mockRejectedValueOnce(new Error("500")).mockResolvedValueOnce({ ok: true });
    const c = neu();
    await expect(fetchShared(c, "/council/budget/debt")).rejects.toThrow("500");
    // Kein automatischer zweiter Versuch (retry: false) …
    expect(get).toHaveBeenCalledTimes(1);
    expect(cachedShared(c, "/council/budget/debt")).toBeNull();
    // … aber der nächste Abruf fragt wieder.
    await expect(fetchShared(c, "/council/budget/debt")).resolves.toEqual({ ok: true });
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("verfällt nach der Gültigkeitsdauer, und `fresh` fragt immer neu", async () => {
    vi.useFakeTimers();
    get.mockResolvedValue({ n: 1 });
    const c = neu();
    await fetchShared(c, "/council/budget/source-stats");
    await fetchShared(c, "/council/budget/source-stats", { fresh: true });
    expect(get).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(SHARED_TTL_MS + 1);
    expect(cachedShared(c, "/council/budget/source-stats")).toBeNull();
  });

  it("ist nach dem Leeren des QueryClients weg — wie bei der Abmeldung", async () => {
    get.mockResolvedValue({ ok: true });
    const c = neu();
    await fetchShared(c, "/council/budget/documents");
    c.clear();
    expect(cachedShared(c, "/council/budget/documents")).toBeNull();
  });
});
