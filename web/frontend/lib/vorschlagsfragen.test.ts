import { describe, expect, it } from "vitest";
import { ERSTE_FRAGE, mischeVorschlaege } from "./vorschlagsfragen";

describe("mischeVorschlaege", () => {
  const fest = [ERSTE_FRAGE, "Was kostet das?", "Was wurde dazu früher beschlossen?"];
  it("nimmt die Fragen des Modells hinter die feste erste", () => {
    expect(mischeVorschlaege(["Was ändert sich bei der Redezeit?"], fest))
      .toEqual([ERSTE_FRAGE, "Was ändert sich bei der Redezeit?"]);
  });
  it("fällt ohne Modell auf die festen Fragen zurück", () => {
    expect(mischeVorschlaege([], fest)).toEqual(fest);
    expect(mischeVorschlaege(null, fest)).toEqual(fest);
  });
  it("kappt auf die Höchstzahl und doppelt die erste nicht", () => {
    expect(mischeVorschlaege([ERSTE_FRAGE, "A?", "B?", "C?"], fest, 3)).toEqual([ERSTE_FRAGE, "A?", "B?"]);
  });
});
