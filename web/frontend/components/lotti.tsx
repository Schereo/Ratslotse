"use client";

import * as React from "react";
import { useEffect } from "react";
import { cn } from "@/lib/utils";

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
 * Regie (Blinzeln, gelegentlich eine kleine Geste).
 */

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      "lotti-figur": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        /** React 18 lässt `className` auf Custom Elements fallen — `class` nehmen. */
        class?: string;
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
  | "hat-idee" | "fragt" | "mag-das";

/* Einmal je Seite: Der Abspieler liegt als fertiges ES-Modul im Bündel und
 * definiert beim Import das Custom Element. `webpackIgnore`, weil die Datei
 * bewusst NICHT durchs Bundling läuft — sie gehört zum kopierten Bündel und
 * muss zu dessen Blättern und Verzeichnis passen, nicht zum App-Build. */
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
  return (
    <lotti-figur
      quelle="/lotti/"
      regung={regung}
      regie={regie}
      spiegel={spiegel ? "" : undefined}
      beschriftung={decorative ? undefined : label}
      class={cn("select-none", className)}
    />
  );
}
