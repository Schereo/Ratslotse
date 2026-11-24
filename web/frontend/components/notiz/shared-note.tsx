"use client";

/* One shared note, live (Schalter `notizen-teilen`, Tims Wunsch 23.11.2026):
   unwrap the note key with the own data key, keep the Yjs document in step
   (`lib/shared-note-live.ts`), show who is there, invite by link, manage
   members. Loaded on demand from „Meine Notiz" — Yjs and the live connection
   reach no page where nobody opens a shared note.

   Inviting and the member list open IN the card, above the text, not as a
   dialog (Tim 24.11.2026: „keine modale bitte"): the note stays visible and
   writable while the link is copied.

   Inviting works by address (a specific account; `lib/shared-note-invite.ts`)
   or by link (anyone who has it). Whoever has the note open hands the key
   over to an account that accepted — automatically, in the background. */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import * as Y from "yjs";
import { Awareness } from "y-protocols/awareness";
import { Check, Copy, Link2, Loader2, LogOut, Share2, Trash2, UserPlus, Users, X } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { NoteField } from "@/components/notiz/note-field";
import { api, ApiError } from "@/lib/api";
import type { NoteDocument } from "@/lib/doc-ref";
import { makeInvite, unwrapForMe, type NoteKey } from "@/lib/shared-note-crypto";
import { ensureIdentity, forgetInvite, grantPending, recordInvite } from "@/lib/shared-note-invite";
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
  keyVersion: number;
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

function Live({ note, nk, dk, keyVersion, meId, meName, rows, documents, seed, onChanged }: SharedNoteViewProps & { nk: NoteKey }) {
  // Dokument, Anwesenheit und Verbindung entstehen und vergehen ZUSAMMEN in
  // einem Effekt. Mit useMemo plus eigenem Aufräum-Effekt zerstörte der
  // doppelte Effektlauf im StrictMode die Anwesenheit gleich nach dem
  // Einhängen: Ihr eigener Zustand war danach `null`, und Name und Cursor
  // gingen still nie hinaus (gefunden 23.11.2026 an den WebSocket-Rahmen).
  const [sitzung, setSitzung] = useState<{ doc: Y.Doc; awareness: Awareness } | null>(null);
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [synced, setSynced] = useState(false);
  const [online, setOnline] = useState<number[]>([]);
  const [bereich, setBereich] = useState<"invite" | "members" | null>(null);
  const einladenRef = useRef<HTMLButtonElement>(null);
  const mitgliederRef = useRef<HTMLButtonElement>(null);
  const versucht = useRef(new Set<string>());
  const bereichId = useId();
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
      onPending: () => onChangedRef.current(),
    });
    setSitzung({ doc, awareness });
    setSynced(false);
    return () => {
      live.destroy();
      awareness.destroy();
      doc.destroy();
    };
  }, [note.id, nk]);

  // Das eigene Schlüsselpaar gleich anlegen: Dann kann einen jemand per
  // Adresse einladen, ohne dass man vorher etwas tun muss.
  useEffect(() => { ensureIdentity(dk, keyVersion).catch(() => {}); }, [dk, keyVersion]);

  // Wer eine Einladung per Adresse angenommen hat, bekommt den Schlüssel von
  // dem Mitglied, das die Notiz gerade offen hat — von selbst, aber nur mit
  // einer Kennung, die in der Notiz steht (lib/shared-note-invite.ts). Erst
  // nach dem Abgleich: Vorher kennt das Dokument die Kennungen noch nicht.
  const wartend = note.pending.map((p) => p.invite_id).join(",");
  useEffect(() => {
    if (!wartend || !synced || !sitzung) return;
    let gone = false;
    grantPending(note, nk, sitzung.doc, versucht.current).then((n) => { if (n && !gone) onChangedRef.current(); });
    return () => { gone = true; };
    // `note` ändert sich mit jedem Neuladen; entscheidend ist, wer wartet.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wartend, synced, sitzung, nk]);

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

  const schliessen = (fokus = false) => {
    if (fokus) (bereich === "invite" ? einladenRef : mitgliederRef).current?.focus();
    setBereich(null);
  };
  const umschalten = (b: "invite" | "members") => setBereich((alt) => (alt === b ? null : b));

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
          <button ref={einladenRef} type="button" className={cn(KNOPF, bereich === "invite" && "bg-accent")}
            aria-expanded={bereich === "invite"} aria-controls={bereichId} onClick={() => umschalten("invite")}>
            <UserPlus className="h-4 w-4" aria-hidden /> Einladen
          </button>
          <button ref={mitgliederRef} type="button" className={cn(KNOPF, bereich === "members" && "bg-accent")}
            aria-expanded={bereich === "members"} aria-controls={bereichId} aria-label="Mitglieder verwalten"
            onClick={() => umschalten("members")}>
            <Users className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>
      <Aufklapp offen={bereich !== null}>
        <div id={bereichId} className="pb-2">
          {bereich === "invite" && sitzung && (
            <Bereich titel="Einladen" onClose={schliessen}>
              <EinladenInhalt note={note} nk={nk} doc={sitzung.doc} meId={meId} onDone={() => schliessen(true)} />
            </Bereich>
          )}
          {bereich === "members" && (
            <Bereich titel="Mitglieder" onClose={schliessen}>
              <MitgliederInhalt note={note} meId={meId} online={online}
                onDone={() => { onChanged(); schliessen(true); }} />
            </Bereich>
          )}
        </div>
      </Aufklapp>
      {collab && (
        <NoteField key={collab.doc.guid} id={`geteilt-${note.id}`} label="Gemeinsame Notiz" value="" onChange={() => {}}
          rows={rows} disabled={status === "removed"} documents={documents} collab={collab}
          placeholder="Was wollt ihr euch zu diesem Punkt gemeinsam merken?" />
      )}
      <p className={cn("mt-1 min-h-5 text-meta", status === "offline" ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground")}
        aria-live="polite">{zustand}</p>
    </div>
  );
}

/** Ein Bereich in der Karte, über dem Text — kein Dialog, kein Abdunkler. */
function Bereich({ titel, children, onClose }: {
  titel: string; children: React.ReactNode; onClose: (fokus?: boolean) => void;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="rounded-xl border border-border bg-muted/40 p-3"
      onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(true); } }}>
      <div className="-mt-1.5 -mr-1.5 flex items-center justify-between gap-2">
        <h3 id={id} className="text-sm font-semibold text-foreground">{titel}</h3>
        <button type="button" aria-label="Schließen" onClick={() => onClose(true)}
          className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground desk:h-9 desk:w-9">
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className="mt-1">{children}</div>
    </section>
  );
}

