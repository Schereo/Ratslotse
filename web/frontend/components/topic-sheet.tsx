"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Check, Loader2, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { entwurfMelden } from "@/lib/draft";
import { Button, Skeleton } from "@/components/ui";

/** Antwort von POST /topics/describe — Beschreibungs-Vorschlag plus die Belege,
 *  mit denen das Blatt „Passt gerade auf" und die Vagheits-Warnung füllt. */
export type Described = {
  description: string;
  matches: number;
  /** Die Zahl ist der Deckel, nicht das Ergebnis → „40+" (wie auf der Karte). */
  matches_capped: boolean;
  verdict: "belegt" | "plausibel" | "ungeeignet";
  examples: string[];
  is_council_topic: boolean;
  reason: string;
  vague: boolean;
  hint: string;
  suggestion: string;
};

/** Nur, was das Blatt wirklich braucht — passt sowohl auf die Zeilen im
 *  Onboarding als auch auf `Topic` aus lib/types.ts. */
export type SheetTopic = { id: number; name: string; description: string };

/** „anpassen": Name + Beschreibung bearbeiten. Zwei Dinge machen es mehr als ein
 *  Formular — beide zielen darauf, dass man die Folgen der eigenen Änderung
 *  sieht, bevor man speichert:
 *  „Passt gerade auf" zählt live, worauf der Text zutrifft, und die
 *  Vagheits-Prüfung warnt bei zu breiten Formulierungen. Sie blockiert nicht:
 *  „Trotzdem speichern" bleibt immer möglich. */
