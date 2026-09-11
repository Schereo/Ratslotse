"use client";

// 1h — Tippspiel-Verwaltung: Ratswahl-Sitze und OB-Prozente eintragen,
// Entwurf vs. veröffentlicht, Phase steuern, Teilnehmer moderieren.
//
// Steht AUSSERHALB des Feature-Schalters `tippspiel` (kein `_frei()` in den
// Backend-Routen) — Tim soll das Spiel vorbereiten können, bevor es live
// geht. Die Rechteprüfung (`require_admin`) sitzt trotzdem im Backend; hier
// nur die Höflichkeit, nicht schon eine leere Seite zu zeigen.

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { darfAdmin } from "@/lib/rechte";
import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { BrandMark } from "@/components/brand";
import { Badge, Button, Input, Segmented, Spinner } from "@/components/ui";

type AdminStand = ApiAntwort<"/tipp/admin/stand">;
type Ansicht = "vergleich" | "rangliste";

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

function Kachel({ kicker, titel, aktion, children }: {
  kicker: string; titel?: string; aktion?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4.5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">{kicker}</p>
          {titel && <h2 className="mt-1 font-display text-xl">{titel}</h2>}
        </div>
        {aktion}
      </div>
      {children}
    </div>
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

  const standQuery = useQuery({ queryKey: ["tipp", "admin-stand"], queryFn: holeAdminStand, enabled: erlaubt });

  const [seatsEntwurf, setSeatsEntwurf] = useState<Record<string, string>>({});
  const [obEntwurf, setObEntwurf] = useState<Record<string, string>>({});
  const [ansicht, setAnsicht] = useState<Ansicht>("vergleich");
  const [endstandBestaetigen, setEndstandBestaetigen] = useState(false);
  const [meldung, setMeldung] = useState<string | null>(null);

  useEffect(() => {
    if (!standQuery.data) return;
    const seats: Record<string, string> = {};
    const ob: Record<string, string> = {};
    for (const r of standQuery.data.results) {
      if (r.slug.startsWith("ob:")) ob[r.slug.slice(3)] = r.pct !== null ? String(r.pct) : "";
      else seats[r.slug] = r.seats !== null ? String(r.seats) : "";
    }
    setSeatsEntwurf(seats);
    setObEntwurf(ob);
  }, [standQuery.data]);

  async function aktion<T>(fn: () => Promise<T>, erfolgstext?: string) {
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["tipp"] });
      if (erfolgstext) { setMeldung(erfolgstext); setTimeout(() => setMeldung(null), 3000); }
    } catch {
      setMeldung("Das hat nicht geklappt — bitte noch einmal versuchen.");
    }
  }

  async function eintragenSenden() {
    // Nur die Zeilen, die sich gegenüber dem Entwurf vom Server unterscheiden.
    // Jede Zeile, die hier ankommt, wird zur HANDEINGABE (`source = manuell`)
    // — und eine veröffentlichte Handeingabe schlägt den Wahlabend für genau
    // diese Liste. Alle 25 Felder zu schicken hieße: Ein einziger korrigierter
    // Tippfehler friert alle anderen Listen auf dem Stand von jetzt ein.
    const bisher = standQuery.data?.results ?? [];
    const seatsVorher = Object.fromEntries(bisher.filter((r) => !r.slug.startsWith("ob:")).map((r) => [r.slug, r.seats]));
    const obVorher = Object.fromEntries(bisher.filter((r) => r.slug.startsWith("ob:")).map((r) => [r.slug.slice(3), r.pct]));
    const zeilen = [
      ...Object.entries(seatsEntwurf)
        .filter(([slug, v]) => v !== "" && Number(v) !== seatsVorher[slug])
        .map(([slug, v]) => ({ slug, seats: Number(v) })),
      ...Object.entries(obEntwurf)
        .filter(([slug, v]) => v !== "" && Number(v) !== obVorher[slug])
        .map(([slug, v]) => ({ slug: `ob:${slug}`, pct: Number(v) })),
    ];
    if (zeilen.length === 0) {
      setMeldung("Nichts geändert.");
      setTimeout(() => setMeldung(null), 3000);
      return;
    }
    await aktion(() => api.put("/tipp/admin/ergebnis", zeilen), `${zeilen.length} Zeile${zeilen.length === 1 ? "" : "n"} in den Entwurf übernommen.`);
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

  const entwurfSumme = Object.values(seatsEntwurf).reduce((s, v) => s + (Number(v) || 0), 0);
  const obSumme = Object.values(obEntwurf).reduce((s, v) => s + (Number(v) || 0), 0);
  const nachgetippt = stand.players.filter((p) => p.late_at && !p.hidden).length;
  // „N Tipps" zählt Tipps, nicht Beitritte: `player_count` zählt jeden, der
  // seinen Namen eingegeben hat — auch ohne Tipp, auch ausgeblendet.
  const tipps = stand.players.filter((p) => p.has_tip && !p.hidden).length;

  const phaseSchritte: { title: string; erledigt: boolean; aktiv?: boolean; rechts: string }[] = [
    { title: "Tippen offen", erledigt: stand.game.phase !== "open" || false, aktiv: stand.game.phase === "open", rechts: stand.game.phase === "open" ? "läuft" : "" },
    { title: "Tipp-Schluss", erledigt: stand.game.phase !== "open",
      rechts: stand.game.locked_at ? `${uhrzeitKurz(stand.game.locked_at)} Uhr` : "" },
    { title: "Live · Hochrechnungen", erledigt: stand.game.phase === "final", aktiv: stand.game.phase === "locked",
      rechts: stand.game.phase === "final" ? "abgeschlossen" : "" },
    { title: "Endergebnis", erledigt: stand.game.phase === "final", rechts: "" },
  ];

  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      {/* Volle Breite nur fürs Band (Rand/Hintergrund) — der Inhalt bleibt wie
          im Rest der App (Wahlabend, (app)-Layout) auf `max-w-7xl` begrenzt
          und zentriert. Ohne das lief die Seite auf einem breiten Schirm bis
          an beide Ränder, mit nur den paar Pixeln `px-8` dazwischen (Tims
          Befund: „bis zum Rand gar kein Platz"). */}
      <div className="border-b border-border bg-card">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <BrandMark className="h-7 w-7" />
            <span className="font-display text-[17px] font-bold">Ratslotse</span>
            <span className="text-[13px] text-muted-foreground">
              <span className="font-medium text-primary">Tippspiel</span> / Verwaltung
            </span>
          </div>
          <div className="flex items-center gap-2.5 text-[12.5px]">
            <Badge color="green">{tipps} {tipps === 1 ? "Tipp" : "Tipps"}</Badge>
            {nachgetippt > 0 && <Badge color="amber">{nachgetippt} nachgetippt</Badge>}
            {meldung && <span className="text-muted-foreground">{meldung}</span>}
          </div>
        </div>
      </div>

      <div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_400px] lg:px-8">
        <div className="flex flex-col gap-5">
          <Kachel
            kicker="Ratswahl · Sitze" titel="Hochrechnung eintragen"
            aktion={<Button variant="secondary" size="sm" onClick={() => void aktion(() => api.post("/tipp/admin/abfragen"), "Votemanager abgefragt.")}>
              Jetzt abfragen
            </Button>}
          >
            <div className="mt-3.5 grid grid-cols-[1fr_70px_110px_120px] gap-2.5 border-b border-muted pb-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              <span>Liste</span><span className="text-right">Sitze</span><span>Quelle</span><span>Ø-Tipp · exakt</span>
            </div>
            {ratswahlZeilen.map((r) => {
              const p = parteiVon[r.slug];
              return (
                <div key={r.slug} className="grid grid-cols-[1fr_70px_110px_120px] items-center gap-2.5 border-b border-muted py-1.5 text-[13px]">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full" style={{ background: p?.color }} />
                    <span className="font-semibold">{p?.short ?? r.slug}</span>
                  </div>
                  <Input
                    type="number" inputMode="numeric" aria-label={`Sitze für ${p?.short}`}
                    value={seatsEntwurf[r.slug] ?? ""}
                    onChange={(e) => setSeatsEntwurf((s) => ({ ...s, [r.slug]: e.target.value }))}
                    className="h-[34px] appearance-none px-2 text-right font-display text-sm font-bold [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <span>
                    {r.published_source && (
                      <Badge color={r.published_source === "votemanager" ? "blue" : "slate"}>{r.published_source}</Badge>
                    )}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {r.avg_tip !== null ? r.avg_tip.toFixed(1) : "–"} · {r.exact_count}
                  </span>
                </div>
              );
            })}
            <div className="mt-3 flex items-center justify-between">
              <span className={`text-[13px] font-semibold ${entwurfSumme === setup.seats_total ? "text-emerald-600 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>
                {entwurfSumme} von {setup.seats_total} Sitzen im Entwurf
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => void aktion(() => api.post("/tipp/admin/verwerfen"), "Entwurf verworfen.")}>
                  Entwurf verwerfen
                </Button>
                <Button variant="primary" size="sm" onClick={eintragenSenden}>Eintragen</Button>
                <Button variant="signal" size="sm" onClick={() => void aktion(() => api.post("/tipp/admin/veroeffentlichen"), "Veröffentlicht.")}>
                  Veröffentlichen → Live
                </Button>
              </div>
            </div>
          </Kachel>

          <Kachel kicker="OB-Wahl · Prozent">
            <div className="mt-3 grid grid-cols-1 gap-x-4.5 gap-y-1.5 sm:grid-cols-3">
              {obZeilen.map((r) => {
                const slug = r.slug.slice(3);
                const kandidatur = setup.mayor_candidates.find((c) => c.slug === slug);
                return (
                  <div key={r.slug} className="flex items-center justify-between gap-2.5 border-b border-muted py-1.5 text-[13px]">
                    <span className="truncate font-semibold" title={kandidatur?.name ?? slug}>{kandidatur?.name ?? slug}</span>
                    <div className="flex items-center gap-1">
                      <Input
                        type="number" inputMode="decimal" step={0.5} aria-label={`Prozent für ${kandidatur?.name}`}
                        value={obEntwurf[slug] ?? ""}
                        onChange={(e) => setObEntwurf((s) => ({ ...s, [slug]: e.target.value })) }
                        className="h-8 w-[62px] appearance-none px-2 text-right text-[13px] font-bold [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                      />
                      <span className="text-xs text-muted-foreground">%</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-2.5 text-xs text-muted-foreground">
              Summe im Entwurf {obSumme.toFixed(1).replace(".", ",")} %. Stichwahl 27.09. ist kein Teil des Tippspiels.
            </p>
          </Kachel>
        </div>

        <div className="flex flex-col gap-5">
          <Kachel kicker="Phase">
            <div className="mt-2.5 flex flex-col gap-1.5 text-[13px]">
              {phaseSchritte.map((s) => (
                <div key={s.title} className={`flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 ${s.aktiv ? "border border-primary/30 bg-primary/5" : "bg-muted/60"}`}>
                  <span className={`flex h-[18px] w-[18px] flex-none items-center justify-center rounded-full text-[11px] ${
                    s.erledigt ? "bg-emerald-600 text-white" : s.aktiv ? "border-2 border-primary" : "border-2 border-dotted border-muted-foreground"
                  }`}>
                    {s.erledigt ? "✓" : ""}
                  </span>
                  <span className={s.aktiv ? "font-semibold" : ""}>{s.title}</span>
                  {s.rechts && <span className="ml-auto font-mono text-[11px] text-muted-foreground">{s.rechts}</span>}
                </div>
              ))}
            </div>
            {stand.game.phase !== "open" && stand.game.phase !== "final" && (
              endstandBestaetigen ? (
                <div className="mt-3 flex items-center gap-2 text-[12.5px]">
                  <span>Endstand jetzt einfrieren?</span>
                  <Button size="sm" variant="signal" onClick={() => { void aktion(() => api.put("/tipp/admin/phase", { phase: "final" }), "Endstand gesetzt."); setEndstandBestaetigen(false); }}>Ja</Button>
                  <Button size="sm" variant="secondary" onClick={() => setEndstandBestaetigen(false)}>Abbrechen</Button>
                </div>
              ) : (
                <Button size="sm" variant="secondary" className="mt-3" onClick={() => setEndstandBestaetigen(true)}>Endstand setzen</Button>
              )
            )}
            {stand.game.phase === "open" && (
              <Button size="sm" variant="secondary" className="mt-3"
                onClick={() => void aktion(() => api.put("/tipp/admin/phase", { phase: "locked" }), "Tippen geschlossen.")}>
                Tippen jetzt schließen
              </Button>
            )}
          </Kachel>

          <Kachel kicker="Beamer">
            <div className="mt-2.5">
              <Segmented value={ansicht} onChange={setAnsicht} options={[
                { value: "vergleich", label: "Vergleich" },
                { value: "rangliste", label: "Rangliste" },
              ]} />
            </div>
            <Button asChild variant="secondary" size="sm" className="mt-3 w-full">
              <a href={`/tipp/live?ansicht=${ansicht}`} target="_blank" rel="noreferrer">Beamer in diesem Modus öffnen</a>
            </Button>
          </Kachel>

          <Kachel kicker="Teilnehmer">
            <div className="mt-2.5 flex max-h-72 flex-col gap-1 overflow-y-auto text-[13px]">
              {stand.players.map((p) => (
                <div key={p.id} className="flex items-center justify-between gap-2 border-b border-muted py-1.5">
                  <div className="min-w-0">
                    <span className={`truncate ${p.hidden ? "text-muted-foreground line-through" : ""}`} title={p.name}>{p.name}</span>
                    {p.late_at && <span className="ml-1.5 text-[10px] text-amber-700 dark:text-amber-400">nachgetippt</span>}
                  </div>
                  <div className="flex flex-none gap-1">
                    <button type="button"
                      className="rounded-md border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                      onClick={() => {
                        const neuerName = window.prompt("Neuer Name", p.name);
                        if (neuerName && neuerName.trim()) void aktion(() => api.put(`/tipp/admin/spieler/${p.id}`, { name: neuerName.trim() }));
                      }}>
                      Umbenennen
                    </button>
                    <button type="button"
                      className="rounded-md border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                      onClick={() => void aktion(() => api.put(`/tipp/admin/spieler/${p.id}`, { hidden: !p.hidden }))}>
                      {p.hidden ? "Einblenden" : "Ausblenden"}
                    </button>
                  </div>
                </div>
              ))}
              {stand.players.length === 0 && <p className="text-muted-foreground">Noch niemand beigetreten.</p>}
            </div>
          </Kachel>

          <Kachel kicker="Protokoll">
            <div className="mt-2 flex flex-col gap-1 text-[12.5px] text-muted-foreground">
              {stand.log.length === 0 && <span>Noch nichts protokolliert.</span>}
              {stand.log.map((zeile, i) => <span key={i}>{zeile}</span>)}
            </div>
          </Kachel>
        </div>
      </div>
    </div>
  );
}
