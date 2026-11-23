"use client";

/**
 * Handlungen in der Oberfläche zählen, die sonst keinen Endpunkt aufrufen.
 *
 * Die Befehlspalette zu öffnen ist so eine: Es passiert nur im Browser, und
 * ohne Zähler bliebe „benutzt die überhaupt jemand?" eine Vermutung (Tims
 * Frage vom 22.11.2026). Gezählt wird je Konto und Tag, wie jede andere
 * Funktion — ohne Seite, ohne Eingabe, ohne Uhrzeit.
 *
 * **Die Namen sind eine Positivliste auf dem Server** (`UI_EVENTS` in
 * `web/backend/app/routers/feedback.py`); ein Name, den er nicht kennt, wird
 * abgewiesen. `tests/test_ereignisse.py` hält beide Listen gegeneinander.
 *
 * **Darf nie stören:** `sendAndForget` wirft nicht und wartet auf nichts.
 */
import { apiUrl } from "./api";
import { sendAndForget } from "./send-and-forget";

export type UiEvent = "palette_desktop" | "palette_mobile";

export function reportUiEvent(kind: UiEvent): void {
  sendAndForget(apiUrl("/activity/event"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind }),
    keepalive: true,
  });
}
