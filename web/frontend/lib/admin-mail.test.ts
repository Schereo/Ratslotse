import { describe, expect, it } from "vitest";
import { mailAnlaesse, mailVerlauf } from "./admin-mail";

describe("Mailstatistik", () => {
  it("behält Lücken, den angeschnittenen Starttag und Monatswechsel auf der Zeitachse", () => {
    expect(mailVerlauf([{ tag: "2026-08-31", mails: 7 }, { tag: "2026-09-02", mails: 2 }], 3, "2026-09-02")).toEqual({
      days: ["2026-08-30", "2026-08-31", "2026-09-01", "2026-09-02"], values: [0, 7, 0, 2],
    });
  });
  it("zeigt Fehlschläge ohne Versand und Aufrufe älterer Mails ohne erfundene Quote", () => {
    const rows = mailAnlaesse({ je_anlass: [{ anlass: "probe", mails: 0, konten: 1, gescheitert: 2 }],
      rueckkehr_je_anlass: [{ anlass: "n6_woche", rueckkehr: 8 }] });
    expect(rows).toEqual([
      { anlass: "probe", mails: 0, konten: 1, gescheitert: 2, rueckkehr: 0 },
      { anlass: "n6_woche", mails: 0, konten: 0, gescheitert: 0, rueckkehr: 8 },
    ]);
  });
});
