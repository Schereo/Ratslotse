import { describe, expect, it } from "vitest";
import { ohneZugang, zugangAus } from "./zugangslink";

const T = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop";

describe("Anmeldelink im Rücksprungziel", () => {
  it("liest Token und Ziel ohne Token", () => {
    expect(zugangAus(`/karte?von=n7_news&ml=${T}`)).toEqual({ token: T, ziel: "/karte?von=n7_news" });
    expect(zugangAus(`/dashboard?lotti=1&ml=${T}`)?.ziel).toBe("/dashboard?lotti=1");
  });
  it("ohne Token oder mit fremdem Ziel: nichts", () => {
    expect(zugangAus("/karte?von=n7_news")).toBeNull();
    expect(zugangAus(`https://fremd.example/?ml=${T}`)).toBeNull();
    expect(zugangAus(`//fremd.example/?ml=${T}`)).toBeNull();
    expect(zugangAus("/karte?ml=kurz")).toBeNull();
  });
  it("räumt das Token aus einer Adresse, lässt den Rest stehen", () => {
    expect(ohneZugang(`/council/ideen?von=n7_news&ml=${T}#oben`)).toBe("/council/ideen?von=n7_news#oben");
    expect(ohneZugang("/karte?ort=x")).toBe("/karte?ort=x");
  });
});
