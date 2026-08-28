"use client";

import Link from "next/link";
import { Check, Pencil, Trash2 } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { OutcomeBadge } from "@/components/decision-ui";
import { formatDate } from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import type { Topic } from "@/lib/types";

/** Eine Karte auf „Meine Themen".
 *
 *  Bis zum 28.08.2026 trug sie eine Zahl, einen einzigen Titel und einen Link.
 *  Wer wissen wollte, was in seinen Themen steckt, musste jedes einzeln
 *  öffnen — bei fünf Themen fünf Seitenwechsel. Jetzt steht der jüngste
 *  Bestand direkt darauf: bis zu fünf Beschlüsse mit Datum, Gremium und
 *  Ergebnis, die ungelesenen mit einem Punkt davor.
 *
 *  Die Karte ist bewusst eine eigene Datei und nicht Teil der Seite: Dieselbe
 *  Anatomie trägt Desktop (zwei Spalten) und Telefon (eine) — was sich
 *  unterscheidet, ist nur die Spaltenzahl außen herum.
 */
export function ThemenKarte({
  topic, onEdit, onDelete, loeschFrage, onLoeschFrage, onAlleGelesen, onTrefferGelesen,
}: {
  topic: Topic;
  onEdit: () => void;
  onDelete: () => void;
  /** Die Löschfrage steht offen — sie liegt bei der Seite, damit immer nur
   *  EINE Karte fragt. */
  loeschFrage: boolean;
  onLoeschFrage: (offen: boolean) => void;
  /** Alle Treffer dieses Themas als gelesen markieren. */
  onAlleGelesen: () => void;
  /** EINEN Treffer als gelesen markieren — wer ihn öffnet, hat ihn gelesen. */
  onTrefferGelesen: (decisionId: number) => void;
}) {
  const treffer = topic.recent_hits ?? [];
  const gesamt = topic.decision_count;
  const gedeckelt = !!topic.decision_count_capped;
  const neu = topic.unread_count ?? 0;

  /* Die rechte Hälfte des Kickers beantwortet „wie viel und wie frisch?" —
     und muss dabei die drei Zustände auseinanderhalten, die auf der alten
     Karte alle gleich aussahen: gerechnet mit Treffern, gerechnet ohne
     Treffer, noch nicht gerechnet (Tims Befund 28.08.2026). */
  const bilanz = !topic.matched && gesamt === 0
    ? "Wird noch gezählt"
    : gesamt > 0
      ? `${gesamt}${gedeckelt ? "+" : ""} gesamt · ${topic.hits_30d ?? 0} in 30 Tagen`
      : `Beobachtet seit ${formatDate(topic.created_at)}`;

  return (
    <article className="rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] sm:px-[18px]">
      <div className="flex items-start justify-between gap-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <h3 className="truncate font-display text-base font-semibold text-foreground">{topic.name}</h3>
          {/* Das Abzeichen IST der Knopf, der es wegräumt. Vorher ging es nur
              weg, wenn man „alle ansehen" antippte — wer die Treffer direkt auf
              der Karte gelesen hatte, trug es weiter vor sich her (Tims Frage
              28.08.2026). Einzelne Zeilen abzuhaken wäre die feinere, aber
              mühsamere Lösung; gemeint ist ja „ich habe das hier gesehen". */}
          {neu > 0 && (
            <button
              type="button" onClick={onAlleGelesen}
              title="Alle als gelesen markieren"
              aria-label={neu === 1
                ? `1 neuen Treffer bei ${topic.name} als gelesen markieren`
                : `${neu} neue Treffer bei ${topic.name} als gelesen markieren`}
              className="group inline-flex shrink-0 items-center gap-1.5 rounded-full bg-signal/[0.12] px-2 py-0.5 text-[11px] font-semibold text-signal transition-colors hover:bg-signal/20"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-signal group-hover:hidden" aria-hidden />
              <Check className="hidden h-3 w-3 group-hover:block" aria-hidden />
              {neu} {neu === 1 ? "neuer" : "neue"}
            </button>
          )}
        </div>
        <div className="flex shrink-0 gap-0.5">
          <button
            type="button" onClick={onEdit} title="Bearbeiten" aria-label={`${topic.name} bearbeiten`}
            className="flex h-[26px] w-[26px] items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button" onClick={() => onLoeschFrage(true)} title="Löschen" aria-label={`${topic.name} löschen`}
            className="flex h-[26px] w-[26px] items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40 dark:hover:text-red-300"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <p className="mt-1 text-[13.5px] leading-relaxed text-muted-foreground">{topic.description}</p>

      {/* Die Rückfrage steht IN der Karte, nicht in einem Dialog über der
          Seite: Sie betrifft genau dieses Thema, und man sieht beim Antworten
          noch, was man löscht. */}
      {loeschFrage && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2.5 rounded-xl border border-red-200 bg-red-50 px-3 py-2 dark:border-red-900/50 dark:bg-red-950/30">
          <span className="text-[12.5px] font-medium text-red-700 dark:text-red-300">
            Thema löschen? Du bekommst dazu keine Treffer mehr.
          </span>
          <div className="flex shrink-0 gap-1.5">
            <button
              type="button" onClick={onDelete}
              className="inline-flex h-[26px] items-center rounded-full bg-red-700 px-2.5 text-xs font-semibold text-white"
            >
              Löschen
            </button>
            <button
              type="button" onClick={() => onLoeschFrage(false)}
              className="inline-flex h-[26px] items-center rounded-full border border-border bg-card px-2.5 text-xs font-medium text-foreground"
            >
              Behalten
            </button>
          </div>
        </div>
      )}

      <div className="mt-4 flex items-baseline justify-between gap-2.5 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        <span>Zuletzt gefunden</span>
        <span className="text-right">{bilanz}</span>
      </div>

      {treffer.length > 0 ? (
        <ul className="mt-0.5">
          {treffer.map((h, i) => (
            <li
              key={h.id}
              className={`flex items-start justify-between gap-2.5 py-2.5 ${i > 0 ? "border-t border-border/60" : ""}`}
            >
              <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-1.5">
                  {h.is_new && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-signal" aria-label="neu" />}
                  {/* Wer einen Beschluss öffnet, hat genau den gelesen — aus
                      „2 neue" wird „1 neuer" (Tims Wunsch 28.08.2026). Vorher
                      räumte nur ein Klick auf das Abzeichen oder auf „alle
                      ansehen" auf, und der räumte gleich alles weg. */}
                  <Link
                    href={decisionHref(h.id)}
                    onClick={() => h.is_new && onTrefferGelesen(h.id)}
                    className={`truncate text-[13.5px] text-foreground hover:underline ${h.is_new ? "font-semibold" : "font-medium"}`}
                  >
                    {h.title}
                  </Link>
                </div>
                {/* `truncate`: Auf dem Telefon brach „27.08.2026 · VERKEHR &
                    MOBILITÄT" in eine zweite Zeile und stand damit ausgerechnet
                    unter einem Titel, der selbst gekürzt ist — das las sich wie
                    ein Fehler. Ein langer Gremiumsname wird lieber gekappt. */}
                <p className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                  {formatDate(h.session_date)} · {shortCommittee(h.committee)}
                </p>
              </div>
              <OutcomeBadge outcome={h.outcome} />
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex flex-col items-center gap-2.5 px-3 pb-2.5 pt-4 text-center">
          <Mascot pose="search" decorative className="h-16 w-16" />
          <div>
            <p className="text-[13.5px] font-semibold text-foreground">
              {topic.matched || gesamt > 0 ? "Noch nichts gefunden." : "Treffer werden noch gezählt."}
            </p>
            <p className="mx-auto mt-0.5 max-w-[260px] text-[13px] leading-relaxed text-muted-foreground">
              {topic.matched || gesamt > 0
                ? "Sobald der Rat zu diesem Thema etwas beschließt, sagen wir dir Bescheid."
                : "Gleich steht hier, was der Rat dazu schon entschieden hat."}
            </p>
          </div>
        </div>
      )}

      {gesamt > 0 && (
        <div className="mt-2.5 border-t border-border/60 pt-3">
          {/* `cat=all` ist Pflicht, nicht Geschmack: Die Suchseite steht sonst
              auf „nur Beschlüsse" und wirft alle Berichte aus der Liste, die
              diese Zahl mitzählt (Tims Befund, Build 12: Karte „40+", Liste 25). */}
          {/* Die Trefferliste zu öffnen gilt weiter als gesehen (RL-903) —
              fire-and-forget, der Seitenwechsel wartet nicht auf den Server. */}
          <Link
            href={`/council?tab=decisions&cat=all&topic=${topic.id}`}
            onClick={onAlleGelesen}
            className="text-[13px] font-medium text-primary hover:underline"
          >
            Alle {gesamt}{gedeckelt ? "+" : ""} Beschlüsse →
          </Link>
        </div>
      )}
    </article>
  );
}
