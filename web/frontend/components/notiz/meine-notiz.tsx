"use client";

/* „Meine Notiz" an einem Tagesordnungspunkt oder Beschluss (Schalter
   `notizen`, Plan `docs/plan-notizen-verschluesselt.md`, Bild
   `docs/entwurf-sitzungsseite/bilder/punkt-desktop-2.png` rechts unten). */

import { Karte, Fuss, LINK, NotizSchloss, SperrenKnopf, type Offen } from "@/components/notiz/notiz-schloss";
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

function Editor({ o, targetKind, targetKey, wofuer, rows, documents }: {
  o: Offen; targetKind: TargetKind; targetKey: string; wofuer: string; rows: number; documents?: NoteDocument[];
}) {
  const v = useVerschluesselt<NoteDoc>(o.dk, o.keyVersion, targetKind, targetKey, "note", leer, istLeer);
  return (
    <Karte titel="Meine Notiz" id="meine-notiz" rechts={<SperrenKnopf owner={o.owner} />}>
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
      <Fuss />
    </Karte>
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