export function TopicSheet({ topic, nameEditable = false, onClose, onSaved }: {
  topic: SheetTopic;
  /** Themen-Seite: dort darf man ein Thema auch umbenennen. Im Onboarding
   *  steht der Name fest — er kommt gerade aus der Auswahl davor. */
  nameEditable?: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(topic.name);
  const [description, setDescription] = useState(topic.description ?? "");
  // Design 29a (P8): Auch hier steckt getippte Arbeit drin — bei abgelaufener
  // Sitzung wird sie gesichert statt kassiert.
  useEffect(() => entwurfMelden(`thema-${topic.id}`, () => description), [topic.id, description]);
  const [check, setCheck] = useState<Described | null>(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Bei jeder Änderung neu prüfen — aber erst, wenn das Tippen kurz ruht.
  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      setChecking(true);
      api.post<Described>("/topics/describe", { name: name.trim() || topic.name, description })
        .then(setCheck)
        .catch(() => setCheck(null))
        .finally(() => setChecking(false));
    }, 900);
    return () => { if (debounce.current) clearTimeout(debounce.current); };
  }, [topic.name, name, description]);

  const regenerate = async () => {
    setChecking(true);
    try {
      const d = await api.post<Described>("/topics/describe", { name: name.trim() || topic.name });
      if (d.description) setDescription(d.description);
      setCheck(d);
    } catch { /* Fehlschlag ändert nichts — der alte Text bleibt stehen */ }
    setChecking(false);
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/topics/${topic.id}`, { name: name.trim(), description: description.trim() });
      onSaved();
    } catch {
      setSaving(false);
    }
  };

  // Solange das Sheet offen ist, darf die Seite darunter nicht mitscrollen —
  // sonst wandert der Onboarding-Schritt hinter dem Sheet weg (Muster aus
  // council-map.tsx). Das Sheet selbst scrollt weiter, `overscroll-contain`
  // verhindert nur, dass sein Scroll-Ende auf die Seite durchschlägt.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Esc schließt — was `aria-modal` verspricht, muss die Tastatur auch halten:
  // Wer keine Maus hat, kam sonst nur über die Tab-Reise bis zum Kreuz wieder
  // heraus. Nur der oberste Dialog reagiert (das Blatt ist immer der oberste,
  // es hängt als letztes Kind an <body>).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Direkt an <body> hängen. `position: fixed` bezieht sich sonst nicht auf das
  // Fenster, sondern auf den nächsten Vorfahren mit `transform` — und genau so
  // einer steht auf der Themen-Seite im Weg (`.animate-fade-up`). Das Blatt saß
  // dadurch mitten in der Seite statt am unteren Bildrand, und der abdunkelnde
  // Hintergrund deckte nur die Inhaltsspalte ab. Gemessen: Hülle 976×1253 an
  // (272|32) statt 1280×720 an (0|0).
  const [amBody, setAmBody] = useState(false);
  useEffect(() => setAmBody(true), []);
  if (!amBody) return null;

  return createPortal(
    // data-topic-sheet: Kennzeichen für den Fokus-Wächter des Onboardings —
    // es erkennt daran, dass dieses Blatt dazugehört, obwohl es an <body> hängt.
    //
    // Ab sm ist das hier ein Dialog in der Bildmitte — und der muss die
    // App-Hülle erkennbar frei lassen, statt sie zu streifen: Auf dem iPad quer
    // (1180×820) ragte das Blatt mit `max-h-[92%]` 3 px in die Kopfzeile und
    // 6 px in die Tab-Leiste, auf dem Gerät mehr, weil die Sicherheitszonen
    // beide Leisten höher machen — „irgendwie ist dieses Fenster weird und
    // überlappt die Nav und Header" (Tim, 16.08.).
    // Statt einer kleineren Prozentzahl steht der Abstand deshalb dort, wo er
    // herkommt: Kopfzeile und Tab-Leiste sind je rund 61 px PLUS ihrer
    // Sicherheitszone hoch (components/nav.tsx). 5 rem + dieselbe Zone lassen
    // darüber 16–19 px Luft — und zwar auf jedem Gerät, weil die Zone in beiden
    // Rechnungen steht. Die Karte füllt den so gepolsterten Kasten dann ganz
    // aus (`sm:max-h-full`); mehr Platz gibt es nicht, ohne die Navigation zu
    // berühren. Ist der Inhalt höher, scrollt die Mitte (s. u.).
    // Auf dem Telefon bleibt es ein Blatt an der Unterkante: Dort DECKT es die
    // Tab-Leiste bewusst ab, wie jedes iOS-Sheet.
    <div data-topic-sheet role="dialog" aria-modal="true" aria-labelledby="thema-anpassen-titel"
      className="fixed inset-0 z-[var(--level-dialog)] flex flex-col justify-end sm:items-center sm:justify-center sm:px-6 sm:pb-[calc(env(safe-area-inset-bottom)+5rem)] sm:pt-[calc(env(safe-area-inset-top)+5rem)]">
      {/* .scrim statt einer eigenen Farbe — s. app/globals.css: Der frühere Ton
          war exakt die dunkle Seitenfarbe und dunkelte im Dunkelmodus nichts ab. */}
      <button type="button" aria-label="Schließen" onClick={onClose}
        className="scrim absolute inset-0 touch-none" />
      {/* Kopf und Fußzeile bleiben stehen, nur die Mitte scrollt: Vorher scrollte
          der ganze Inhalt samt „Speichern" weg, sodass man für die Knöpfe erst
          ans Ende wischen musste. Zusammen mit der höheren Textarea passt die
          Beschreibung jetzt meist ohne Scrollen hinein. */}
      <div className="relative flex max-h-[92%] w-full flex-col rounded-t-[22px] bg-card pt-2.5 shadow-[0_-12px_40px_-14px_rgba(2,32,71,0.4)] sm:max-h-full sm:max-w-lg sm:rounded-[22px] sm:shadow-[0_24px_60px_-20px_rgba(2,32,71,0.45)]">
        <div className="shrink-0 px-[18px]">
          {/* Ziehgriff nur auf dem Telefon — auf dem Desktop ist es ein Dialog. */}
          <span aria-hidden className="mx-auto mb-3.5 block h-1 w-9 rounded-full bg-border sm:hidden" />
          <div className="flex items-center gap-2.5">
            <h3 id="thema-anpassen-titel" className="flex-1 font-display text-lg font-bold text-foreground">Thema anpassen</h3>
            <button type="button" onClick={onClose} aria-label="Schließen"
              className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-muted text-muted-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* pb: Der letzte Block (》Passt gerade auf《 bzw. die Vagheits-Warnung)
            klebte sonst direkt an der Knopfleiste — im Bild vom 15.08. sitzt
            der Kasten mit einem Haar Abstand auf der Trennlinie. */}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-[18px] pb-4">

        <p className="mb-1.5 mt-4 text-xs font-semibold text-muted-foreground">Name</p>
        {nameEditable ? (
          /* text-base aus demselben Grund wie unten bei der Beschreibung:
             unter 16 px zoomt iOS/WKWebView beim Antippen hinein — und zwar
             nicht nur „auf dem Telefon", sondern auf jedem Touch-Gerät. Ein
             iPad ist fast immer ≥640px breit UND ein Touch-Gerät: `sm:`
             (Breite) griff dort also gar nicht; `maus:` (pointer:fine) ist
             die richtige Bedingung (Tims Befund 19.08.). */
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} aria-label="Name"
            className="h-[46px] w-full rounded-xl border-[1.5px] border-primary bg-card px-3.5 text-base font-medium text-foreground outline-none maus:text-[15px]" />
        ) : (
          <div className="flex h-[46px] items-center rounded-xl border border-border bg-card px-3.5 text-[15px] font-medium text-foreground">
            {topic.name}
          </div>
        )}

        <div className="mb-1.5 mt-4 flex items-center justify-between">
          <p className="text-xs font-semibold text-muted-foreground">Beschreibung</p>
          <button type="button" onClick={regenerate} disabled={checking}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-signal disabled:opacity-50">
            <Sparkles className="h-3 w-3" /> Neu generieren
          </button>
        </div>
        {/* Die generierten Beschreibungen sind regelmäßig 5–7 Zeilen lang; mit
            rows={3} war der Text im eigenen Feld abgeschnitten.

            text-base auf dem Telefon (16 px): Darunter zoomt iOS beim Antippen
            in das Feld hinein und der Rest des Blattes rutscht aus dem Bild.
            Ab sm wieder die kompakten 13 px — dasselbe Muster wie in
            components/ui/input.tsx. */}
        <textarea value={description} onChange={(e) => setDescription(e.target.value)}
          rows={6} aria-label="Beschreibung"
          className="w-full rounded-xl border-[1.5px] border-primary bg-card px-3.5 py-3 text-base leading-relaxed text-foreground outline-none maus:text-[13px]" />

        <div className="mt-3.5 rounded-xl bg-muted/60 px-3.5 py-3">
          {/* „auf den Text im Feld": Dieselbe Definition wie die Themen-Karte,
              aber live auf den ungespeicherten Text — die Karte zeigt den Stand
              des letzten Abgleichs. Zwei Zahlen, die auseinandergehen dürfen,
              brauchen zwei Beschriftungen (Tims Befund 16.08.: Karte „40+",
              Blatt „12" beim selben Thema — die 12 war damals nichts weiter
              als die Länge des Prompt-Kontexts). */}
          <p className="text-[11px] font-semibold uppercase tracking-[0.05em] text-muted-foreground">
            Passt auf den Text im Feld
          </p>
          {/* Während der Prüfung Platzhalterzeilen statt Spinner + „prüft…":
              Der Block behält seine Höhe (kein Springen, wenn das Ergebnis
              eintrifft), und die Andeutung zeigt, dass hier gleich Text steht. */}
          {checking ? (
            <div className="mt-1.5 space-y-1.5" role="status" aria-label="Treffer werden geprüft">
              <Skeleton className="h-[11px] w-4/5" />
              <Skeleton className="h-[11px] w-3/5" />
            </div>
          ) : (
            <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
              {!check ? "—" : check.matches > 0 ? (
                <>
                  <strong className="font-semibold text-foreground">
                    {check.matches}{check.matches_capped ? "+" : ""}{" "}
                    {check.matches === 1 && !check.matches_capped ? "Beschluss" : "Beschlüsse"}
                  </strong>
                  {check.examples.length > 0 && <> — u. a. „{check.examples.slice(0, 2).join("“, „")}“.</>}
                </>
              ) : (
                /* Keine Zahl behaupten, wo keine Belege sind: Vorher stand hier
                   „12 Beschlüsse — u. a. Grundschule Auf der Wunderburg“ unter
                   einem Thema namens „Grundschule Krusenbusch“. */
                <>Noch nichts — der Rat hat dazu bisher nicht entschieden. Sobald das
                passiert, meldet sich Lotti.</>
              )}
            </p>
          )}
        </div>

        {check?.vague && (
          <div className="mt-3 rounded-xl border border-amber-500/35 bg-amber-500/[0.06] px-3.5 py-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-px h-[15px] w-[15px] shrink-0 text-amber-700 dark:text-amber-500" />
              <div className="min-w-0">
                <p className="text-[12.5px] leading-relaxed text-amber-900 dark:text-amber-200">
                  {check.hint || "Das ist recht weit gefasst — enger fassen?"}
                </p>
                {check.suggestion && (
                  <button type="button" onClick={() => setDescription(check.suggestion)}
                    className="mt-1.5 inline-flex items-start gap-1.5 rounded-[9px] border border-amber-500/40 bg-card px-2.5 py-1.5 text-left text-xs text-amber-900 dark:text-amber-200">
                    <Check className="mt-0.5 h-[11px] w-[11px] shrink-0" />
                    <span>Vorschlag übernehmen: „{check.suggestion}“</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        </div>

        {/* Die Sicherheitszone gehört nur ins Blatt an der Unterkante — dort
            reicht die Karte bis an den Bildrand. Ab sm schwebt sie frei, und der
            Rahmen darum hält den Abstand zur Zone schon ein: Ohne das `sm:`
            stünde sie zweimal drin und ließe auf dem iPad ~20 pt tote Fläche
            unter den Knöpfen. */}
        <div className="shrink-0 flex gap-2.5 border-t border-border/60 px-[18px] pb-[calc(1.125rem+env(safe-area-inset-bottom))] pt-3.5 sm:pb-[1.125rem]">
          <button type="button" onClick={onClose}
            className="h-[46px] flex-1 rounded-xl border border-border bg-card text-sm font-medium text-foreground">
            Abbrechen
          </button>
          <Button className="h-[46px] flex-1" onClick={save} disabled={saving || !name.trim() || !description.trim()}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : check?.vague ? "Trotzdem speichern" : "Speichern"}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
