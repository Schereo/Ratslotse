"use client";

import { Play } from "lucide-react";
import { cn } from "@/lib/utils";
import type { VideoResult } from "@/lib/types";
import { voteLabel } from "@/components/decision-ui";

/**
 * Vorläufiges Abstimmungsergebnis aus der O1-Übertragung (RL-Video): LLM-
 * gelesen aus dem Live-Mitschnitt des Streams (noch am Sitzungsabend) oder
 * aus den Untertiteln der YouTube-Aufzeichnung (tags darauf) — das amtliche
 * Protokoll braucht 1–2 Monate. Zwei Bausteine:
 *
 * - `VideoResultChip` an der TOP-Zeile: Punkt + Wort in der Farbgrammatik
 *   der Beschlüsse (decision-ui.tsx), aber im GESTRICHELTEN Rahmen — die
 *   Designsprache reserviert gestrichelt für „nicht von uns / noch nicht
 *   fertig", genau das ist ein unbestätigtes Ergebnis. Mit `video_id`
 *   springt der Zeitstempel zur Fundstelle im Video; ohne (Livestream —
 *   die Aufzeichnung existiert noch nicht) ist der Chip kein Link und
 *   zeigt keine Zeit: die gespeicherten Sekunden zählen ab Aufnahmestart.
 * - `VideoResultsNotice` einmal über der Tagesordnung: benennt Quelle und
 *   Vorbehalt (Ehrlichkeit ist Designprinzip — der Disclaimer hat einen
 *   festen Ort und hängt nicht an jedem Chip einzeln).
 *
 * Beide erscheinen nur, solange der TOP keinen Protokoll-Beschluss hat —
 * sobald das Protokoll da ist, gewinnt es, und die Chips verschwinden.
 */

/** Farben wie OUTCOME_DOT_CLS in decision-ui.tsx — `removed` gibt es nur
 *  hier (das Protokoll kennt den Wert nicht: abgesetzte TOPs haben dort
 *  einfach keinen Beschluss). */
const DOT_CLS: Record<VideoResult["outcome"], string> = {
  accepted: "bg-[#22c55e]",
  rejected: "bg-[#ef4444]",
  postponed: "bg-[#f59e0b]",
  noted: "bg-blue-500",
  removed: "bg-muted-foreground/50",
};

const LABEL: Record<VideoResult["outcome"], string> = {
  accepted: "Angenommen",
  rejected: "Abgelehnt",
  postponed: "Vertagt",
  noted: "Zur Kenntnis",
  removed: "Abgesetzt",
};

/** 5025 → „1:23:45" — Stunden ohne führende Null, wie YouTube selbst. */
export function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

export function watchUrl(r: VideoResult): string {
  const t = r.video_seconds != null ? `&t=${Math.max(0, r.video_seconds - 5)}s` : "";
  return `https://www.youtube.com/watch?v=${r.video_id}${t}`;
}

export function VideoResultChip({ r, layout = "row" }: {
  r: VideoResult;
  /** "row" — in der TOP-Zeile (Flex-Nachbar von Titel und Merkzeichen);
   *  "block" — in einem eigenen Kasten wie dem Dringlichkeits-Block, wo
   *  die Umbruch-Regeln der Zeile nichts zu suchen haben. */
  layout?: "row" | "block";
}) {
  // Der äußere Span trägt das Umbruch-Verhalten: Unter 744 px (Variant `mobil:` — max-sm gibt es bei raw-Screens nicht, s. tailwind.config) quetschte der
  // Chip als Flex-Nachbar den TOP-Titel auf Ein-Wort-Zeilen — dort nimmt
  // der Wrapper die volle Zeile (basis-full) unter dem Titel, eingerückt
  // auf die Titel-Spalte (Nummernbreite w-10 + gap-x-3); der Chip selbst
  // bleibt so breit wie sein Inhalt, sonst liefe der gestrichelte Rahmen
  // über die ganze Karte.
  // Und order-last: mobil rückt der Chip ans ZEILENENDE — sonst wrappt das
  // Merkzeichen hinter der vollen Chip-Zeile allein nach unten links, statt
  // oben rechts neben dem Titel zu bleiben.
  const inner = (
    <>
      <span className={cn("h-[7px] w-[7px] rounded-full", DOT_CLS[r.outcome])} aria-hidden />
      {LABEL[r.outcome]}
      {/* vote steht nur da, wo der Wortlaut ihn trägt (council/videos.py) —
          fehlt er, bleibt der Chip beim bloßen Ergebnis statt zu raten. */}
      {r.vote && <span className="font-normal text-muted-foreground">{voteLabel(r.vote)}</span>}
      {r.video_id && r.video_seconds != null && (
        <span className="inline-flex items-center gap-0.5 font-normal tabular-nums text-muted-foreground">
          <Play className="h-3 w-3" aria-hidden />
          {formatTimestamp(r.video_seconds)}
        </span>
      )}
      <span className="sr-only">— vorläufig, automatisch aus der Übertragung der Sitzung erkannt</span>
    </>
  );
  const chipCls = cn(
    "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full",
    "border border-dashed border-border px-2 py-0.5 text-xs font-medium text-foreground",
  );
  return (
    <span className={layout === "row"
      ? "shrink-0 mobil:order-last mobil:ml-[52px] mobil:basis-full"
      : "mt-1.5 inline-flex"}>
    {r.video_id ? (
      <a
        href={watchUrl(r)}
        target="_blank"
        rel="noreferrer"
        onClick={(e) => e.stopPropagation()}
        // Das title-Attribut trägt den wörtlichen Transkript-Beleg — echtes
        // Zitat, darum (anders als bei Paraphrasen) mit Anführungszeichen.
        title={r.quote ? `„${r.quote}“` : undefined}
        className={cn(chipCls, "transition-colors hover:border-primary/50 hover:text-primary")}
      >
        {inner}
      </a>
    ) : (
      <span title={r.quote ? `„${r.quote}“` : undefined} className={chipCls}>
        {inner}
      </span>
    )}
    </span>
  );
}

export function VideoResultsNotice({ count, videoId }: { count: number; videoId: string }) {
  // Zwei Quellen, ein Vorbehalt: mit videoId stammen die Ergebnisse aus der
  // YouTube-Aufzeichnung (Zeitstempel springen ins Video), ohne stammen sie
  // aus dem Live-Mitschnitt des O1-Streams — dann gibt es noch kein Video,
  // auf das ein Zeitstempel zeigen könnte.
  return (
    <div className="mb-3 rounded-lg border border-dashed border-border bg-muted/40 p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
        {videoId ? "Vorläufig · aus der Videoaufzeichnung" : "Vorläufig · aus der Live-Übertragung"}
      </p>
      <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
        {count === 1 ? "Ein Ergebnis" : `${count} Ergebnisse`} mit gestricheltem
        Rand hat eine Maschine aus der{" "}
        {videoId ? (
          <a
            href={`https://www.youtube.com/watch?v=${videoId}`}
            target="_blank"
            rel="noreferrer"
            className="text-primary hover:underline"
          >
            O1-Aufzeichnung der Sitzung
          </a>
        ) : (
          <a
            href="https://oeins.de/tv-stream/"
            target="_blank"
            rel="noreferrer"
            className="text-primary hover:underline"
          >
            O1-Übertragung der Sitzung
          </a>
        )}{" "}
        gelesen — ohne Gewähr, das amtliche Protokoll folgt.
        {videoId
          ? " Der Zeitstempel springt zur Stelle im Video."
          : " Verweise ins Video folgen, sobald die Aufzeichnung online ist."}
      </p>
    </div>
  );
}
