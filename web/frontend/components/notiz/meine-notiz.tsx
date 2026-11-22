"use client";

/* „Meine Notiz" an einem Tagesordnungspunkt oder Beschluss (Schalter
   `notizen`, Plan `docs/plan-notizen-verschluesselt.md`, Bild
   `docs/entwurf-sitzungsseite/bilder/punkt-desktop-2.png` rechts unten). */

import { Karte, Fuss, LINK, NotizSchloss, SperrenKnopf, type Offen } from "@/components/notiz/notiz-schloss";
import { statusText, useVerschluesselt } from "@/components/notiz/use-verschluesselt";
import type { NoteDoc, TargetKind } from "@/lib/notizen";

const leer: NoteDoc = { text: "" };
const istLeer = (d: NoteDoc) => !d.text.trim();

export function MeineNotiz({ targetKind, targetKey, wofuer = "Punkt" }: {
  targetKind: TargetKind; targetKey: string; wofuer?: "Punkt" | "Beschluss";
}) {
  return (
    <NotizSchloss titel="Meine Notiz" id="meine-notiz"
      angebot={`Notiere dir, was du zu diesem ${wofuer} wissen oder nachfragen willst. Nur du kannst es lesen.`}>
      {(o) => <Editor key={`${targetKind}|${targetKey}`} o={o} targetKind={targetKind} targetKey={targetKey} wofuer={wofuer} />}
    </NotizSchloss>
  );
}

function Editor({ o, targetKind, targetKey, wofuer }: { o: Offen; targetKind: TargetKind; targetKey: string; wofuer: string }) {
  const v = useVerschluesselt<NoteDoc>(o.dk, o.keyVersion, targetKind, targetKey, "note", leer, istLeer);
  return (
    <Karte titel="Meine Notiz" id="meine-notiz" rechts={<SperrenKnopf owner={o.owner} />}>
      {v.unlesbar && (
        <p className="mb-2 text-hinweis text-amber-700 dark:text-amber-300">
          Diese Notiz lässt sich mit dem jetzigen Schlüssel nicht lesen. Was du schreibst, ersetzt sie.
        </p>
      )}
      <label htmlFor="notiz-text" className="sr-only">Meine Notiz zu diesem {wofuer}</label>
      <textarea id="notiz-text" value={v.doc.text} disabled={v.stand === "lädt"} rows={5} maxLength={8000}
        onChange={(e) => v.setDoc({ text: e.target.value })} onBlur={() => { void v.jetztSpeichern(); }}
        placeholder={`Was willst du dir zu diesem ${wofuer} merken?`}
        className="w-full resize-y rounded-xl border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
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
      <p className="mt-1 whitespace-pre-wrap italic">{text || "(leer)"}</p>
      <div className="mt-2 flex flex-wrap gap-3">
        <button type="button" className={LINK} onClick={onUebernehmen}>Diese Fassung übernehmen</button>
        <button type="button" className={LINK} onClick={onBehalten}>Meine behalten</button>
      </div>
    </div>
  );
}
