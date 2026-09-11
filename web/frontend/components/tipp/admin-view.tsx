"use client";

// 1h — Tippspiel-Verwaltung: Ratswahl-Sitze und OB-Prozente eintragen,
// Entwurf vs. veröffentlicht, Phase steuern, Beamer wählen, Teilnehmer
// moderieren. Gebaut gegen das Artboard 1h (Desktop 1280): Kopfband,
// links die beiden Eingabe-Karten, rechts Phase / Beamer / Protokoll.
//
// Steht AUSSERHALB des Feature-Schalters `tippspiel` (kein `_frei()` in den
// Backend-Routen) — Tim soll das Spiel vorbereiten können, bevor es live
// geht. Die Rechteprüfung (`require_admin`) sitzt trotzdem im Backend; hier
// nur die Höflichkeit, nicht schon eine leere Seite zu zeigen.
//
// **Die Felder SIND der Entwurf.** Wie im Artboard gibt es keinen
// „Eintragen"-Knopf: Ein Feld verlassen (oder Enter) speichert genau diese
// Zeile als Handeingabe — und nur, wenn sich der Wert geändert hat, denn eine
// veröffentlichte Handeingabe schlägt den Wahlabend für diese Liste
// (prediction/service.py). „Veröffentlichen → Live" bleibt der eine Schritt,
// an dem etwas auf den Beamer kommt.

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { darfAdmin } from "@/lib/rechte";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/brand";
import { Button, Segmented, Spinner } from "@/components/ui";

type AdminStand = ApiAntwort<"/tipp/admin/stand">;
type Ergebnis = AdminStand["results"][number];
type Beamer = "auto" | "vergleich" | "rangliste";

async function holeAdminStand(): Promise<AdminStand> {
  return api.get<AdminStand>("/tipp/admin/stand");
}

/** „HH:MM" aus einem ISO-Zeitstempel, deutsche Zeit. Bewusst hier lokal
 *  gehalten statt aus `lib/tipp.ts` (Handy-Screens, ein anderer PR desselben
 *  Plans) — diese Seite soll unabhängig davon fertig werden. */
function uhrzeitKurz(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
}

