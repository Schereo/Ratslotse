"use client";

/* „Meine Notiz" an einem Tagesordnungspunkt oder Beschluss (Schalter
   `notizen`, Plan `docs/plan-notizen-verschluesselt.md`, Bild
   `docs/entwurf-sitzungsseite/bilder/punkt-desktop-2.png` rechts unten).

   Mit dem Schalter `notizen-teilen` steht über dem Feld ein Umschalter:
   die eigene Notiz („Nur ich“), die gemeinsamen Notizen zu diesem Ziel und
   „Gemeinsam“ zum Anlegen. Die gemeinsame Ansicht (`shared-note.tsx`, Yjs,
   Live-Verbindung) lädt erst, wenn jemand sie öffnet. */

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Karte, Fuss, LINK, NotizSchloss, SperrenKnopf, type Offen } from "@/components/notiz/notiz-schloss";
import type { SharedNote } from "@/components/notiz/shared-note";
import { Segmented } from "@/components/ui/segmented";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFeature } from "@/lib/features";
import { newNoteKey, wrapForMe } from "@/lib/shared-note-crypto";
import type { ApiAntwort } from "@/lib/vertrag";
import { NoteField } from "@/components/notiz/note-field";
import { NoteView } from "@/components/notiz/note-view";
import type { NoteDocument } from "@/lib/doc-ref";
import { statusText, useVerschluesselt } from "@/components/notiz/use-verschluesselt";
import type { NoteDoc, TargetKind } from "@/lib/notizen";

const leer: NoteDoc = { text: "" };
const istLeer = (d: NoteDoc) => !d.text.trim();

/** `rows`: Höhe des Felds — in der Seitenspalte knapp, als eigener Reiter
 *  der Punkt-Seite (neben dem Chat) mit Platz zum Schreiben. */
export function MeineNotiz({ targetKind, targetKey, wofuer = "Punkt", rows = 5, documents }: {
  targetKind: TargetKind; targetKey: string; wofuer?: "Punkt" | "Beschluss"; rows?: number;
  /** Unterlagen, auf deren Seiten die Notiz verweisen kann (`doc-ref.tsx`). */
  documents?: NoteDocument[];
}) {
  return (
    <NotizSchloss titel="Meine Notiz" id="meine-notiz"
      angebot={`Notiere dir, was du zu diesem ${wofuer} wissen oder nachfragen willst. Nur du kannst es lesen.`}>
      {(o) => <Editor key={`${targetKind}|${targetKey}`} o={o} targetKind={targetKind} targetKey={targetKey} wofuer={wofuer}
        rows={rows} documents={documents} />}
    </NotizSchloss>
  );
}

const SharedNoteView = dynamic(() => import("@/components/notiz/shared-note"), {
  ssr: false,
  loading: () => <p className="min-h-11 text-sm text-muted-foreground" role="status">Öffnet …</p>,
});

/** Nach dem Beitreten über eine Einladung: diese Notiz gleich öffnen. */
export const OFFEN_KEY = "ratslotse:geteilte-notiz-offen";

function Editor({ o, targetKind, targetKey, wofuer, rows, documents }: {
  o: Offen; targetKind: TargetKind; targetKey: string; wofuer: string; rows: number; documents?: NoteDocument[];
}) {
  const v = useVerschluesselt<NoteDoc>(o.dk, o.keyVersion, targetKind, targetKey, "note", leer, istLeer);
  const teilen = useFeature("notizen-teilen");
  const { user } = useAuth();
  const [geteilt, setGeteilt] = useState<SharedNote[] | null>(null);
  const ansichtKey = `ratslotse:notiz-ansicht:${targetKind}|${targetKey}`;
  // Gleich beim Anlegen: nach dem Beitreten die neue Notiz, sonst die zuletzt
  // gewählte Ansicht dieses Punkts (auch nach dem Neuladen). Geprüft wird,
  // sobald die Liste da ist.
  const [ansicht, setAnsicht] = useState<string>(() => {
    try { return sessionStorage.getItem(OFFEN_KEY) || sessionStorage.getItem(ansichtKey) || "private"; } catch { return "private"; }
  });
  const [seed, setSeed] = useState<{ id: string; text: string } | null>(null);
  useEffect(() => {
    // Erst merken, wenn die Liste da ist — sonst überschriebe der erste
    // Stand („privat“) die gemerkte Notiz, bevor sie geprüft ist.
    if (geteilt === null || ansicht === "new") return;
    try { sessionStorage.setItem(ansichtKey, ansicht); } catch { /* privat */ }
  }, [ansicht, ansichtKey, geteilt]);

  const laden = useCallback(async () => {
    if (!teilen) return;
    try {
      const r = await api.get<ApiAntwort<"/shared-notes">>(
        `/shared-notes?target_kind=${targetKind}&target_key=${encodeURIComponent(targetKey)}`);
      setGeteilt(r.notes);
      try { sessionStorage.removeItem(OFFEN_KEY); } catch { /* privat */ }
      setAnsicht((a) => (a === "private" || a === "new" || r.notes.some((n) => n.id === a) ? a : "private"));
    } catch {
      // Ohne Liste bleibt die eigene Notiz.
      setGeteilt([]);
      setAnsicht("private");
    }
  }, [teilen, targetKind, targetKey]);
  useEffect(() => { void laden(); }, [laden]);

  const wechseln = (neu: string) => {
    if (ansicht === "private") void v.jetztSpeichern();
    setAnsicht(neu);
  };
  const liste = geteilt ?? [];
  const aktiv = liste.find((n) => n.id === ansicht) ?? null;
  // Eine gemerkte gemeinsame Notiz, solange die Liste noch lädt: nicht kurz die eigene zeigen.
  const wartet = teilen && geteilt === null && ansicht !== "private" && ansicht !== "new";
  const name = (n: SharedNote) => {
    const andere = n.members.filter((m) => m.user_id !== o.owner).map((m) => m.display_name);
    if (!andere.length) return "Gemeinsam";
    return `Mit ${andere.slice(0, 2).join(", ")}${andere.length > 2 ? ` +${andere.length - 2}` : ""}`;
  };

  return (
    <Karte titel="Meine Notiz" id="meine-notiz" rechts={<SperrenKnopf owner={o.owner} />}>
      {teilen && (
        <Segmented className="mb-3 flex-wrap" value={ansicht} onChange={wechseln} options={[
          { value: "private", label: "Nur ich" },
          ...liste.map((n) => ({ value: n.id, label: name(n) })),
          { value: "new", label: "+ Gemeinsam" },
        ]} />
      )}
      {ansicht === "new" ? (
        <Anlegen eigenerText={v.doc.text} onAnlegen={async (mitText) => {
          const nk = await newNoteKey();
          const w = await wrapForMe(o.dk, nk);
          const n = await api.post<ApiAntwort<"/shared-notes", "post">>("/shared-notes", { target_kind: targetKind, target_key: targetKey,
            key_iv: w.iv, key_ct: w.ct, key_version: o.keyVersion });
          if (mitText && v.doc.text.trim()) setSeed({ id: n.id, text: v.doc.text });
          setGeteilt((g) => [n, ...(g ?? [])]);
          setAnsicht(n.id);
        }} />
      ) : wartet ? (
        <p className="min-h-11 text-sm text-muted-foreground" role="status">Öffnet …</p>
      ) : aktiv ? (
        <SharedNoteView note={aktiv} dk={o.dk} meId={o.owner} meName={user?.display_name || "Ich"} rows={rows}
          documents={documents} seed={seed?.id === aktiv.id ? seed.text : undefined} onChanged={() => void laden()} />
      ) : (
        <PrivatesFeld v={v} wofuer={wofuer} rows={rows} documents={documents} />
      )}
      <Fuss />
    </Karte>
  );
}

