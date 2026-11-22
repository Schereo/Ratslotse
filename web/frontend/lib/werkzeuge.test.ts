import { describe, expect, it } from "vitest";
import {
  auswahlAus, auswahlQuery, aufzaehlung, liste, reihenFuer, sitzReihenfolge, uebernehmen, umschalten,
  wahlVon, type Auswahl,
} from "./werkzeuge";

const leer: Auswahl = { gremium: null, dabei: [], ohne: [] };

describe("Auswahl in der Adresse", () => {
  it("liest Listen ohne Leeres und Doppeltes", () => {
    expect(liste(" spd, ,gruene,spd ")).toEqual(["spd", "gruene"]);
    expect(liste(null)).toEqual([]);
  });

  it("lässt „ohne“ gewinnen, wenn ein Block in beiden steht", () => {
    const a = auswahlAus(new URLSearchParams("gremium=rat&dabei=spd,afd&ohne=afd"));
    expect(a).toEqual({ gremium: "rat", dabei: ["spd"], ohne: ["afd"] });
  });

  it("schreibt nur, was gesetzt ist — und liest es unverändert zurück", () => {
    expect(auswahlQuery(leer)).toBe("");
    const a: Auswahl = { gremium: "rat", dabei: ["spd", "gruene"], ohne: ["afd"] };
    expect(auswahlAus(new URLSearchParams(auswahlQuery(a)))).toEqual(a);
  });
});

describe("umschalten", () => {
  it("setzt, wechselt und nimmt wieder heraus", () => {
    let a = umschalten(leer, "spd", "dabei");
    expect(wahlVon(a, "spd")).toBe("dabei");
    a = umschalten(a, "spd", "ohne");
    expect(a.dabei).toEqual([]);
    expect(wahlVon(a, "spd")).toBe("ohne");
    a = umschalten(a, "spd", "ohne");
    expect(wahlVon(a, "spd")).toBeNull();
  });

  it("übernimmt eine Kombination, ohne Ausgeschlossenes hineinzuholen", () => {
    const a = uebernehmen({ gremium: "rat", dabei: ["cdu"], ohne: ["afd"] }, ["gruene", "spd", "afd"]);
    expect(a.dabei).toEqual(["gruene", "spd"]);
    expect(a.ohne).toEqual(["afd"]);
  });
});

describe("Halbkreis", () => {
  it("setzt Gewähltes nach links und Ausgeschlossenes nach rechts", () => {
    const b = ["gruene", "spd", "linke", "cdu", "afd"].map((key) => ({ key }));
    expect(sitzReihenfolge(b, ["cdu"], ["spd"]).map((x) => x.key)).toEqual(["cdu", "gruene", "linke", "afd", "spd"]);
  });

  it("braucht für wenige Sitze nur einen Bogen", () => {
    expect(reihenFuer(6)).toBe(1);
    expect(reihenFuer(11)).toBe(1);
    expect(reihenFuer(16)).toBe(1);
    expect(reihenFuer(53)).toBe(3);
  });
});

it("zählt Namen auf, wie man sie sagt", () => {
  expect(aufzaehlung([])).toBe("");
  expect(aufzaehlung(["Grüne"])).toBe("Grüne");
  expect(aufzaehlung(["Grüne", "SPD", "Linke"])).toBe("Grüne, SPD und Linke");
});