function dezimal(n: number): string {
  return n.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function Kicker({ children }: { children: React.ReactNode }) {
  return <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">{children}</p>;
}

function Karte({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("rounded-2xl border border-border bg-card px-5 py-[18px]", className)}>{children}</div>;
}

/** Ein Sitz- oder Prozentfeld: speichert beim Verlassen, wenn sich der Wert
 *  gegenüber dem Entwurf des Servers geändert hat. Handeingaben stehen auf
 *  Warn-Tönung (Artboard: „manuell" gelb), damit man sieht, welche Liste der
 *  Wahlabend nicht mehr überschreibt. */
function Feld({ wert, manuell, label, breit, dezimalstellen, onSpeichern }: {
  wert: number | null; manuell: boolean; label: string; breit?: boolean; dezimalstellen?: boolean;
  onSpeichern: (neu: number) => void;
}) {
  const [text, setText] = useState(wert !== null ? String(wert) : "");
  useEffect(() => { setText(wert !== null ? String(wert) : ""); }, [wert]);
  function abgeben() {
    if (text.trim() === "") return;
    const neu = Number(text.replace(",", "."));
    if (!Number.isFinite(neu) || neu === wert) return;
    onSpeichern(neu);
  }
  return (
    <input
      type="number" inputMode={dezimalstellen ? "decimal" : "numeric"} step={dezimalstellen ? 0.1 : 1} min={0}
      aria-label={label} value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={abgeben}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
      className={cn(
        "h-[34px] appearance-none rounded-lg border px-2 text-right font-display text-sm font-bold text-foreground",
        "transition-[border-color,box-shadow,background-color] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        "[&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none",
        manuell ? "border-amber-200 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10" : "border-input bg-card",
        breit ? "w-[62px]" : "w-full",
      )}
    />
  );
}

function Quelle({ r }: { r: Ergebnis }) {
  const wert = r.seats ?? r.pct;
  if (wert === null) return <span />;
  const manuell = r.source === "manuell";
  return (
    <span className={cn(
      "w-max rounded-full px-2 py-0.5 text-[11px] font-semibold",
      manuell ? "bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200" : "bg-muted text-muted-foreground",
    )}>
      {manuell ? "manuell" : r.source}
    </span>
  );
}

function NichtErlaubt() {
  return (
    <div className="mx-auto max-w-sm px-6 py-24 text-center">
      <p className="font-display text-xl font-bold">Adminrechte erforderlich</p>
      <p className="mt-2 text-sm text-muted-foreground">Diese Seite gehört zur Verwaltung des Tippspiels.</p>
    </div>
  );
}

export function TippAdminView() {
  const { user, loading: authLaedt } = useAuth();
  const qc = useQueryClient();
  const erlaubt = darfAdmin(user);

  const standQuery = useQuery({ queryKey: ["tipp", "admin-stand"], queryFn: holeAdminStand, enabled: erlaubt, refetchInterval: 30_000 });

  const [beamer, setBeamer] = useState<Beamer>("auto");
  const [endstandBestaetigen, setEndstandBestaetigen] = useState(false);
  const [meldung, setMeldung] = useState<{ text: string; ton: "ok" | "fehler" } | null>(null);
  const [laeuft, setLaeuft] = useState<string | null>(null);

  /** Eine Admin-Aktion mit sichtbarem Zustand: der Knopf zeigt `laeuft`,
   *  danach eine kurze Meldung — Tim soll sehen, dass der Klick ankam. */
  async function aktion(schluessel: string, fn: () => Promise<unknown>, erfolgstext?: string) {
    setLaeuft(schluessel);
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["tipp"] });
      if (erfolgstext) {
        setMeldung({ text: erfolgstext, ton: "ok" });
        setTimeout(() => setMeldung(null), 3500);
      }
    } catch {
      setMeldung({ text: "Das hat nicht geklappt — bitte noch einmal versuchen.", ton: "fehler" });
    } finally {
      setLaeuft(null);
    }
  }

  if (authLaedt) return <Spinner />;
  if (!user || !erlaubt) return <NichtErlaubt />;
  if (!standQuery.data) return <Spinner />;

  const stand = standQuery.data;
  // Parteien/OB-Kandidaten kommen aus `stand.game` (= dasselbe `PredictionGame`
  // wie `/tipp/setup`), nicht aus einem eigenen Aufruf von `/tipp/setup`: Der
  // öffentliche Endpunkt steht hinter dem Feature-Schalter `tippspiel` und
  // würde vor dessen Freischaltung 404 liefern — genau in der Phase, in der
  // Tim hier vorbereiten soll (s. Moduldoc in routers/tippspiel.py).
  const setup = stand.game;
  const parteiVon = Object.fromEntries(setup.parties.map((p) => [p.slug, p]));
  const ratswahlZeilen = stand.results.filter((r) => !r.slug.startsWith("ob:"));
  const obZeilen = stand.results.filter((r) => r.slug.startsWith("ob:"));

  const entwurfSumme = ratswahlZeilen.reduce((s, r) => s + (r.seats ?? 0), 0);
  const entwurfVoll = entwurfSumme === setup.seats_total;
  const obSumme = obZeilen.reduce((s, r) => s + (r.pct ?? 0), 0);
  const veroeffentlichtAm = ratswahlZeilen.map((r) => r.published_at).filter(Boolean).sort().at(-1) ?? null;
  const entwurfIstLive = ratswahlZeilen.every((r) => r.seats === r.published_seats) && obZeilen.every((r) => r.pct === r.published_pct);
  // „N Tipps" zählt Tipps, nicht Beitritte: `player_count` zählt jeden, der
  // seinen Namen eingegeben hat — auch ohne Tipp, auch ausgeblendet.
  const tipps = stand.players.filter((p) => p.has_tip && !p.hidden).length;
  const nachgetippt = stand.players.filter((p) => p.late_at && !p.hidden).length;
  const phase = setup.phase;
  const schluss = uhrzeitKurz(setup.locked_at);

  function speichern(slug: string, feld: "seats" | "pct", neu: number) {
    void aktion(`feld:${slug}`, () => api.put("/tipp/admin/ergebnis", [{ slug, [feld]: neu }]), "In den Entwurf übernommen.");
  }

  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      {/* Volle Breite nur fürs Band — der Inhalt bleibt wie im Rest der App
          auf `max-w-7xl` begrenzt und zentriert (Tims Befund: „bis zum Rand
          gar kein Platz"). */}
      <div className="border-b border-border bg-card">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3.5 sm:px-8">
          <div className="flex items-center gap-2.5">
            <BrandMark className="h-7 w-7" />
            <span className="font-display text-[17px] font-bold">Ratslotse</span>
            <span className="text-[13px] text-muted-foreground">
              <span className="font-medium text-primary">Tippspiel</span> / Verwaltung
            </span>
          </div>
          <div className="flex items-center gap-2.5 text-[12.5px]">
            {meldung && (
              <span className={cn(
                "animate-fade-up rounded-full px-3 py-1.5 font-semibold",
                meldung.ton === "ok" ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200" : "bg-destructive/10 text-destructive",
              )}>
                {meldung.text}
              </span>
            )}
            <span className="rounded-full border border-border px-3 py-1.5 text-muted-foreground">
              {tipps} {tipps === 1 ? "Tipp" : "Tipps"}{nachgetippt > 0 && ` · ${nachgetippt} nachgetippt`}
            </span>
          </div>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-6 px-4 py-6 sm:px-8 sm:pb-8 lg:grid-cols-[1fr_400px]">
        <div className="flex flex-col gap-5">
          {/* ── Ratswahl · Sitze ─────────────────────────────────────── */}
          <Karte>
            <div className="flex items-center justify-between gap-4">
              <div>
                <Kicker>Ratswahl · Sitze</Kicker>
                <h2 className="mt-1 font-display text-xl font-bold">Hochrechnung eintragen</h2>
              </div>
              <Button
                variant="secondary" size="sm" disabled={laeuft === "abfragen"}
                onClick={() => void aktion("abfragen", () => api.post("/tipp/admin/abfragen"), "Votemanager abgefragt — Zahlen im Entwurf.")}
              >
                {laeuft === "abfragen" ? "Fragt ab …" : "Jetzt abfragen"}
              </Button>
            </div>

            <div className="mt-3.5 grid grid-cols-[1fr_80px_120px_140px] gap-2.5 border-b border-muted px-1.5 pb-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              <span>Liste</span><span className="text-right">Sitze</span><span>Quelle</span><span>Ø-Tipp · exakt</span>
            </div>
            {ratswahlZeilen.map((r) => {
              const p = parteiVon[r.slug];
              return (
                <div key={r.slug} className="grid grid-cols-[1fr_80px_120px_140px] items-center gap-2.5 border-b border-muted px-1.5 py-1.5 text-[13px]">
                  <div className="flex items-center gap-2.5">
                    <span className="h-2 w-2 rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,0.15)]" style={{ background: p?.color }} />
                    <span className="font-semibold">{p?.short ?? r.slug}</span>
                  </div>
                  <Feld wert={r.seats} manuell={r.source === "manuell" && r.seats !== null} label={`Sitze für ${p?.short ?? r.slug}`}
                        onSpeichern={(neu) => speichern(r.slug, "seats", neu)} />
                  <Quelle r={r} />
                  <span className="font-mono text-xs text-muted-foreground">
                    Ø {r.avg_tip !== null ? dezimal(r.avg_tip) : "–"} · {r.exact_count} exakt
                  </span>
                </div>
              );
            })}

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className={cn("text-[13px] font-semibold", entwurfVoll ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400")}>
                Summe {entwurfSumme} von {setup.seats_total} Sitzen{entwurfVoll ? " ✓" : ""}
                {" · "}
                {entwurfIstLive
                  ? (veroeffentlichtAm ? `live seit ${uhrzeitKurz(veroeffentlichtAm)}` : "noch nichts veröffentlicht")
                  : "Entwurf, noch nicht live"}
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={laeuft === "verwerfen" || entwurfIstLive}
                        onClick={() => void aktion("verwerfen", () => api.post("/tipp/admin/verwerfen"), "Entwurf verworfen.")}>
                  {laeuft === "verwerfen" ? "Verwirft …" : "Entwurf verwerfen"}
                </Button>
                <Button variant="primary" size="sm" disabled={laeuft === "veroeffentlichen" || entwurfIstLive}
                        onClick={() => void aktion("veroeffentlichen", () => api.post("/tipp/admin/veroeffentlichen"), "Veröffentlicht — der Beamer zeigt den Stand.")}>
                  {laeuft === "veroeffentlichen" ? "Veröffentlicht …" : "Veröffentlichen → Live"}
                </Button>
              </div>
            </div>
          </Karte>

          {/* ── OB-Wahl · Prozent ────────────────────────────────────── */}
          <Karte>
            <Kicker>OB-Wahl · Prozent</Kicker>
            <div className="mt-2.5 grid grid-cols-1 gap-x-[18px] gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
              {obZeilen.map((r) => {
                const slug = r.slug.slice(3);
                const kandidatur = setup.mayor_candidates.find((c) => c.slug === slug);
                return (
                  <div key={r.slug} className="flex items-center justify-between gap-2.5 border-b border-muted py-1.5 text-[13px]">
                    <span className="truncate font-semibold" title={kandidatur?.name ?? slug}>{kandidatur?.name ?? slug}</span>
                    <div className="flex flex-none items-center gap-1">
                      <Feld wert={r.pct} manuell={r.source === "manuell" && r.pct !== null} label={`Prozent für ${kandidatur?.name ?? slug}`}
                            breit dezimalstellen onSpeichern={(neu) => speichern(r.slug, "pct", neu)} />
                      <span className="text-xs text-muted-foreground">%</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-2.5 text-xs text-muted-foreground">
              Summe {dezimal(obSumme)} %. Stichwahl 27.09. ist kein Teil des Tippspiels.
            </p>
          </Karte>
        </div>

        <div className="flex flex-col gap-5">
          {/* ── Phase ────────────────────────────────────────────────── */}
          <Karte>
            <Kicker>Phase</Kicker>
            <div className="mt-2.5 flex flex-col gap-1.5 text-[13px]">
              <PhaseZeile zustand={phase === "open" ? "aktiv" : "erledigt"} titel="Tippen offen"
                rechts={phase === "open"
                  ? <Button size="sm" variant="secondary" className="h-7 px-2.5 text-xs" disabled={laeuft === "schliessen"}
                            onClick={() => void aktion("schliessen", () => api.put("/tipp/admin/phase", { phase: "locked" }), "Tippen geschlossen.")}>
                      {laeuft === "schliessen" ? "Schließt …" : "Jetzt schließen"}
                    </Button>
                  : <span className="font-mono text-[11px] text-muted-foreground">{schluss ? `bis ${schluss}` : ""}</span>} />
              <PhaseZeile zustand={phase === "open" ? "offen" : "erledigt"} titel="Tipp-Schluss"
                rechts={<span className="font-mono text-[11px] text-muted-foreground">{schluss ? `${schluss} Uhr` : "mit der 1. Hochrechnung"}</span>} />
              <PhaseZeile zustand={phase === "locked" ? "aktiv" : phase === "final" ? "erledigt" : "offen"} titel="Live · Hochrechnungen"
                rechts={<span className="font-mono text-[11px] text-primary">{phase === "locked" && veroeffentlichtAm ? `Stand ${uhrzeitKurz(veroeffentlichtAm)}` : ""}</span>} />
              <PhaseZeile zustand={phase === "final" ? "aktiv" : "offen"} titel="Endergebnis"
                rechts={phase === "locked" && (
                  endstandBestaetigen ? (
                    <span className="flex items-center gap-1.5">
                      <Button size="sm" variant="signal" className="h-7 px-2.5 text-xs" disabled={laeuft === "final"}
                              onClick={() => { void aktion("final", () => api.put("/tipp/admin/phase", { phase: "final" }), "Endstand gesetzt."); setEndstandBestaetigen(false); }}>
                        Ja, einfrieren
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setEndstandBestaetigen(false)}>Abbrechen</Button>
                    </span>
                  ) : (
                    <Button size="sm" variant="secondary" className="h-7 px-2.5 text-xs" onClick={() => setEndstandBestaetigen(true)}>Endstand setzen</Button>
                  )
                )} />
            </div>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              Der Tipp-Schluss fällt von selbst mit der ersten Hochrechnung der Ratswahl. „Endstand setzen" fragt inline nach — kein Dialog.
            </p>
          </Karte>

          {/* ── Beamer ───────────────────────────────────────────────── */}
          <Karte>
            <Kicker>Beamer</Kicker>
            <div className="mt-2.5">
              <Segmented tone="primary" value={beamer} onChange={setBeamer} options={[
                { value: "auto", label: "Automatik 45 s" },
                { value: "vergleich", label: "Vergleich" },
                { value: "rangliste", label: "Rangliste" },
              ]} />
            </div>
            <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">Bei neuem Stand springt der Beamer für 60 s auf die Rangliste.</p>
            <Button asChild variant="secondary" size="sm" className="mt-3 w-full">
              <a href={beamer === "auto" ? "/tipp/live" : `/tipp/live?ansicht=${beamer}`} target="_blank" rel="noreferrer">
                Beamer öffnen <ExternalLink />
              </a>
            </Button>
          </Karte>

          {/* ── Teilnehmer ───────────────────────────────────────────── */}
          <Karte>
            <Kicker>Teilnehmer</Kicker>
            <div className="mt-2 flex max-h-72 flex-col overflow-y-auto text-[13px]">
              {stand.players.map((p) => (
                <div key={p.id} className="flex items-center justify-between gap-2 border-b border-muted py-1.5 last:border-b-0">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className={cn("truncate font-medium", p.hidden && "text-muted-foreground line-through")} title={p.name}>{p.name}</span>
                    {p.late_at && (
                      <span className="flex-none rounded-full border border-amber-200 px-1.5 font-mono text-[9px] uppercase tracking-[0.06em] text-amber-800 dark:border-amber-500/40 dark:text-amber-200">
                        nachgetippt {uhrzeitKurz(p.late_at)}
                      </span>
                    )}
                    {!p.has_tip && !p.hidden && <span className="flex-none text-[11px] text-muted-foreground">kein Tipp</span>}
                  </div>
                  <div className="flex flex-none gap-1">
                    <Button size="sm" variant="secondary" className="h-7 px-2 text-[11px]"
                      onClick={() => {
                        const neuerName = window.prompt("Neuer Name", p.name);
                        if (neuerName && neuerName.trim()) void aktion(`name:${p.id}`, () => api.put(`/tipp/admin/spieler/${p.id}`, { name: neuerName.trim() }), "Umbenannt.");
                      }}>
                      Umbenennen
                    </Button>
                    <Button size="sm" variant="secondary" className="h-7 px-2 text-[11px]" disabled={laeuft === `hide:${p.id}`}
                      onClick={() => void aktion(`hide:${p.id}`, () => api.put(`/tipp/admin/spieler/${p.id}`, { hidden: !p.hidden }), p.hidden ? "Wieder sichtbar." : "Ausgeblendet.")}>
                      {p.hidden ? "Einblenden" : "Ausblenden"}
                    </Button>
                  </div>
                </div>
              ))}
              {stand.players.length === 0 && <p className="text-muted-foreground">Noch niemand beigetreten.</p>}
            </div>
          </Karte>

          {/* ── Protokoll ────────────────────────────────────────────── */}
          <Karte>
            <Kicker>Protokoll</Kicker>
            <div className="mt-2 flex flex-col gap-1.5 text-[12.5px] text-muted-foreground tabular-nums">
              {stand.log.length === 0 && <span>Noch nichts protokolliert.</span>}
              {stand.log.map((zeile, i) => {
                const [zeit, ...rest] = zeile.split(" · ");
                return (
                  <span key={i}>
                    <span className="font-mono text-foreground">{zeit}</span> {rest.join(" · ")}
                  </span>
                );
              })}
            </div>
          </Karte>
        </div>
      </div>
    </div>
  );
}

function PhaseZeile({ zustand, titel, rechts }: { zustand: "erledigt" | "aktiv" | "offen"; titel: string; rechts?: React.ReactNode }) {
  return (
    <div className={cn(
      "flex min-h-[38px] items-center gap-2.5 rounded-[10px] px-2.5 py-1.5",
      zustand === "aktiv" && "border border-primary/30 bg-primary/5",
      zustand === "erledigt" && "bg-muted/60",
    )}>
      <span className={cn(
        "flex h-[18px] w-[18px] flex-none items-center justify-center rounded-full text-[11px]",
        zustand === "erledigt" && "bg-emerald-600 text-white",
        zustand === "aktiv" && "border-2 border-primary",
        zustand === "offen" && "border-2 border-dotted border-muted-foreground/60",
      )}>
        {zustand === "erledigt" ? "✓" : ""}
      </span>
      <span className={cn(zustand === "aktiv" && "font-semibold", zustand === "offen" && "text-muted-foreground")}>{titel}</span>
      <span className="ml-auto flex items-center">{rechts}</span>
    </div>
  );
}
