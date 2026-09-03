"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { getMascotTheme, type MascotTheme } from "@/lib/mascot-theme";

/**
 * Die animierte Sprite-Lotti — React-Hülle um das Web-Component
 * `<lotti-figur>` aus dem Lotti-Studio (Repo ratslotse-social).
 *
 * Das Bündel unter `public/lotti/` (Blätter, Verzeichnis, Abspieler) ist eine
 * unveränderte Kopie von dort; aktualisiert wird es mit
 * `python scripts/lotti_uebernehmen.py`. Der Abspieler ist abhängigkeitsfrei
 * (kein Canvas, kein WebGL — ein `div` mit `background-position`), respektiert
 * `prefers-reduced-motion`, pausiert außerhalb des Sichtfelds und lädt je
 * Regung nur das Blatt, das sie braucht. Welche Regungen es gibt, zeigt
 * /lotti/katalog.html im Dev-Server.
 *
 * Diese Hülle tut bewusst wenig: Element registrieren (einmal je Seite),
 * Attribute durchreichen, Größe über `className` (h-24/w-24 usw.) wie bisher beim
 * SVG. Gespielt wird deklarativ über das `regung`-Attribut — der Abspieler
 * spielt sie beim Erscheinen und bei jeder Änderung; danach übernimmt seine
 * Regie (Blinzeln, selten ein Nicken — mehr NICHT: Gesten mit Bedeutung
 * spielt nur, wer sie ausdrücklich setzt, s. DESIGNSPRACHE.md § 1).
 */

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      "lotti-figur": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        /** React 18 lässt `className` auf Custom Elements fallen — `class` nehmen. */
        class?: string;
        /** ATTRIBUT DES CUSTOM ELEMENTS — heißt im Abspieler
         *  `public/lotti/lotti-figur.js` so und bleibt deshalb deutsch.
         *  Umbenannt fiele es beim Andocken auf den Vorgabe-Pfad zurück
         *  und die Figur lüde `/lotti.json` ins Leere (404). */
        quelle?: string;
        regung?: string;
        regie?: "ruhig" | "lebhaft" | "aus";
        beschriftung?: string;
        spiegel?: string;
        "ohne-leben"?: string;
      };
    }
  }
}

/** Alle Regungen aus dem gebackenen Katalog (public/lotti/lotti.json). */
export type LottiRegung =
  | "ruht" | "blinzelt" | "nickt" | "schuettelt-kopf"
  | "winkt" | "freut-sich" | "lacht" | "staunt" | "seufzt" | "klatscht"
  | "schreckt-auf" | "verbeugt-sich" | "zeigt-auf-sich"
  | "zeigt-links" | "zeigt-rechts" | "zeigt-hoch" | "zeigt-runter"
  | "hebt-hand" | "erklaert" | "ist-traurig"
  | "denkt" | "sucht" | "wartet" | "schlaeft" | "jongliert"
  | "hat-idee" | "fragt" | "mag-das"
  | "liest" | "schreibt" | "hebt-pokal";

/* Einmal je Seite: Der Abspieler liegt als fertiges ES-Modul im Bündel und
 * definiert beim Import das Custom Element. `webpackIgnore`, weil die Datei
 * bewusst NICHT durchs Bundling läuft — sie gehört zum kopierten Bündel und
 * muss zu dessen Blättern und Verzeichnis passen, nicht zum App-Build. */
/* ── Jahreszeit: welcher Bündel-Ordner? ──────────────────────────────────
 * Das Studio backt je Jahreszeit ein komplettes Bündel (fruehling: Blume,
 * sommer: Sonnenbrille, herbst/winter: Schal, weihnachten: roter Schal) —
 * gewählt wird nur der ORDNER, der Abspieler bleibt derselbe. Bestimmt wird
 * das Datum erst nach dem Mount (wie useMascotTheme, gegen eingebrannte
 * Build-Jahreszeiten im statischen Export); bis dahin steht die neutrale
 * Lotti da. Die übrigen Feiertage (Pride, Halloween, Ostern) tragen wie in
 * der 3D-Szene ihr Jahreszeiten-Outfit weiter — dafür gibt es keine Blätter.
 * Der Hook lebt hier statt in seasonal-mascot.tsx, weil der Weg dorthin ein
 * Import-Kreis wäre (seasonal-mascot → mascot → lotti). */
function varianteFuer(theme: MascotTheme): string {
  if (theme.holiday === "christmas") return "weihnachten";
  return { spring: "fruehling", summer: "sommer", autumn: "herbst", winter: "winter" }[theme.season];
}

function useJahreszeitQuelle(): string {
  const [source, setQuelle] = useState("/lotti/");
  useEffect(() => {
    const setzen = () => setQuelle(`/lotti/${varianteFuer(getMascotTheme())}/`);
    setzen();
    // Über Mitternacht hinweg aktuell halten (lange Sessions/Kiosk-Displays).
    const id = setInterval(setzen, 60 * 60 * 1000);
    return () => clearInterval(id);
  }, []);
  return source;
}

let geladen = false;
function elementLaden() {
  if (geladen || typeof window === "undefined") return;
  geladen = true;
  // Über eine Variable, damit TypeScript die URL nicht als Modul auflösen will.
  const url = "/lotti/lotti-figur.js";
  import(/* webpackIgnore: true */ url).catch(() => {
    // Ohne Abspieler bleibt das Element leer — die Seite trägt keinen Fehler.
    geladen = false;
  });
}

export function Lotti({
  regung,
  regie = "ruhig",
  spiegel = false,
  decorative = false,
  label,
  className,
}: {
  /** Startregung; jede Änderung spielt neu. Ohne Angabe: ruhende Figur. */
  regung?: LottiRegung;
  /** Was Lotti VON SELBST tut: "ruhig" (Default), "lebhaft" oder "aus". */
  regie?: "ruhig" | "lebhaft" | "aus";
  /** Horizontal gespiegelt — für Figuren am rechten Rand, die nach links schauen. */
  spiegel?: boolean;
  /** Rein dekorativ: für Vorlesesoftware unsichtbar (Abspieler-Default). */
  decorative?: boolean;
  /** Beschriftung für Vorlesesoftware; ohne sie ist die Figur aria-hidden. */
  label?: string;
  /** Größe wie beim alten SVG über h-24/w-24 usw. (das Element ist quadratisch). */
  className?: string;
}) {
  useEffect(elementLaden, []);
  const source = useJahreszeitQuelle();
  return (
    /* `source` liest der Abspieler nur beim Andocken — der `key` baut das
       Element beim Jahreszeitenwechsel neu auf, statt ins Leere zu schreiben. */
    <lotti-figur
      key={source}
      quelle={source}
      regung={regung}
      regie={regie}
      spiegel={spiegel ? "" : undefined}
      beschriftung={decorative ? undefined : label}
      class={cn("select-none", className)}
    />
  );
}
