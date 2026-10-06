import { describe, expect, it } from "vitest";

import { limitArt } from "./frage-limit";

describe("limitArt", () => {
  it("erkennt das Tageskontingent am Satz des Servers", () => {
    expect(limitArt("Für heute hast du schon 60 Fragen gestellt — ab morgen …")).toBe("tag");
  });

  it("alles andere ist das Fenster", () => {
    expect(limitArt("Zu viele Anfragen. Bitte warte einen Moment.")).toBe("limit");
    expect(limitArt(undefined)).toBe("limit");
    expect(limitArt([{ msg: "x" }])).toBe("limit");
  });
});
