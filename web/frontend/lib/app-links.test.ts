import { describe, expect, it } from "vitest";
import { appPfad } from "./app-links";

describe("appPfad", () => {
  it("macht aus einem Link auf ratslotse.de den In-App-Pfad", () => {
    expect(appPfad("https://ratslotse.de/verify-email?token=abc")).toBe("/verify-email?token=abc");
    expect(appPfad("https://www.ratslotse.de/g?t=x")).toBe("/g?t=x");
  });
  it("verwirft fremde Schemata, fremde Hosts und Skript-Pfade", () => {
    for (const roh of [
      "x:javascript:alert(1)",
      "javascript:alert(1)",
      "http://ratslotse.de/x",
      "https://evil.example/verify-email",
      "ratslotse://g?t=x",
      "nicht einmal eine Adresse",
    ]) {
      expect(appPfad(roh), roh).toBeNull();
    }
  });
});
