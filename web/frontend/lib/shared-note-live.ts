/* The live connection of a shared note: a Yjs document in the browser, kept
   in step with everyone else's through the server (`routers/shared_notes.py`).

   Everything that leaves the browser is sealed with the note key
   (`lib/shared-note-crypto.ts`): updates, snapshots, presence (cursor and
   name). The server numbers updates (`seq`), stores and relays them.

   - Typing is gathered for a moment (`flushMs`) and sent as ONE merged update.
   - After a gap the connection asks for everything since the last number it
     has (`sync`); what was sent but not confirmed goes again — Yjs applies an
     update twice without harm.
   - Every `compactAfter` updates a member sends a snapshot; the server then
     drops the updates it covers, so a note never becomes an endless log.
   - Messages are handled strictly in order (decrypting is asynchronous; two
     updates applied the other way round would still merge, but the sequence
     numbers would no longer tell what is missing).

   The socket and the ticket are injected, so the tests run two clients and a
   relay in memory. */

import * as Y from "yjs";
import { Awareness, applyAwarenessUpdate, encodeAwarenessUpdate } from "y-protocols/awareness";
import { openBlob, sealBlob, type NoteKey, type Sealed } from "@/lib/shared-note-crypto";

export type LiveStatus = "connecting" | "online" | "offline" | "removed" | "closed";

