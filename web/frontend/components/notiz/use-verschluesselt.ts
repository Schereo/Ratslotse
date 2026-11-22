"use client";

/* Laden und Zwischenspeichern eines verschlüsselten Dokuments (Notiz oder
   Mitschrieb): 1,5 s Ruhe nach dem Tippen, dann verschlüsselt hinaus; ein
   leeres Dokument wird gelöscht; ein Stand von einem anderen Gerät führt zur
   Frage statt zum stillen Überschreiben. */

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

  useEffect(() => {
    let weg = false;
    geladen.current = false;
    setStand("lädt");
    loadDoc<T>(dk, kind, key, art).then((n) => {
      if (weg) return;
      const d = n?.doc ?? leer;
      setDoc(d);
      zuletzt.current = JSON.stringify(d);
      setVersion(n?.version ?? 0);
      setUm(n?.updatedAt ?? null);
      setUnlesbar(n != null && !n.lesbar);
      setStand("bereit");
      geladen.current = true;
    }).catch(() => { if (!weg) setStand("fehler"); });
    return () => { weg = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dk, kind, key, art]);

  const speichern = useCallback(async (wert: T, basis: number, erzwingen = false) => {
    const roh = JSON.stringify(wert);
    if (!erzwingen && roh === zuletzt.current) return;
    setStand("speichert");
    try {
      if (istLeer(wert)) {
        if (basis > 0) await deleteDoc(kind, key, art);
        zuletzt.current = roh;
        setVersion(0);
        setUm(null);
        setStand("gespeichert");
        return;
      }
      const r = await saveDoc<T>(dk, keyVersion, kind, key, art, wert, basis);
      if (r.ok) {
        zuletzt.current = roh;
        setVersion(r.version);
        setUm(r.updatedAt);
        setStand("gespeichert");
      } else {
        setKonflikt(r.conflict);
        setStand("konflikt");
      }
    } catch {
      setStand("fehler");
    }
  }, [dk, keyVersion, kind, key, art, istLeer]);

  useEffect(() => {
    if (!geladen.current || stand === "konflikt") return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void speichern(doc, version); }, 1500);
    return () => { if (timer.current) clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc]);

  return {
    doc, setDoc, stand, version, um, unlesbar, konflikt,
    jetztSpeichern: () => speichern(doc, version),
    uebernehmen: () => {
      const d = konflikt?.doc ?? leer;
      setDoc(d);
      zuletzt.current = JSON.stringify(d);
      setVersion(konflikt?.version ?? 0);
      setKonflikt(null);
      setStand("bereit");
    },
    behalten: () => {
      const basis = konflikt?.version ?? 0;
      setKonflikt(null);
      setStand("bereit");
      void speichern(doc, basis, true);
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
