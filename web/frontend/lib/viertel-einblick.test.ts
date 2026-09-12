import { describe, expect, it } from "vitest";
import { letzterViertelStand, naechsteViertelBeratung, type ViertelTafel } from "./viertel-einblick";

function projekt(id: number, last_date: string | null, stage = "planning", hidden = false): ViertelTafel["projects"][number] {
  return { id, last_date, stage, hidden, first_date: null, project_key: String(id), place_id: "krusenbusch",
    name: "Vorhaben", what: "Beschreibung", when: null, category: "traffic", confidence: 90,
    report_count: 0, reported: false, decisions: [], locations: [] };
}
const termin = (id: number, session_date: string, session_time = "17:00"): ViertelTafel["upcoming"][number] => ({
  id, session_date, session_time, ksinr: id, title: "Beratung", item_number: "Ö 5", kvonr: null, committee: null, location: "",
});

describe("Viertel-Einblick", () => {
  it("wartet bei bereits geladenen Vierteldaten auf das lokale Datum", () => {
    expect(naechsteViertelBeratung([termin(1, "2026-09-12")], "")).toBeUndefined();
  });
  it("wählt die letzte Ratsberatung, auch wenn sie eine Ablehnung ist; versteckte Vorhaben bleiben draußen", () => {
    const projects = [projekt(1, "2026-04-01", "building"), projekt(2, "2026-05-01", "rejected"), projekt(3, "2026-09-01", "planning", true), projekt(4, null)];
    expect(letzterViertelStand(projects)?.id).toBe(2);
    expect(projects.map(p => p.id)).toEqual([1, 2, 3, 4]);
    expect(letzterViertelStand([])).toBeUndefined();
  });
  it("zeigt nur Beratungen ab heute in den nächsten zwei Wochen, nach Datum und Uhrzeit", () => {
    expect(naechsteViertelBeratung([termin(1, "2026-09-11"), termin(2, "2026-09-27")], "2026-09-12")).toBeUndefined();
    expect(naechsteViertelBeratung([termin(2, "2026-09-12", "19:00"), termin(3, "2026-09-26"), termin(1, "2026-09-12", "16:00")], "2026-09-12")?.id).toBe(1);
    expect(naechsteViertelBeratung([termin(1, "2026-09-26")], "2026-09-12")?.id).toBe(1);
  });
});
