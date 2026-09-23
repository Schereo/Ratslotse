import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  _vollbildZuruecksetzen,
  meldeVollbild,
  vollbildAktiv,
} from "./vollbild";

describe("vollbild", () => {
  beforeEach(() => _vollbildZuruecksetzen());

  it("ist ohne Ablauf aus", () => {
    expect(vollbildAktiv()).toBe(false);
  });

  it("meldet nur den Wechsel, nicht jede Anmeldung", () => {
    // Kein jsdom in dieser Suite (web/frontend/CLAUDE.md) — ein `window` mit
    // genau dem einen Verb, das der Melder benutzt, reicht für die Zusage.
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", { dispatchEvent, CustomEvent });
    meldeVollbild("onboarding", true);
    meldeVollbild("tour", true);
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    expect(dispatchEvent.mock.calls[0][0].detail).toEqual({ aktiv: true });
    meldeVollbild("onboarding", false);
    meldeVollbild("tour", false);
    expect(dispatchEvent).toHaveBeenCalledTimes(2);
    expect(dispatchEvent.mock.calls[1][0].detail).toEqual({ aktiv: false });
    vi.unstubAllGlobals();
  });

  it("bleibt an, solange noch ein Ablauf steht", () => {
    // Assistent und Tour-Einladung überlappen sich um einen Wimpernschlag:
    // Das Abmelden des einen darf den anderen nicht mit abräumen.
    meldeVollbild("onboarding", true);
    meldeVollbild("tour-einladung", true);
    meldeVollbild("onboarding", false);
    expect(vollbildAktiv()).toBe(true);
    meldeVollbild("tour-einladung", false);
    expect(vollbildAktiv()).toBe(false);
  });

  it("verträgt doppeltes Abmelden", () => {
    meldeVollbild("tour", true);
    meldeVollbild("tour", false);
    meldeVollbild("tour", false);
    expect(vollbildAktiv()).toBe(false);
  });
});
