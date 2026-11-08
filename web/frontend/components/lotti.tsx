"use client";

import * as React from "react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";
import { LOTTI_BASE } from "@/lib/asset-paths";
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
 * SVG. Dazu zwei Dinge, die nur hier gehen, weil der Abspieler unverändert
 * bleibt: Sie hängt die Figur erst in Sichtnähe ein und gleich mit dem
 * richtigen Jahreszeiten-Ordner (s. unten). Adressiert wird das Bündel über
 * `LOTTI_BASE` (lib/asset-paths.ts) — versioniert, damit der Browser es
 * zwischenspeichern darf. Gespielt wird deklarativ über das `regung`-Attribut — der Abspieler
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
      /** Steht da, bis die Figur in Sichtnähe kommt (s. useNearViewport).
       *  Ein eigenes unbekanntes Element statt eines `span`: Es bekommt in
       *  globals.css dieselbe Regel wie das noch nicht aufgerüstete
       *  `<lotti-figur>` und damit genau dessen Kasten. */
      "lotti-placeholder": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        class?: string;
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
 * das Datum erst im Browser (wie useMascotTheme, gegen eingebrannte
 * Build-Jahreszeiten im vorgerenderten HTML). Die übrigen Feiertage (Pride,
 * Halloween, Ostern) tragen wie in der 3D-Szene ihr Jahreszeiten-Outfit
 * weiter — dafür gibt es keine Blätter. Der Hook lebt hier statt in
 * seasonal-mascot.tsx, weil der Weg dorthin ein Import-Kreis wäre
 * (seasonal-mascot → mascot → lotti).
 *
 * KEINE FIGUR MIT DEM NEUTRALEN ORDNER. Bis 11/2026 begann jede Figur mit
 * useState("/lotti/") und sprang erst im Effekt auf die Jahreszeit. Für die
 * erste Figur einer Seite war das harmlos, der Abspieler war da noch nicht
 * geladen. Jede SPÄTER einhängende Figur (in der App-Hülle fast jede, sie
 * rendert erst nach /auth/me) traf aber auf den schon definierten Abspieler,
 * dockte sofort mit dem neutralen Ordner an und holte dessen Verzeichnis und
 * Blatt; der key-Wechsel einen Augenblick später baute sie mit dem
 * Jahreszeiten-Ordner neu, die neutralen Downloads liefen trotzdem zu Ende.
 * Gemessen auf 22 von 67 Seiten, 0,6–1,3 MB je Seite, nie zu sehen.
 *
 * useSyncExternalStore trennt die beiden Fälle: Beim Hydrieren gilt der
 * Server-Wert `null` (es steht der Platzhalter da), jede Figur, die danach
 * einhängt, kennt den Ordner schon beim ersten Rendern. */
function varianteFuer(theme: MascotTheme): string {
  if (theme.holiday === "christmas") return "weihnachten";
  return { spring: "fruehling", summer: "sommer", autumn: "herbst", winter: "winter" }[theme.season];
}

function seasonSource(): string {
  return `${LOTTI_BASE}${varianteFuer(getMascotTheme())}/`;
}

function subscribeHourly(onChange: () => void): () => void {
  // Über Mitternacht hinweg aktuell halten (lange Sessions/Kiosk-Displays).
  const id = setInterval(onChange, 60 * 60 * 1000);
  return () => clearInterval(id);
}

function useSeasonSource(): string | null {
  return useSyncExternalStore(subscribeHourly, seasonSource, () => null);
}

/* ── Erst in Sichtnähe ────────────────────────────────────────────────────
 * Der Abspieler lädt beim Andocken sofort Verzeichnis, Ruhe-Blatt und das
 * Blatt der Startregung; sein eigener IntersectionObserver hält nur den TAKT
 * an, nicht das Laden. Die drei Figuren unterhalb des ersten Bildschirms der
 * Startseite kosteten so 1,2 MB, bevor jemand dorthin scrollte, und eine
 * Figur mit `hidden sm:block` lud auf dem Telefon, ohne je zu erscheinen.
 * Deshalb steht bis kurz vor dem sichtbaren Bereich nur der Platzhalter da —
 * gleich groß, also springt nichts. Der Abspieler selbst wird auch erst
 * dann geholt. Die Figur erscheint ohnehin erst, wenn ihr Blatt geladen ist;
 * die 300 px Vorlauf geben dem Blatt beim gemächlichen Scrollen einen
 * Vorsprung. Wer schnell wischt, sieht sie einen Augenblick später
 * erscheinen — so wie bisher schon beim ersten Laden der Seite. */
const NEAR_MARGIN = "300px 0px";

function useNearViewport(): [React.RefObject<HTMLElement>, boolean] {
  const ref = useRef<HTMLElement>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    if (near) return;
    const element = ref.current;
    if (!element) return;
    if (typeof IntersectionObserver === "undefined") {
      setNear(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          observer.disconnect();
          setNear(true);
        }
      },
      { rootMargin: NEAR_MARGIN },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [near]);
  return [ref, near];
}

let geladen = false;
function elementLaden() {
  if (geladen || typeof window === "undefined") return;
  geladen = true;
  // Über eine Variable, damit TypeScript die URL nicht als Modul auflösen will.
  const url = `${LOTTI_BASE}lotti-figur.js`;
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
  const source = useSeasonSource();
  const [placeholderRef, near] = useNearViewport();
  const ready = near && source !== null;
  useEffect(() => {
    if (ready) elementLaden();
  }, [ready]);
  const caption = decorative ? undefined : label;
  if (!ready) {
    return (
      <lotti-placeholder
        ref={placeholderRef}
        role={caption ? "img" : "presentation"}
        aria-label={caption}
        aria-hidden={caption ? undefined : "true"}
        class={cn("select-none", className)}
      />
    );
  }
  return (
    /* `source` liest der Abspieler nur beim Andocken — der `key` baut das
       Element beim Jahreszeitenwechsel neu auf, statt ins Leere zu schreiben. */
    <lotti-figur
      key={source}
      quelle={source}
      regung={regung}
      regie={regie}
      spiegel={spiegel ? "" : undefined}
      beschriftung={caption}
      class={cn("select-none", className)}
    />
  );
}
