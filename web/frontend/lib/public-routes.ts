// Welche Seiten sich ohne Konto lesen lassen.
//
// Teilen ist die Kernhandlung der App — aber wer einen weitergereichten Link
// öffnete, sah zuerst das Registrierungsformular, bevor er überhaupt wusste,
// worum es geht. Das schreckt genau die Leute ab, die man gewinnen will.
//
// Öffentlich sind deshalb die drei Detailseiten, für die es Teilen-Knöpfe und
// Link-Vorschauen gibt. Stöbern, Suche, Dashboard, eigene Themen und alles
// Persönliche bleiben hinter der Anmeldung — die Liste hier ist die
// Frontend-Hälfte einer Grenze, die das Backend eigenständig durchsetzt
// (`optional_user` in web/backend/app/deps.py). Ein Eintrag hier allein macht
// nichts sichtbar; ohne offenen Endpunkt bliebe die Seite leer.

import { useEffect, useState } from "react";

/** Pfade (ohne Query), die auch ohne Anmeldung eine Ansicht zeigen. */
export const OEFFENTLICHE_PFADE = [
  "/council/decision",
  "/council/thema",
  "/council/person",
  "/probleme",
] as const;

/** Ist dieser Pfad ohne Konto lesbar? */
export function istOeffentlich(pfad: string | null | undefined): boolean {
  if (!pfad) return false;
  // Der statische Export legt die Seiten als Verzeichnis ab, der Browser hängt
  // dann einen Schrägstrich an — beide Schreibweisen müssen treffen.
  const p = pfad.length > 1 && pfad.endsWith("/") ? pfad.slice(0, -1) : pfad;
  return (OEFFENTLICHE_PFADE as readonly string[]).includes(p);
}

/** Ein Rücksprungziel, dem man folgen darf.
 *
 *  Nur seiteneigene Pfade: `//fremde.example` und `https://…` sind für den
 *  Browser Weiterleitungen nach außen, und ein Ziel aus der Adresszeile ist
 *  fremde Eingabe. Alles andere wird verworfen, nicht repariert.
 */
export function sicheresZiel(roh: string | null | undefined): string | null {
  if (!roh) return null;
  if (!roh.startsWith("/")) return null;
  if (roh.startsWith("//") || roh.startsWith("/\\")) return null;
  return roh;
}

/** Aktuellen Pfad samt Query als Rücksprungziel verpacken. */
export function mitRuecksprung(ziel: "/login" | "/register", weiter: string): string {
  return `${ziel}?weiter=${encodeURIComponent(weiter)}`;
}

/** Wohin nach erfolgreicher An- oder Abmeldung?
 *
 *  Wer sich von einem geteilten Beschluss aus anmeldet, will zurück zu diesem
 *  Beschluss und nicht aufs Dashboard. Bewusst erst beim Absenden aus der
 *  Adresszeile gelesen statt über `useSearchParams`: Der Hook zwingt die Seite
 *  in eine Suspense-Grenze, und der statische Export (MOBILE=1) bricht daran ab.
 */
export function zielNachAnmeldung(): string {
  if (typeof window === "undefined") return "/dashboard";
  const weiter = new URLSearchParams(window.location.search).get("weiter");
  return sicheresZiel(weiter) ?? "/dashboard";
}

/** Das eigene `?weiter=` als anhängbares Suffix — für die Querverweise zwischen
 *  Anmelden und Registrieren.
 *
 *  Ohne das verliert man das Ziel beim ersten Klick: Wer von einem geteilten
 *  Beschluss auf „Anmelden" geht und dort merkt, dass er noch kein Konto hat,
 *  landet nach dem Umweg über „Registrieren" sonst wieder auf dem Dashboard.
 *  Nach dem Mounten gelesen, damit der statische Export nichts einbackt.
 */
export function useWeiterSuffix(): string {
  const [suffix, setSuffix] = useState("");
  useEffect(() => {
    const weiter = sicheresZiel(new URLSearchParams(window.location.search).get("weiter"));
    setSuffix(weiter ? `?weiter=${encodeURIComponent(weiter)}` : "");
  }, []);
  return suffix;
}
