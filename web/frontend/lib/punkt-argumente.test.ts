import { describe, expect, it } from "vitest";
import { askHref, attribution, basisLine, countLine, sourceLabel, type ItemArguments, type Statement } from "./punkt-argumente";

const rede = (id: number, extra: Partial<Statement> = {}): Statement => ({
  text: "Zu teuer.", speaker: "Ratsherr Baak", party: "CDU", body: "Verkehrsausschuss", date: "2026-08-24",
  source: { kind: "speech", id, page: 4, url: "https://example.org/p.pdf#page=4" }, ...extra,
});
const vorlage: Statement = {
  text: "Umsetzbar.", speaker: null, party: null, body: "Vorlage 25/0397", date: null,
  source: { kind: "template", id: 9, page: null, url: "https://example.org/v" },
};
const args = (over: Partial<ItemArguments> = {}): ItemArguments => ({
  subject_key: "tn:25/0397", show_arguments: true, pro_count: 3, contra_count: 2,
  issues: [{ question: "Was kostet es?", pro: [rede(1)], contra: [rede(2, { party: null, speaker: "Dr. Korallus" })] }],
  further: { pro: [rede(1), vorlage], contra: [rede(3)] },
  show_factions: false, factions: [], created_at: null, stale: false, ...over,
});

describe("Urheber und Fundstelle", () => {
  it("Person mit Fraktion, Gremium, Datum", () => {
    expect(attribution(rede(1))).toBe("Ratsherr Baak (CDU) · Verkehrsausschuss · 24.08.2026");
    expect(attribution(rede(1), { party: false })).toBe("Ratsherr Baak · Verkehrsausschuss · 24.08.2026");
  });
  it("ohne Fraktion im Protokoll keine Klammer", () => {
    expect(attribution(rede(1, { party: null, speaker: "Dr. Korallus" }))).toBe("Dr. Korallus · Verkehrsausschuss · 24.08.2026");
  });
  it("die Vorlage spricht als Verwaltung, ohne erfundenes Datum", () => {
    expect(attribution(vorlage)).toBe("Verwaltung · Vorlage 25/0397");
    expect(sourceLabel(vorlage)).toBe("im Ratsinfo");
    expect(sourceLabel(rede(1))).toBe("Protokoll, S. 4");
    expect(sourceLabel(rede(1, { source: { kind: "speech", id: 1, page: null, url: null } }))).toBe("Protokoll");
  });
});

describe("Zählung und Herkunft", () => {
  it("nennt beide Seiten", () => {
    expect(countLine(args())).toBe("3 dafür · 2 dagegen oder mit Bedenken");
  });
  it("zählt Wortbeiträge einmal, die Vorlage als Ganzes", () => {
    expect(basisLine(args())).toBe("aus 3 Wortbeiträgen und der Vorlage");
    expect(basisLine(args({ issues: [], further: { pro: [rede(1)], contra: [] } }))).toBe("aus 1 Wortbeitrag");
  });
});

describe("Dazu fragen", () => {
  it("setzt Bezug und Streitpunkt, die Frage ist die des Streitpunkts", () => {
    const u = new URL(askHref(4654, "Ö 9", args().issues[0]), "https://x.test");
    expect(u.pathname).toBe("/fragen");
    expect(u.searchParams.get("q")).toBe("Was kostet es?");
    expect(u.searchParams.get("chip")).toBe("1");
    expect(u.searchParams.get("ksinr")).toBe("4654");
    expect(u.searchParams.get("top")).toBe("Ö 9");
    expect(u.searchParams.get("streit")).toBe("Was kostet es?");
    expect(u.searchParams.get("streit_text")).toBe("Dafür: Zu teuer. Dagegen: Zu teuer.");
  });
  it("hält den Text kurz", () => {
    const lang = { question: "Q?", pro: Array.from({ length: 40 }, (_, i) => rede(i, { text: "Wort ".repeat(20) })), contra: [] };
    const u = new URL(askHref(1, "Ö 1", lang), "https://x.test");
    expect(u.searchParams.get("streit_text")!.length).toBeLessThanOrEqual(600);
  });
});
