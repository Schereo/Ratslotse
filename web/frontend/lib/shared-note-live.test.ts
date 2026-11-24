import { describe, expect, it } from "vitest";
import * as Y from "yjs";
import { Awareness } from "y-protocols/awareness";
import { newNoteKey, type NoteKey } from "./shared-note-crypto";
import { SharedNoteLive, TicketRefused, type SocketLike } from "./shared-note-live";

/** Ein Relais im Speicher, das sich verhält wie `routers/shared_notes.py`:
 *  nummeriert, speichert, verteilt, ersetzt Änderungen durch einen Stand. */
class Relais {
  updates: { seq: number; iv: string; ct: string }[] = [];
  snapshot: { seq: number; iv: string; ct: string } | null = null;
  next = 1;
  clients = new Set<FakeSocket>();
  gesendet = 0;

  socket = () => {
    const s = new FakeSocket(this);
    this.clients.add(s);
    queueMicrotask(() => s.onopen?.());
    return s;
  };

  empfangen(von: FakeSocket, m: Record<string, unknown>) {
    const an = (s: FakeSocket, x: object) => queueMicrotask(() => s.offen && s.onmessage?.({ data: JSON.stringify(x) }));
    if (m.t === "sync") {
      const since = m.since as number;
      const snap = this.snapshot && since < this.snapshot.seq ? this.snapshot : null;
      const ab = snap ? snap.seq : since;
      an(von, { t: "sync", snapshot: snap, updates: this.updates.filter((u) => u.seq > ab), next_seq: this.next });
    } else if (m.t === "update") {
      this.gesendet += 1;
      const u = { seq: this.next++, iv: m.iv as string, ct: m.ct as string };
      this.updates.push(u);
      an(von, { t: "ack", c: m.c, seq: u.seq });
      for (const s of this.clients) if (s !== von) an(s, { t: "update", ...u, from: 1 });
    } else if (m.t === "snapshot") {
      const upto = m.upto as number;
      const ok = upto > (this.snapshot?.seq ?? 0) && upto < this.next;
      if (ok) {
        this.snapshot = { seq: upto, iv: m.iv as string, ct: m.ct as string };
        this.updates = this.updates.filter((u) => u.seq > upto);
      }
      an(von, { t: "snapshot", ok, upto });
    } else if (m.t === "awareness") {
      for (const s of this.clients) if (s !== von) an(s, { ...m, from: 1 });
    }
  }
}

class FakeSocket implements SocketLike {
  offen = true;
  onopen: ((ev?: unknown) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  constructor(private relais: Relais) {}
  send(data: string) { if (this.offen) this.relais.empfangen(this, JSON.parse(data)); }
  close(code = 1000) { this.trennen(code); }
  trennen(code: number) {
    if (!this.offen) return;
    this.offen = false;
    this.relais.clients.delete(this);
    queueMicrotask(() => this.onclose?.({ code }));
  }
}

const ruhe = async (ms = 30) => { for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, ms / 5)); };

function client(relais: Relais, nk: NoteKey, extra: Partial<ConstructorParameters<typeof SharedNoteLive>[0]> = {}) {
  const doc = new Y.Doc();
  const awareness = new Awareness(doc);
  const live = new SharedNoteLive({
    noteId: "n1", nk, doc, awareness, ticket: async () => "t", socket: relais.socket, url: () => "test://",
    flushMs: 0, retryMs: [5], ...extra,
  });
  return { doc, awareness, live, text: () => doc.getText("t").toString() };
}

describe("Live-Verbindung einer gemeinsamen Notiz", () => {
  it("zwei schreiben gleichzeitig, beide sehen dasselbe", async () => {
    const relais = new Relais();
    const nk = await newNoteKey();
    const anna = client(relais, nk);
    const ben = client(relais, nk);
    await ruhe();
    expect(anna.live.status).toBe("online");
    anna.doc.getText("t").insert(0, "Hallo ");
    ben.doc.getText("t").insert(0, "Rat");
    await ruhe();
    expect(anna.text()).toBe(ben.text());
    expect(anna.text()).toContain("Hallo ");
    expect(anna.text()).toContain("Rat");
    // Beim Relais liegt nichts im Klartext.
    expect(JSON.stringify(relais.updates)).not.toContain("Hallo");
  });

  it("schnelles Tippen geht als eine zusammengefasste Änderung hinaus", async () => {
    const relais = new Relais();
    const nk = await newNoteKey();
    const anna = client(relais, nk, { flushMs: 20 });
    await ruhe();
    for (const z of "Kosten") anna.doc.getText("t").insert(anna.doc.getText("t").length, z);
    await ruhe(60);
    expect(relais.gesendet).toBe(1);
  });

  it("wer später kommt oder getrennt war, holt alles nach — Offline-Geschriebenes geht danach hinaus", async () => {
    const relais = new Relais();
    const nk = await newNoteKey();
    const anna = client(relais, nk, { retryMs: [80] });
    await ruhe();
    anna.doc.getText("t").insert(0, "eins ");
    await ruhe();
    for (const s of [...relais.clients]) s.trennen(1006);
    await ruhe(5);
    expect(anna.live.status).toBe("offline");
    anna.doc.getText("t").insert(anna.doc.getText("t").length, "zwei");   // offline geschrieben
    await ruhe(200);
    expect(anna.live.status).toBe("online");
    const ben = client(relais, nk);
    await ruhe();
    expect(ben.text()).toBe("eins zwei");
  });

  it("nach vielen Änderungen ersetzt ein Stand die Liste — Neue lesen ihn", async () => {
    const relais = new Relais();
    const nk = await newNoteKey();
    const anna = client(relais, nk, { compactAfter: 3 });
    await ruhe();
    for (let i = 0; i < 5; i++) {
      anna.doc.getText("t").insert(anna.doc.getText("t").length, `${i}`);
      await ruhe(10);
    }
    await ruhe();
    expect(relais.snapshot).not.toBeNull();
    expect(relais.updates.length).toBeLessThan(3);
    const ben = client(relais, nk);
    await ruhe();
    expect(ben.text()).toBe("01234");
  });

  it("mit fremdem Schlüssel kommt nichts an, und nichts bricht", async () => {
    const relais = new Relais();
    const anna = client(relais, await newNoteKey());
    const fremd = client(relais, await newNoteKey());
    await ruhe();
    anna.doc.getText("t").insert(0, "geheim");
    await ruhe();
    expect(fremd.text()).toBe("");
    expect(fremd.live.status).toBe("online");
  });

  it("entfernt: keine neue Verbindung mehr", async () => {
    const relais = new Relais();
    const nk = await newNoteKey();
    let erlaubt = true;
    const anna = client(relais, nk, { ticket: async () => { if (!erlaubt) throw new TicketRefused(); return "t"; } });
    await ruhe();
    for (const s of [...relais.clients]) s.trennen(4403);
    await ruhe();
    expect(anna.live.status).toBe("removed");
    erlaubt = false;
    await ruhe(30);
    expect(relais.clients.size).toBe(0);
  });

  it("die Anwesenheit (Name, Cursor) kommt verschlüsselt beim anderen an", async () => {
    const relais = new Relais();
    const nk = await newNoteKey();
    const anna = client(relais, nk);
    const ben = client(relais, nk);
    await ruhe();
    anna.awareness.setLocalStateField("user", { name: "Anna", color: "#0a6" });
    await new Promise((r) => setTimeout(r, 300));
    await ruhe();
    const states = [...ben.awareness.getStates().values()].map((s) => (s as { user?: { name: string } }).user?.name);
    expect(states).toContain("Anna");
  });
});
