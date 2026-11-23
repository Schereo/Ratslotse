"use client";

/* Laden und Zwischenspeichern eines verschlüsselten Dokuments (Notiz oder
   Mitschrieb): 1,5 s Ruhe nach dem Tippen, dann verschlüsselt hinaus; ein
   leeres Dokument wird gelöscht; ein Stand von einem anderen Gerät führt zur
   Frage statt zum stillen Überschreiben.

   Gespeichert wird immer nur EINMAL zur selben Zeit, und die Version kommt
   aus dem Moment des Absendens (`versionRef`), nicht aus dem des Tippens.
   Bis 23.11.2026 nahm der Zeitgeber die Version mit, die beim Tippen galt:
   Lief da noch ein Speichern, schickte das nächste die Version von davor,
   bekam 409 — und Tim las mitten im Schreiben „Auf einem anderen Gerät
   wurde diese Notiz inzwischen geändert“, darunter den eigenen Text. */

import { useCallback, useEffect, useRef, useState } from "react";
import { deleteDoc, loadDoc, saveDoc, type Loaded, type NoteArt, type TargetKind } from "@/lib/notizen";

export type Stand = "lädt" | "bereit" | "speichert" | "gespeichert" | "fehler" | "konflikt";

export function useVerschluesselt<T>(dk: CryptoKey, keyVersion: number, kind: TargetKind, key: string, art: NoteArt,
  leer: T, istLeer: (d: T) => boolean) {
  const [doc, setDoc] = useState<T>(leer);
  const [stand, setStand] = useState<Stand>("lädt");
  const [version, setVersion] = useState(0);
  const [um, setUm] = useState<string | null>(null);
  const [konflikt, setKonflikt] = useState<Loaded<T> | null>(null);
  const [unlesbar, setUnlesbar] = useState(false);
  const zuletzt = useRef<string>(JSON.stringify(leer));
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const geladen = useRef(false);
  /** Die Version, auf der das NÄCHSTE Speichern aufsetzt. */
  const versionRef = useRef(0);
  /** Das laufende Speichern — das nächste wartet darauf. */
  const kette = useRef<Promise<void>>(Promise.resolve());
  /** Was dieses Feld schon abgeschickt hat: Liegt genau das beim Server,
   *  ist es kein fremder Stand (etwa wenn eine Antwort verloren ging). */
  const eigene = useRef(new Set<string>());

  const setzeVersion = (v: number) => { versionRef.current = v; setVersion(v); };

  useEffect(() => {
    let weg = false;
    geladen.current = false;
    setStand("lädt");
    loadDoc<T>(dk, kind, key, art).then((n) => {
      if (weg) return;
      const d = n?.doc ?? leer;
      setDoc(d);
      zuletzt.current = JSON.stringify(d);
      eigene.current = new Set();
      setzeVersion(n?.version ?? 0);
      setUm(n?.updatedAt ?? null);
      setUnlesbar(n != null && !n.lesbar);
      setStand("bereit");
      geladen.current = true;
    }).catch(() => { if (!weg) setStand("fehler"); });
    return () => { weg = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dk, kind, key, art]);

  /** `basis`: nur beim „Meine behalten“ vorgegeben, sonst der Stand von jetzt. */
  const einmal = useCallback(async (wert: T, erzwingen: boolean, basis?: number) => {
    const roh = JSON.stringify(wert);
    if (!erzwingen && roh === zuletzt.current) return;
    const b = basis ?? versionRef.current;
    setStand("speichert");
    try {
      if (istLeer(wert)) {
        if (b > 0) await deleteDoc(kind, key, art);
        zuletzt.current = roh;
        setzeVersion(0);
        setUm(null);
        setStand("gespeichert");
        return;
      }
      eigene.current.add(roh);
      let r = await saveDoc<T>(dk, keyVersion, kind, key, art, wert, b);
      if (!r.ok && r.conflict?.doc != null && eigene.current.has(JSON.stringify(r.conflict.doc))) {
        // Der Stand beim Server ist unser eigener: darauf aufsetzen, nicht fragen.
        r = await saveDoc<T>(dk, keyVersion, kind, key, art, wert, r.conflict.version);
      }
      if (r.ok) {
        zuletzt.current = roh;
        setzeVersion(r.version);
        setUm(r.updatedAt);
        setStand("gespeichert");
      } else {
        setKonflikt(r.conflict);
        setStand("konflikt");
      }
    } catch {
      setStand("fehler");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dk, keyVersion, kind, key, art, istLeer]);

  /** Hinten anstellen: Wer während eines Speicherns kommt, wartet und setzt
   *  dann auf dessen Version auf. Doppelte Anläufe (Zeitgeber und Verlassen
   *  des Felds) fallen am Vergleich mit `zuletzt` weg. */
  const speichern = useCallback((wert: T, erzwingen = false, basis?: number): Promise<void> => {
    const dran = kette.current.then(() => einmal(wert, erzwingen, basis));
    kette.current = dran.catch(() => {});
    return dran;
  }, [einmal]);

  useEffect(() => {
    if (!geladen.current || stand === "konflikt") return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void speichern(doc); }, 1500);
    return () => { if (timer.current) clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc]);

  return {
    doc, setDoc, stand, version, um, unlesbar, konflikt,
    jetztSpeichern: () => {
      if (timer.current) clearTimeout(timer.current);
      return speichern(doc);
    },
    uebernehmen: () => {
      const d = konflikt?.doc ?? leer;
      setDoc(d);
      zuletzt.current = JSON.stringify(d);
      setzeVersion(konflikt?.version ?? 0);
      setKonflikt(null);
      setStand("bereit");
    },
    behalten: () => {
      const basis = konflikt?.version ?? 0;
      setKonflikt(null);
      setStand("bereit");
      void speichern(doc, true, basis);
    },
  };
}

export function statusText(stand: Stand, version: number, um: string | null): string | null {
  const uhr = um ? new Date(um.endsWith("Z") ? um : `${um}Z`).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : null;
  if (stand === "speichert") return "Speichert …";
  if (stand === "gespeichert") return version ? `Gespeichert${uhr ? ` um ${uhr}` : ""}` : "Gelöscht";
  if (stand === "fehler") return "Nicht gespeichert — Verbindung prüfen.";
  return null;
}