const datum = (iso: string) => new Date(iso.endsWith("Z") ? iso : `${iso}Z`).toLocaleDateString("de-DE",
  { day: "numeric", month: "long" });

const PRIMAER = "inline-flex h-11 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60";
const FELD = "h-11 min-w-0 flex-1 rounded-lg border border-input bg-background px-3 text-sm";

function EinladenInhalt({ note, nk, doc, meId, onDone }: {
  note: SharedNote; nk: NoteKey; doc: Y.Doc; meId: number; onDone: () => void;
}) {
  const [adresse, setAdresse] = useState("");
  const [gesendet, setGesendet] = useState<string[]>([]);
  const [sendet, setSendet] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [link, setLink] = useState<{ url: string; invite: Invite } | null>(null);
  const [entsteht, setEntsteht] = useState(false);
  const [kopiert, setKopiert] = useState(false);

  // Ob es zu der Adresse ein Konto gibt, sagt der Server nicht (keine
  // Kontensuche) — der Haken heißt „abgeschickt“, nicht „angekommen“.
  const perAdresse = async (e: React.FormEvent) => {
    e.preventDefault();
    const a = adresse.trim();
    if (!a || sendet) return;
    setSendet(true);
    setFehler(null);
    const token = recordInvite(doc, meId);
    try {
      await api.post(`/shared-notes/${note.id}/address-invites`, { email: a, token });
      setGesendet((g) => [a, ...g.filter((x) => x !== a)]);
      setAdresse("");
    } catch (err) {
      forgetInvite(doc, token);
      setFehler(err instanceof Error ? err.message : "Das hat nicht geklappt.");
    } finally {
      setSendet(false);
    }
  };
  // Jedes Mal ein frischer Link: Ein älterer kann inzwischen weggefallen sein
  // (endet eine Mitgliedschaft, enden alle Link-Einladungen).
  const linkErstellen = async () => {
    setEntsteht(true);
    setFehler(null);
    try {
      const { secret, sealed, verifierHash } = await makeInvite(nk);
      const inv = await api.post<Invite>(`/shared-notes/${note.id}/invites`,
        { iv: sealed.iv, ciphertext: sealed.ct, verifier_hash: verifierHash, days: 7 });
      // Das Geheimnis steht im Anker (#…): Den schickt kein Browser an einen Server.
      setLink({ url: `${window.location.origin}/notiz-einladung?i=${encodeURIComponent(inv.id)}#${secret}`, invite: inv });
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Das hat nicht geklappt.");
    } finally {
      setEntsteht(false);
    }
  };
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
    setLink(null);
    onDone();
  };
  const teilen = typeof navigator !== "undefined" && "share" in navigator;

  return (
    <div className="space-y-3">
      <form onSubmit={perAdresse} className="flex gap-2">
        <label className="contents">
          <span className="sr-only">E-Mail-Adresse</span>
          <input type="email" inputMode="email" autoComplete="off" value={adresse} placeholder="E-Mail-Adresse"
            onChange={(e) => setAdresse(e.target.value)} className={FELD} />
        </label>
        <button type="submit" disabled={sendet || !adresse.trim()} className={PRIMAER}>
          {sendet && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />} Einladen
        </button>
      </form>
      {gesendet.length > 0 && (
        <ul className="space-y-1" role="status" aria-label="Eingeladen">
          {gesendet.map((a) => (
            <li key={a} className="flex min-w-0 items-center gap-1.5 text-meta text-muted-foreground">
              <Check className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
              <span className="truncate">{a}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center gap-3 text-meta text-muted-foreground" aria-hidden>
        <span className="h-px flex-1 bg-border" /> oder <span className="h-px flex-1 bg-border" />
      </div>

      {!link ? (
        <button type="button" onClick={() => void linkErstellen()} disabled={entsteht}
          className={cn(KNOPF, "w-full justify-center border border-border bg-card")}>
          {entsteht ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Link2 className="h-4 w-4" aria-hidden />}
          Link erstellen
        </button>
      ) : (
        <div className="space-y-1.5">
          <div className="flex gap-2">
            <label className="contents">
              <span className="sr-only">Einladungslink</span>
              <input readOnly value={link.url} onFocus={(e) => e.currentTarget.select()} className={cn(FELD, "font-mono text-xs")} />
            </label>
            <button type="button" onClick={kopieren} className={PRIMAER} aria-label={kopiert ? "Kopiert" : "Link kopieren"}>
              {kopiert ? <Check className="h-4 w-4" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
              <span className="hidden sm:inline">{kopiert ? "Kopiert" : "Kopieren"}</span>
            </button>
            {teilen && (
              <button type="button" aria-label="Teilen" className={cn(KNOPF, "border border-border bg-card")}
                onClick={() => { void navigator.share({ title: "Gemeinsame Notiz", url: link.url }).catch(() => {}); }}>
                <Share2 className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>
          <p className="text-meta text-muted-foreground">
            Gilt bis {datum(link.invite.expires_at)} für alle, die den Link haben ·{" "}
            <button type="button" className="underline underline-offset-2 hover:text-foreground" onClick={zurueckziehen}>
              zurückziehen
            </button>
          </p>
        </div>
      )}
      {fehler && <p className="text-sm text-destructive" role="alert">{fehler}</p>}
    </div>
  );
}

function MitgliederInhalt({ note, meId, online, onDone }: {
  note: SharedNote; meId: number; online: number[]; onDone: () => void;
}) {
  const leite = note.role === "owner";
  const [loeschen, setLoeschen] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const tun = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      onDone();
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Das hat nicht geklappt.");
    }
  };
  return (
    <>
      <ul className="divide-y divide-border">
        {note.members.map((m) => (
          <li key={m.user_id} className="flex min-h-11 items-center gap-2 py-1 text-sm">
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
        <div className="mt-1 border-t border-border pt-2">
          {!loeschen ? (
            <button type="button" className={cn(KNOPF, "text-destructive")} onClick={() => setLoeschen(true)}>
              <Trash2 className="h-4 w-4" aria-hidden /> Für alle löschen
            </button>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-foreground">Endgültig für alle löschen?</span>
              <button type="button" onClick={() => tun(() => api.del(`/shared-notes/${note.id}`))}
                className="inline-flex h-11 items-center rounded-lg bg-destructive px-4 text-sm font-medium text-destructive-foreground hover:bg-destructive/90">
                Löschen
              </button>
              <button type="button" className={KNOPF} onClick={() => setLoeschen(false)}>Abbrechen</button>
            </div>
          )}
        </div>
      )}
      {fehler && <p className="mt-2 text-sm text-destructive" role="alert">{fehler}</p>}
    </>
  );
}
