import { describe, expect, it } from "vitest";
import * as Y from "yjs";
import { forgetInvite, INVITES_MAP, isRecorded, recordInvite } from "./shared-note-invite";

describe("Einladungs-Kennungen in der Notiz", () => {
  it("übergeben wird nur an Kennungen, die ein Mitglied in die Notiz gelegt hat", () => {
    const doc = new Y.Doc();
    const t = recordInvite(doc, 1);
    expect(t).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    expect(isRecorded(doc, t)).toBe(true);
    // Eine Kennung, die nur der Server kennt, steht nicht in der Notiz.
    expect(isRecorded(doc, "erfunden-vom-server")).toBe(false);
    expect(isRecorded(doc, "")).toBe(false);
  });

  it("die Kennung kommt bei den anderen an — und gilt nur einmal und 14 Tage", () => {
    const anna = new Y.Doc();
    const ben = new Y.Doc();
    const t = recordInvite(anna, 1);
    Y.applyUpdate(ben, Y.encodeStateAsUpdate(anna));
    expect(isRecorded(ben, t)).toBe(true);
    expect(isRecorded(ben, t, Date.now() + 15 * 86_400_000)).toBe(false);
    forgetInvite(ben, t);
    Y.applyUpdate(anna, Y.encodeStateAsUpdate(ben));
    expect(isRecorded(anna, t)).toBe(false);
    expect(anna.getMap(INVITES_MAP).size).toBe(0);
  });
});