function Anlegen({ eigenerText, onAnlegen }: { eigenerText: string; onAnlegen: (mitText: boolean) => Promise<void> }) {
  const [mitText, setMitText] = useState(Boolean(eigenerText.trim()));
  const [laeuft, setLaeuft] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  return (
    <div className="rounded-xl border border-dashed border-border p-4">
      <p className="text-sm text-foreground">
        Eine gemeinsame Notiz schreibt ihr zu mehreren, alle sehen Änderungen sofort. Eingeladen wird per Link.
      </p>
      {eigenerText.trim() && (
        <label className="mt-3 flex min-h-11 items-center gap-2 text-sm text-foreground">
          <input type="checkbox" checked={mitText} onChange={(e) => setMitText(e.target.checked)} className="h-4 w-4 accent-primary" />
          Mit meiner Notiz beginnen
        </label>
      )}
      <button type="button" disabled={laeuft} onClick={async () => {
        setLaeuft(true);
        setFehler(null);
        try { await onAnlegen(mitText); } catch (e) { setFehler(e instanceof Error ? e.message : "Das hat nicht geklappt."); }
        setLaeuft(false);
      }} className="mt-3 inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60">
        {laeuft ? "Legt an …" : "Gemeinsame Notiz anlegen"}
      </button>
      {fehler && <p className="mt-2 text-sm text-destructive" role="alert">{fehler}</p>}
    </div>
  );
}

function PrivatesFeld({ v, wofuer, rows, documents }: {
  v: ReturnType<typeof useVerschluesselt<NoteDoc>>; wofuer: string; rows: number; documents?: NoteDocument[];
}) {
  return (
    <>
      {v.unlesbar && (
        <p className="mb-2 text-hinweis text-amber-700 dark:text-amber-300">
          Diese Notiz lässt sich mit dem jetzigen Schlüssel nicht lesen. Was du schreibst, ersetzt sie.
        </p>
      )}
      <NoteField id="notiz-text" label={`Meine Notiz zu diesem ${wofuer}`} value={v.doc.text}
        disabled={v.stand === "lädt"} rows={rows} documents={documents}
        onChange={(text) => v.setDoc({ text })} onBlur={() => { void v.jetztSpeichern(); }}
        placeholder={`Was willst du dir zu diesem ${wofuer} merken?`} />
      {v.stand === "konflikt" && (
        <Konflikt text={v.konflikt?.doc?.text ?? ""} onUebernehmen={v.uebernehmen} onBehalten={v.behalten} was="Notiz" />
      )}
      <p className="mt-1 min-h-5 text-meta text-muted-foreground" aria-live="polite">{statusText(v.stand, v.version, v.um)}</p>
    </>
  );
}

export function Konflikt({ text, onUebernehmen, onBehalten, was }: {
  text: string; onUebernehmen: () => void; onBehalten: () => void; was: string;
}) {
  return (
    <div className="mt-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
      <p>Auf einem anderen Gerät wurde diese {was} inzwischen geändert.</p>
      {text.trim() ? <NoteView text={text} className="mt-1 text-sm" /> : <p className="mt-1 italic">(leer)</p>}
      <div className="mt-2 flex flex-wrap gap-3">
        <button type="button" className={LINK} onClick={onUebernehmen}>Diese Fassung übernehmen</button>
        <button type="button" className={LINK} onClick={onBehalten}>Meine behalten</button>
      </div>
    </div>
  );
}
