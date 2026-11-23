"use client";

/* One shared note, live (Schalter `notizen-teilen`, Tims Wunsch 23.11.2026):
   unwrap the note key with the own data key, keep the Yjs document in step
   (`lib/shared-note-live.ts`), show who is there, invite by link, manage
   members. Loaded on demand from „Meine Notiz" — Yjs and the live connection
   reach no page where nobody opens a shared note. */

import { useEffect, useMemo, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as Y from "yjs";
import { Awareness } from "y-protocols/awareness";
import { Check, Copy, LogOut, Share2, Trash2, UserPlus, Users, X } from "lucide-react";
import { NoteField } from "@/components/notiz/note-field";
import { api, ApiError } from "@/lib/api";
import type { NoteDocument } from "@/lib/doc-ref";
import { makeInvite, unwrapForMe, type NoteKey } from "@/lib/shared-note-crypto";
import { SharedNoteLive, TicketRefused, type LiveStatus } from "@/lib/shared-note-live";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";

export type SharedNote = ApiAntwort<"/shared-notes">["notes"][number];
type Ticket = ApiAntwort<"/shared-notes/{note_id}/ticket", "post">;
type Invite = ApiAntwort<"/shared-notes/{note_id}/invites", "post">;

const FARBEN = ["#0e7490", "#b45309", "#7c3aed", "#be123c", "#15803d", "#1d4ed8", "#a21caf", "#4d7c0f"];
/** Eine feste Farbe je Konto — Cursor und Punkt in der Mitgliederliste passen zusammen. */
export const farbe = (userId: number) => FARBEN[Math.abs(userId) % FARBEN.length];

const KNOPF = "inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-foreground hover:bg-accent desk:min-h-9";

export interface SharedNoteViewProps {
  note: SharedNote;
  dk: CryptoKey;
  meId: number;
  meName: string;
  rows: number;
  documents?: NoteDocument[];
  /** Markdown, mit dem eine eben angelegte Notiz beginnt. */
  seed?: string;
  /** Die Liste neu holen (Mitglied entfernt, verlassen, gelöscht). */
  onChanged: () => void;
}

export default function SharedNoteView(props: SharedNoteViewProps) {
  const { note, dk } = props;
  const [nk, setNk] = useState<NoteKey | null | undefined>(undefined);
  useEffect(() => {
    let gone = false;
    unwrapForMe(dk, { iv: note.key_iv, ct: note.key_ct }).then((k) => { if (!gone) setNk(k); });
    return () => { gone = true; };
  }, [dk, note.key_iv, note.key_ct]);
  if (nk === undefined) return <p className="min-h-11 text-sm text-muted-foreground" role="status">Öffnet …</p>;
  if (nk === null) {
    return (
      <p className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
        Diese gemeinsame Notiz lässt sich mit deinem jetzigen Schlüssel nicht öffnen. Lass dich noch einmal einladen.
      </p>
    );
  }
  return <Live key={note.id} {...props} nk={nk} />;
}

function Live({ note, nk, meId, meName, rows, documents, seed, onChanged }: SharedNoteViewProps & { nk: NoteKey }) {
  // Dokument, Anwesenheit und Verbindung entstehen und vergehen ZUSAMMEN in
  // einem Effekt. Mit useMemo plus eigenem Aufräum-Effekt zerstörte der
  // doppelte Effektlauf im StrictMode die Anwesenheit gleich nach dem
  // Einhängen: Ihr eigener Zustand war danach `null`, und Name und Cursor
  // gingen still nie hinaus (gefunden 23.11.2026 an den WebSocket-Rahmen).
  const [sitzung, setSitzung] = useState<{ doc: Y.Doc; awareness: Awareness } | null>(null);
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [synced, setSynced] = useState(false);
  const [online, setOnline] = useState<number[]>([]);
  const [dialog, setDialog] = useState<"invite" | "members" | null>(null);
  const onChangedRef = useRef(onChanged);
  useEffect(() => { onChangedRef.current = onChanged; });

  useEffect(() => {
    const doc = new Y.Doc();
    const awareness = new Awareness(doc);
    const live = new SharedNoteLive({
      noteId: note.id, nk, doc, awareness,
      ticket: async () => {
        try {
          return (await api.post<Ticket>(`/shared-notes/${note.id}/ticket`)).ticket;
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) throw new TicketRefused();
          throw e;
        }
      },
      onStatus: (s) => {
        setStatus(s);
        if (s === "online") setSynced(true);
        if (s === "removed") onChangedRef.current();
      },
      onPresence: setOnline,
    });
    setSitzung({ doc, awareness });
    setSynced(false);
    return () => {
      live.destroy();
      awareness.destroy();
      doc.destroy();
    };
  }, [note.id, nk]);

  // Taucht jemand auf, den die Liste noch nicht kennt (eben beigetreten),
  // die Liste neu holen — sonst stünde neben „Du“ niemand.
  const unbekannt = online.filter((id) => !note.members.some((m) => m.user_id === id)).join(",");
  useEffect(() => { if (unbekannt) onChangedRef.current(); }, [unbekannt]);

  const user = useMemo(() => ({ name: meName, color: farbe(meId) }), [meName, meId]);
  const collab = useMemo(() => (sitzung ? { ...sitzung, user, synced, seed } : null), [sitzung, user, synced, seed]);
  const andere = online.filter((id) => id !== meId).length;
  const zustand = status === "online"
    ? (andere ? `Live · ${andere === 1 ? "1 weitere Person" : `${andere} weitere Personen`} gerade dabei` : "Live")
    : status === "offline" ? "Offline — deine Änderungen gehen hinaus, sobald die Verbindung zurück ist."
      : status === "removed" ? "Du bist nicht mehr Mitglied dieser Notiz." : "Verbindet …";

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <ul className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5" aria-label="Mitglieder">
          {note.members.map((m) => (
            <li key={m.user_id} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2 py-0.5 text-xs text-foreground">
              <span aria-hidden className={cn("h-2 w-2 rounded-full", online.includes(m.user_id) ? "" : "opacity-30")}
                style={{ backgroundColor: farbe(m.user_id) }} />
              {m.user_id === meId ? "Du" : m.display_name}
              <span className="sr-only">{online.includes(m.user_id) ? " (gerade dabei)" : ""}</span>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-1">
          <button type="button" className={KNOPF} onClick={() => setDialog("invite")}>
            <UserPlus className="h-4 w-4" aria-hidden /> Einladen
          </button>
          <button type="button" className={KNOPF} onClick={() => setDialog("members")} aria-label="Mitglieder verwalten">
            <Users className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>
      {collab && (
        <NoteField key={collab.doc.guid} id={`geteilt-${note.id}`} label="Gemeinsame Notiz" value="" onChange={() => {}}
          rows={rows} disabled={status === "removed"} documents={documents} collab={collab}
          placeholder="Was wollt ihr euch zu diesem Punkt gemeinsam merken?" />
      )}
      <p className={cn("mt-1 min-h-5 text-meta", status === "offline" ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground")}
        aria-live="polite">{zustand}</p>
      {dialog === "invite" && <EinladenDialog note={note} nk={nk} onClose={() => setDialog(null)} />}
      {dialog === "members" && (
        <MitgliederDialog note={note} meId={meId} online={online} onClose={() => setDialog(null)} onChanged={onChanged} />
      )}
    </div>
  );
}

function NotizDialog({ titel, children, onClose }: { titel: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <DialogPrimitive.Root open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="scrim fixed inset-0" style={{ zIndex: "var(--level-dialog)" }} />
        <DialogPrimitive.Content style={{ zIndex: "var(--level-dialog)" }}
          onKeyDown={(e) => { if (e.key === "Escape") e.stopPropagation(); }}
          className="fixed left-1/2 top-1/2 max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-border bg-card p-4 shadow-lg">
          <div className="flex items-center justify-between gap-2">
            <DialogPrimitive.Title className="text-base font-semibold text-foreground">{titel}</DialogPrimitive.Title>
            <DialogPrimitive.Close aria-label="Schließen"
              className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground">
              <X className="h-4 w-4" aria-hidden />
            </DialogPrimitive.Close>
          </div>
          <DialogPrimitive.Description className="sr-only">{titel}</DialogPrimitive.Description>
          <div className="mt-2">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

const datum = (iso: string) => new Date(iso.endsWith("Z") ? iso : `${iso}Z`).toLocaleDateString("de-DE",
  { day: "numeric", month: "long" });

function EinladenDialog({ note, nk, onClose }: { note: SharedNote; nk: NoteKey; onClose: () => void }) {
  const [link, setLink] = useState<{ url: string; invite: Invite } | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [kopiert, setKopiert] = useState(false);
  useEffect(() => {
    let gone = false;
    (async () => {
      try {
        const { secret, sealed, verifierHash } = await makeInvite(nk);
        const inv = await api.post<Invite>(`/shared-notes/${note.id}/invites`,
          { iv: sealed.iv, ciphertext: sealed.ct, verifier_hash: verifierHash, days: 7 });
        // Das Geheimnis steht im Anker (#…): Den schickt kein Browser an einen Server.
        const url = `${window.location.origin}/notiz-einladung?i=${encodeURIComponent(inv.id)}#${secret}`;
        if (!gone) setLink({ url, invite: inv });
      } catch (e) {
        if (!gone) setFehler(e instanceof Error ? e.message : "Das hat nicht geklappt.");
      }
    })();
    return () => { gone = true; };
  }, [note.id, nk]);

  const kopieren = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setKopiert(true);
      setTimeout(() => setKopiert(false), 2000);
    } catch { /* Ohne Zwischenablage bleibt das Feld zum Markieren. */ }
  };
  const zurueckziehen = async () => {
    if (!link) return;
    await api.del(`/shared-notes/${note.id}/invites/${link.invite.id}`);
    onClose();
  };

  return (
    <NotizDialog titel="Zum Mitschreiben einladen" onClose={onClose}>
      {fehler && <p className="text-sm text-destructive" role="alert">{fehler}</p>}
      {!link && !fehler && <p className="min-h-11 text-sm text-muted-foreground" role="status">Link entsteht …</p>}
      {link && (
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            Wer diesen Link hat, kann bis zum {datum(link.invite.expires_at)} beitreten und mitschreiben. Schick ihn nur
            an Leute, die dabei sein sollen.
          </p>
          <label className="block">
            <span className="sr-only">Einladungslink</span>
            <input readOnly value={link.url} onFocus={(e) => e.currentTarget.select()}
              className="h-11 w-full rounded-lg border border-input bg-background px-2 font-mono text-xs" />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={kopieren}
              className="inline-flex h-11 items-center gap-1.5 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              {kopiert ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
              {kopiert ? "Kopiert" : "Link kopieren"}
            </button>
            {typeof navigator !== "undefined" && "share" in navigator && (
              <button type="button" className={cn(KNOPF, "border border-border")}
                onClick={() => { void navigator.share({ title: "Gemeinsame Notiz", url: link.url }).catch(() => {}); }}>
                <Share2 className="h-4 w-4" aria-hidden /> Teilen
              </button>
            )}
            <button type="button" className={cn(KNOPF, "ml-auto text-muted-foreground")} onClick={zurueckziehen}>
              Link zurückziehen
            </button>
          </div>
        </div>
      )}
    </NotizDialog>
  );
}

function MitgliederDialog({ note, meId, online, onClose, onChanged }: {
  note: SharedNote; meId: number; online: number[]; onClose: () => void; onChanged: () => void;
}) {
  const leite = note.role === "owner";
  const [loeschen, setLoeschen] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const tun = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      onChanged();
      onClose();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Das hat nicht geklappt.");
    }
  };
  return (
    <NotizDialog titel="Mitglieder" onClose={onClose}>
      <ul className="divide-y divide-border">
        {note.members.map((m) => (
          <li key={m.user_id} className="flex min-h-11 items-center gap-2 py-1.5 text-sm">
            <span aria-hidden className={cn("h-2.5 w-2.5 rounded-full", online.includes(m.user_id) ? "" : "opacity-30")}
              style={{ backgroundColor: farbe(m.user_id) }} />
            <span className="min-w-0 flex-1 truncate text-foreground">
              {m.user_id === meId ? `${m.display_name} (du)` : m.display_name}
              {m.role === "owner" && <span className="ml-1.5 text-xs text-muted-foreground">leitet</span>}
            </span>
            {m.user_id === meId ? (
              <button type="button" className={KNOPF}
                onClick={() => tun(() => api.del(`/shared-notes/${note.id}/members/${meId}`))}>
                <LogOut className="h-4 w-4" aria-hidden /> Verlassen
              </button>
            ) : leite ? (
              <button type="button" className={KNOPF} aria-label={`${m.display_name} entfernen`}
                onClick={() => tun(() => api.del(`/shared-notes/${note.id}/members/${m.user_id}`))}>
                Entfernen
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {leite && (
        <div className="mt-3 border-t border-border pt-3">
          {!loeschen ? (
            <button type="button" className={cn(KNOPF, "text-destructive")} onClick={() => setLoeschen(true)}>
              <Trash2 className="h-4 w-4" aria-hidden /> Für alle löschen
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-foreground">Die Notiz verschwindet für alle Mitglieder. Das lässt sich nicht rückgängig machen.</p>
              <div className="flex gap-2">
                <button type="button" onClick={() => tun(() => api.del(`/shared-notes/${note.id}`))}
                  className="inline-flex h-11 items-center rounded-lg bg-destructive px-4 text-sm font-medium text-destructive-foreground hover:bg-destructive/90">
                  Endgültig löschen
                </button>
                <button type="button" className={KNOPF} onClick={() => setLoeschen(false)}>Abbrechen</button>
              </div>
            </div>
          )}
        </div>
      )}
      {fehler && <p className="mt-2 text-sm text-destructive" role="alert">{fehler}</p>}
    </NotizDialog>
  );
}
