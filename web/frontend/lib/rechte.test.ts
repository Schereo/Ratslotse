import { describe, expect, it } from "vitest";
import { darfAdmin, darfHaushalt, hatRecht } from "./rechte";

// Die Rechteprüfung der ganzen Oberfläche. Ein Fehler hier hat zwei Gestalten,
// und beide sind schlimm: jemanden aussperren, der darf — oder jemanden
// hereinlassen, der nicht darf.

describe("hatRecht", () => {
  it("erkennt ein vorhandenes Recht", () => {
    expect(hatRecht({ permissions: ["budget"] }, "budget")).toBe(true);
    expect(hatRecht({ permissions: ["admin", "budget"] }, "admin")).toBe(true);
  });

  it("sagt nein zu einem Recht, das nicht dasteht", () => {
    expect(hatRecht({ permissions: ["budget"] }, "admin")).toBe(false);
    expect(hatRecht({ permissions: [] }, "budget")).toBe(false);
  });

  it("sagt nein, solange kein Konto da ist — auch beim Laden", () => {
    // Absicht: Ein kurz aufblitzender Link, den man gleich darauf nicht mehr
    // anklicken kann, ist schlechter als einer, der später erscheint.
    for (const u of [null, undefined, {}, { permissions: null }, { permissions: undefined }]) {
      expect(hatRecht(u as never, "budget")).toBe(false);
    }
  });

  it("gibt immer einen echten Wahrheitswert zurück, nie undefined", () => {
    // `!!` steht aus einem Grund in der Funktion: `user?.permissions?.includes`
    // liefert sonst `undefined`, und ein `checked={undefined}` macht aus einem
    // kontrollierten Eingabefeld ein unkontrolliertes.
    expect(hatRecht(null, "budget")).toBe(false);
    expect(typeof hatRecht(null, "budget")).toBe("boolean");
  });

  it("prüft genau, nicht auf Teilzeichenketten", () => {
    expect(hatRecht({ permissions: ["budget_readonly"] }, "budget")).toBe(false);
    expect(hatRecht({ permissions: ["superadmin"] }, "admin")).toBe(false);
  });

  it("verlässt sich nicht auf einen Rollennamen", () => {
    // Der Gegenentwurf stand bis 09/2026 an sechs Stellen: `role === "admin"`.
    // Ein Konto mit der Rolle, aber ohne das Recht, darf hier nicht durch.
    expect(hatRecht({ role: "admin", permissions: [] } as never, "admin")).toBe(false);
  });
});

describe("darfHaushalt / darfAdmin", () => {
  it("hängen an ihrem Recht, nicht aneinander", () => {
    const ratsmitglied = { permissions: ["budget"] };
    expect(darfHaushalt(ratsmitglied)).toBe(true);
    expect(darfAdmin(ratsmitglied)).toBe(false);
  });

  it("Admin trägt beides — weil die Registry es so vergibt", () => {
    const admin = { permissions: ["budget", "admin"] };
    expect(darfHaushalt(admin)).toBe(true);
    expect(darfAdmin(admin)).toBe(true);
  });

  it("ein gewöhnliches Konto darf keins von beiden", () => {
    const nutzer = { permissions: [] };
    expect(darfHaushalt(nutzer)).toBe(false);
    expect(darfAdmin(nutzer)).toBe(false);
  });
});