export interface SocketLike {
  send(data: string): void;
  close(code?: number): void;
  onopen: ((ev?: unknown) => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  onclose: ((ev: { code: number }) => void) | null;
}

export class TicketRefused extends Error {}

export interface LiveOptions {
  noteId: string;
  nk: NoteKey;
  doc: Y.Doc;
  awareness: Awareness;
  /** Eine Einmal-Kennung vom Server; `TicketRefused`, wenn man nicht mehr dabei ist. */
  ticket: () => Promise<string>;
  socket?: (url: string) => SocketLike;
  url?: (noteId: string, ticket: string) => string;
  onStatus?: (s: LiveStatus) => void;
  onPresence?: (online: number[]) => void;
  compactAfter?: number;
  flushMs?: number;
  retryMs?: number[];
}

/** Herkunft entfernter Änderungen — sie gehen nicht noch einmal hinaus. */
export const REMOTE = Symbol("remote");

function defaultSocket(url: string): SocketLike {
  return new WebSocket(url) as unknown as SocketLike;
}

function liveUrl(noteId: string, ticket: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/shared-notes/${encodeURIComponent(noteId)}/live?ticket=${encodeURIComponent(ticket)}`;
}

export class SharedNoteLive {
  status: LiveStatus = "connecting";
  /** Die eigene Konto-Kennung, sobald der Server sie gesagt hat. */
  you: number | null = null;
  private ws: SocketLike | null = null;
  private lastSeq = 0;
  private snapshotSeq = 0;
  private got = new Set<number>();
  private synced = false;
  private pending: Uint8Array[] = [];
  private unacked = new Map<number, Uint8Array>();
  private counter = 0;
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private awTimer: ReturnType<typeof setTimeout> | null = null;
  private awChanged = new Set<number>();
  private retry = 0;
  private stopped = false;
  private compacting = false;
  private inbox: Promise<void> = Promise.resolve();
  private outbox: Promise<void> = Promise.resolve();
  private readonly compactAfter: number;
  private readonly flushMs: number;
  private readonly retryMs: number[];

  constructor(private readonly o: LiveOptions) {
    this.compactAfter = o.compactAfter ?? 200;
    this.flushMs = o.flushMs ?? 60;
    this.retryMs = o.retryMs ?? [1000, 2000, 5000, 10000];
    o.doc.on("update", this.onDoc);
    o.awareness.on("update", this.onAwareness);
    void this.connect();
  }

  destroy(): void {
    this.stopped = true;
    this.o.doc.off("update", this.onDoc);
    this.o.awareness.off("update", this.onAwareness);
    if (this.flushTimer) clearTimeout(this.flushTimer);
    if (this.awTimer) clearTimeout(this.awTimer);
    this.ws?.close(1000);
    this.ws = null;
    this.setStatus("closed");
  }

  private setStatus(s: LiveStatus) {
    if (this.status === s) return;
    this.status = s;
    this.o.onStatus?.(s);
  }

  private async connect(): Promise<void> {
    if (this.stopped) return;
    this.setStatus(this.retry ? "offline" : "connecting");
    let ticket: string;
    try {
      ticket = await this.o.ticket();
    } catch (e) {
      if (e instanceof TicketRefused) {
        this.stopped = true;
        this.setStatus("removed");
        return;
      }
      this.later();
      return;
    }
    if (this.stopped) return;
    const ws = (this.o.socket ?? defaultSocket)((this.o.url ?? liveUrl)(this.o.noteId, ticket));
    this.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ t: "sync", since: this.lastSeq }));
    ws.onmessage = (ev) => {
      this.inbox = this.inbox.then(() => this.handle(String(ev.data))).catch(() => {});
    };
    ws.onclose = (ev) => {
      if (this.ws !== ws) return;
      this.ws = null;
      this.synced = false;
      this.compacting = false;
      if (ev.code === 4403 || ev.code === 4404) {
        this.stopped = true;
        this.setStatus("removed");
        return;
      }
      if (!this.stopped) {
        this.setStatus("offline");
        this.later();
      }
    };
  }

  private later() {
    const wait = this.retryMs[Math.min(this.retry, this.retryMs.length - 1)];
    this.retry += 1;
    setTimeout(() => void this.connect(), wait);
  }

  private send(m: object) {
    this.ws?.send(JSON.stringify(m));
  }

  private mark(seq: number) {
    if (seq <= this.lastSeq) return;
    this.got.add(seq);
    while (this.got.delete(this.lastSeq + 1)) this.lastSeq += 1;
  }

  private async applyRemote(kind: "update" | "snapshot", s: Sealed): Promise<void> {
    const u = await openBlob(this.o.nk, this.o.noteId, kind, s);
    // Was sich nicht öffnen lässt, ist nicht von uns — liegen lassen statt abbrechen.
    if (u) Y.applyUpdate(this.o.doc, u, REMOTE);
  }

  private async handle(data: string): Promise<void> {
    let m: Record<string, unknown>;
    try {
      m = JSON.parse(data);
    } catch {
      return;
    }
    switch (m.t) {
      case "hello":
        this.you = typeof m.you === "number" ? m.you : null;
        break;
      case "sync": {
        const snap = m.snapshot as (Sealed & { seq: number }) | null;
        if (snap) {
          await this.applyRemote("snapshot", snap);
          this.snapshotSeq = snap.seq;
          if (snap.seq > this.lastSeq) {
            this.lastSeq = snap.seq;
            for (const g of this.got) if (g <= this.lastSeq) this.got.delete(g);
          }
        }
        for (const u of (m.updates as (Sealed & { seq: number })[]) ?? []) {
          await this.applyRemote("update", u);
          this.mark(u.seq);
        }
        this.synced = true;
        this.retry = 0;
        this.setStatus("online");
        // Unbestätigtes noch einmal — doppelt angewendet schadet nichts.
        if (this.unacked.size) {
          this.pending.unshift(...this.unacked.values());
          this.unacked.clear();
        }
        this.flush();
        this.announce([...this.o.awareness.getStates().keys()].filter((c) => c === this.o.doc.clientID));
        this.maybeCompact();
        break;
      }
      case "update":
        await this.applyRemote("update", m as unknown as Sealed);
        this.mark(m.seq as number);
        this.maybeCompact();
        break;
      case "ack":
        this.unacked.delete(m.c as number);
        this.mark(m.seq as number);
        this.maybeCompact();
        break;
      case "full": {
        // Die Liste beim Server ist voll: erst ein Stand, dann diese Änderung noch einmal.
        const u = this.unacked.get(m.c as number);
        if (u) {
          this.unacked.delete(m.c as number);
          this.pending.unshift(u);
        }
        this.maybeCompact(true);
        break;
      }
      case "snapshot":
        this.compacting = false;
        if (m.ok) this.snapshotSeq = Math.max(this.snapshotSeq, m.upto as number);
        this.flush();
        break;
      case "awareness": {
        const u = await openBlob(this.o.nk, this.o.noteId, "awareness", m as unknown as Sealed);
        if (u) applyAwarenessUpdate(this.o.awareness, u, REMOTE);
        break;
      }
      case "presence":
        this.o.onPresence?.((m.online as number[]) ?? []);
        break;
    }
  }

  private onDoc = (update: Uint8Array, origin: unknown) => {
    if (origin === REMOTE) return;
    this.pending.push(update);
    if (this.flushTimer) return;
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      this.flush();
    }, this.flushMs);
  };

  private flush() {
    if (!this.ws || !this.synced || this.compacting || !this.pending.length) return;
    const merged = this.pending.length === 1 ? this.pending[0] : Y.mergeUpdates(this.pending);
    this.pending = [];
    const c = ++this.counter;
    this.unacked.set(c, merged);
    this.outbox = this.outbox.then(async () => {
      const s = await sealBlob(this.o.nk, this.o.noteId, "update", merged);
      this.send({ t: "update", ...s, c });
    }).catch(() => {});
  }

  private onAwareness = ({ added, updated, removed }: { added: number[]; updated: number[]; removed: number[] },
    origin: unknown) => {
    if (origin === REMOTE) return;
    for (const c of [...added, ...updated, ...removed]) this.awChanged.add(c);
    if (this.awTimer) return;
    this.awTimer = setTimeout(() => {
      this.awTimer = null;
      const clients = [...this.awChanged];
      this.awChanged.clear();
      this.announce(clients);
    }, 250);
  };

  private announce(clients: number[]) {
    if (!this.ws || !this.synced || !clients.length) return;
    const u = encodeAwarenessUpdate(this.o.awareness, clients);
    this.outbox = this.outbox.then(async () => {
      this.send({ t: "awareness", ...(await sealBlob(this.o.nk, this.o.noteId, "awareness", u)) });
    }).catch(() => {});
  }

  private maybeCompact(force = false) {
    if (!this.ws || !this.synced || this.compacting) return;
    if (!force && (this.pending.length || this.unacked.size)) return;
    if (!force && this.lastSeq - this.snapshotSeq < this.compactAfter) return;
    if (this.lastSeq <= this.snapshotSeq) return;
    this.compacting = true;
    const upto = this.lastSeq;
    const state = Y.encodeStateAsUpdate(this.o.doc);
    this.outbox = this.outbox.then(async () => {
      this.send({ t: "snapshot", upto, ...(await sealBlob(this.o.nk, this.o.noteId, "snapshot", state)) });
    }).catch(() => {});
  }
}
