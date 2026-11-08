// Was über den Einrichtungs-Assistenten bekannt sein muss, BEVOR er geladen ist.
//
// Der Assistent selbst (components/onboarding-flow.tsx) ist mit Themen-Blatt,
// Stadtteil-Karte und Gremien-Liste gut 12 KB (gzip) groß und erscheint nur
// für neue Konten. Bis 11/2026 hing er im Wurzel-Layout und kam damit auf jede
// Seite — auch auf Impressum, Anmeldung und Teilen-Seite, wo er nie erscheinen
// kann. Jetzt lädt ihn das Tor (components/onboarding-gate.tsx) im App-Layout
// erst nach, wenn der Server `pending` meldet.
//
// Abzeichen, Tour-Einladung und Anmeldung fragen aber schon vorher, ob er
// läuft oder gleich läuft. Diese Fragen und die Ereignisse stehen deshalb
// hier, ohne Abhängigkeit auf den Assistenten.

import { einladungStand } from "@/lib/tour-einladung";
import { darfAdmin } from "@/lib/rechte";
import { pfad } from "@/lib/utils";

/** Im Browser darf der Assistent nur INNERHALB der App auftauchen.
 *
 *  Im Web liegt unter der App auch die Landingpage, das Changelog, Impressum
 *  und Datenschutz — und ein deckender Vollbild-Assistent über dem Impressum
 *  wäre schlicht falsch, gerade weil solche Seiten aus Rechtsgründen
 *  erreichbar bleiben müssen.
 *
 *  Bewusst eine Positivliste der Bereiche aus `app/(app)/`: Eine Negativliste
 *  müsste bei jeder neuen öffentlichen Seite nachgezogen werden, und wer das
 *  vergisst, merkt es nicht — der Fehler zeigt sich nur angemeldeten
 *  Erstnutzer*innen auf genau dieser Seite. */
export const APP_BEREICHE = [
  "/dashboard", "/council", "/fragen", "/topics", "/abos",
  "/bookmarks", "/quiz", "/account", "/admin", "/haushalt",
];

export function imAppBereich(pathname: string | null): boolean {
  const p = pfad(pathname);
  return APP_BEREICHE.some((b) => p === b || p.startsWith(`${b}/`));
}

/** Ein Konto allein reicht nicht — frisch registriert ist es „pending" und
 *  unbestätigt, und die Schritte 1–3 (Abos, Themen) laufen dann in 403. Erst
 *  wenn es freigeschaltet ist, geht es weiter; bis dahin liegt die
 *  Bestätigungs-Aufforderung frei. Admins sind wie im App-Layout ausgenommen. */
export function isUsable(user: { status?: string; email_verified?: boolean; permissions?: readonly string[] | null } | null): boolean {
  if (!user) return false;
  if (darfAdmin(user)) return true;
  return user.status === "active" && !!user.email_verified;
}

/** Läuft der Flow gerade? Der Abzeichen-Toast fragt das ab und schweigt so
 *  lange: Beim Anmelden registriert die App den Push-Token, was sofort das
 *  „Frühwarner"-Abzeichen auslöst — die Meldung knallte damit über den
 *  Willkommens-Gruß, bevor man überhaupt etwas getan hatte. Modul-State statt
 *  Context, damit der Celebrator nicht am Flow hängen muss. */
let flowVisible = false;
/** Der Flow WEISS noch nicht, ob er sich zeigt — er wartet auf `/onboarding/setup`
 *  (oder, seit er nachgeladen wird, auf sein eigenes Bündel).
 *
 *  Diese zweite Marke war nötig, seit die Entscheidung serverseitig fällt: In
 *  der Lücke zwischen Seitenaufbau und Antwort war `flowVisible` noch `false`,
 *  und der Abzeichen-Toast fuhr genau dort hinein — quer über den Willkommens-
 *  Gruß, also exakt der Fall, den der Riegel verhindern soll. Vorher las der
 *  Flow den localStorage synchron und war sofort „sichtbar"; es gab keine Lücke.
 *
 *  Bis der Assistent geladen ist, setzt das Tor die Marke, danach er selbst. */
let flowDeciding = false;
/** Stand der Assistent auf dieser Seite schon einmal offen? Dann ist, was
 *  währenddessen verdient wurde, ein Abzeichen der Einrichtung — und das feiert
 *  der Celebrator nicht (Tims Befund 08.11.2026, s. `BadgeCelebrator`). */
let flowWasVisible = false;

export function setFlowVisible(visible: boolean): void {
  flowVisible = visible;
  if (visible) flowWasVisible = true;
}
export function isFlowDeciding(): boolean {
  return flowDeciding;
}
export function setFlowDeciding(deciding: boolean): void {
  flowDeciding = deciding;
}

/** Die Tour-Einladung (`tour-einladung.tsx`) ist der letzte Takt der Einrichtung:
 *  Solange sie offen steht, halten die Abzeichen-Meldungen genauso still wie
 *  unter dem Assistenten — sonst knallte das „Frühwarner"-Abzeichen genau in
 *  Lottis Frage hinein. Gefragt wird die gemerkte Marke, nicht ein Zustand im
 *  Speicher dieser Sitzung: Nach einem Neuladen mit offener Einladung ist die
 *  Komponente noch gar nicht da, wenn die Abzeichen das erste Mal fragen. */
export function isOnboardingVisible(): boolean {
  return flowVisible || flowDeciding || einladungStand() === "offen";
}
export function einrichtungLiefHier(): boolean {
  return flowWasVisible;
}

/** Wird beim Abschluss/Abbruch gefeuert, damit, was auf das Ende wartet, loslegen
 *  kann: der Push-Hinweis und geparkte Abzeichen-Meldungen. Feuert AUCH, wenn der Flow nur entschieden hat,
 *  sich nicht zu zeigen — für „jemand hat die Einrichtung gerade wirklich
 *  beendet" gibt es deshalb das zweite Ereignis darunter. */
export const ONBOARDING_DONE_EVENT = "ratslotse:onboarding-done";
/** Nur beim echten Abschluss des letzten Schritts (auch per „Überspringen"
 *  dort) — das Signal, auf das die Tour-Einladung wartet. Vorher landete man
 *  nach dem letzten Schritt unvermittelt auf „Heute" und musste die Tour in
 *  der „Erste Schritte"-Karte erst einmal finden. */
export const ONBOARDING_FINISHED_EVENT = "ratslotse:onboarding-finished";
/** Der Auftakt tritt beiseite und gibt den Login frei. Die Login-Seite liegt
 *  darunter längst gemountet — ohne dieses Signal begrüßte sie eine:n
 *  Erstnutzer*in mit „Willkommen zurück". */
export const ONBOARDING_NEEDS_LOGIN_EVENT = "ratslotse:onboarding-needs-login";
