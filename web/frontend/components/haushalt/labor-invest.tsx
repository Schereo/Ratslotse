"use client";

// Werkbank 3 des Haushalts-Labors: Investitionen & Finanzierung (Labor 2.0,
// Entwurf „Werkbank Investitionen“).
//
// DIESE WERKBANK HAT ANDERE ZIELGRÖSSEN ALS DIE LÜCKE — und genau das ist
// ihre Lektion: Ein gestrichenes Vorhaben bewegt das Jahresergebnis fast
// nicht (dort landen nur die Abschreibungen), es schont die Kasse und den
// Schuldenpfad. Die Schalter hier rechnen deshalb NICHT in den Lücken-Balken
// der Ergebnis-Karte hinein; sie haben ihre eigene Bilanzzeile.
//
// EHRLICHKEITEN dieser Werkbank:
//  * Das Investitionsprogramm führt GESAMTKOSTEN über alle Jahre, keine
//    Jahresraten (die Aufteilung liegt nicht vor) — „gestrichen“ heißt also
//    „diese Gesamtkosten fallen über die kommenden Jahre weg“, nicht „dieses
//    Jahr wird um X entlastet“.
//  * Der Zinssatz des Kredit-Schalters ist KEINE Marktannahme: Er ist die
//    Spanne der Sätze, die die Stadt laut ihren eigenen Abschlüssen zuletzt
//    gezahlt hat (Zinsaufwand ÷ Schuldenstand, lib/haushalt-labor.ts).

import Link from "next/link";
import { Search } from "lucide-react";
import { deMio, type HaushaltssatzungZeile } from "@/lib/haushalt";
import type { ProgrammDaten } from "@/lib/haushalt-investitionsprogramm";
import type { SchuldenDaten } from "@/lib/haushalt-schulden";
import { gezahlteZinsspanne } from "@/lib/haushalt-labor";
import { Beleg } from "@/components/haushalt/quelle";
import { cn } from "@/lib/utils";

/** Wie viele Vorhaben die Liste zeigt — die größten; alles andere steht
 *  durchsuchbar auf der Investitionen-Seite. */
const ANZAHL = 6;

function Schalter({ an, onClick, label }: {
  an: boolean; onClick: () => void; label: string;
}) {
  return (
    <button type="button" role="switch" aria-checked={an} aria-label={label}
      onClick={onClick}
      className={cn(
        "relative h-5 w-[34px] shrink-0 rounded-full transition-colors",
        an ? "bg-primary" : "border border-border bg-muted",
      )}>
      <span className={cn(
        "absolute top-[2px] h-4 w-4 rounded-full bg-card shadow-[0_1px_2px_rgba(2,32,71,0.25)] transition-[left]",
        an ? "left-[16px]" : "left-[2px]",
      )} />
    </button>
  );
}

export function InvestWerkbank({
  programm, schulden, satzung, vorhabenAus, toggleVorhaben, kredit, setKredit,
  neuesDefizit,
}: {
  programm: ProgrammDaten | null;
  schulden: SchuldenDaten | null;
  satzung: HaushaltssatzungZeile[] | undefined;
  vorhabenAus: Record<string, boolean>;
  toggleVorhaben: (schluessel: string) => void;
  kredit: boolean;
  setKredit: (v: boolean) => void;
  /** Das Minus des Planjahres nach dem aktuellen Szenario, in Mio. € —
   *  der Betrag, um den es beim Kredit-Schalter geht. */
  neuesDefizit: number;
}) {
  const year = programm?.jahre.at(-1) ?? null;
  const vorhaben = year != null
    ? (programm?.massnahmen ?? [])
        .filter((z) => z.year === year && z.gesamtsumme > 0)
        .sort((a, b) => b.gesamtsumme - a.gesamtsumme)
        .slice(0, ANZAHL)
    : [];
  const schluessel = (z: { code: string; bezeichnung: string }) =>
    z.code || z.bezeichnung;
  /** Detailzeilen, die etwas SAGEN: Wiederholt ein Sachkonto nur den
   *  Maßnahmen-Namen (ggf. abgeschnitten), trägt es nichts — was bleibt,
   *  sind die informativen („Eig.kap. Zusch.Stadion Oldb GmbH & Co KG“,
   *  die Bauabschnitte der Fliegerhorst-Straßen). */
  const detailInfo = (z: { bezeichnung: string; details: string | null }) => {
    if (!z.details) return null;
    const eigene = z.details.split(" · ").filter((d) => {
      const stamm = d.split(",")[0].trim();
      return !(z.bezeichnung.startsWith(stamm) || stamm.startsWith(z.bezeichnung));
    });
    return eigene.length ? eigene.join(" · ") : null;
  };
  const gestrichen = vorhaben
    .filter((z) => vorhabenAus[schluessel(z)])
    .reduce((s, z) => s + z.gesamtsumme, 0);

  const schuldenLetzte = schulden?.reihe.length
    ? schulden.reihe[schulden.reihe.length - 1] : null;
  const zinsLetzte = schulden?.zinslast.length
    ? schulden.zinslast[schulden.zinslast.length - 1] : null;
  const spanne = gezahlteZinsspanne(schulden?.zinslast, schulden?.reihe ?? undefined);

  // § 2 der Satzung, aus den Daten statt behauptet: In wie vielen Jahrgängen
  // stand „nicht veranschlagt“ (= 0)?
  const satzSelbst = (satzung ?? []).filter((z) => z.nachtrag === 0);
  const ohneKredit = satzSelbst.filter((z) => z.kredite_investitionen === 0).length;
  const dispo = satzSelbst
    .filter((z) => z.liquiditaetskredite != null)
    .sort((a, b) => a.year - b.year)
    .at(-1);

  const zinsProzent = (v: number) =>
    (v * 100).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        {["Liquidität", "Schuldenstand"].map((z) => (
          <span key={z}
            className="rounded-full border border-primary/30 bg-primary/5 px-2.5 py-0.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-primary">
            Zielgröße · {z}
          </span>
        ))}
      </div>

      {vorhaben.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Vorhaben aus dem Investitionsprogramm {year}
            </p>
            <span className="font-mono text-[10.5px] text-muted-foreground">
              die {vorhaben.length} größten<Beleg q="investitionsprogramm" />
            </span>
          </div>
          <div className="mt-2 flex flex-col">
            {vorhaben.map((z) => {
              const aus = !!vorhabenAus[schluessel(z)];
              // Kein Vorhaben ohne Namen: Trägt die Summenzeile im Dokument
              // keinen (und die Detailzeilen keinen gemeinsamen), steht hier
              // der Code — eine benannte Lücke statt eines leeren Schalters.
              const name = z.bezeichnung || `Maßnahme ${z.code}`;
              return (
                <div key={schluessel(z)}
                  className="flex items-start gap-3 border-t border-border/60 py-2.5 first:border-t-0">
                  <div className="pt-0.5">
                    <Schalter an={!aus} label={name}
                      onClick={() => toggleVorhaben(schluessel(z))} />
                  </div>
                  <span className="min-w-0 flex-1">
                    <span className={cn("text-[12.5px] leading-snug",
                      aus ? "text-muted-foreground line-through" : "text-foreground")}>
                      {name}
                    </span>
                    {/* Der Weg zum Nachlesen: die Beschluss-Suche mit dem
                        Namen als Anfrage — ein Suchlink, kein behaupteter
                        Treffer (eine feste Vorlagen-Zuordnung liegt nicht vor). */}
                    <Link
                      href={`/council?tab=decisions&q=${encodeURIComponent(z.bezeichnung || z.code)}`}
                      title="In Beschlüssen und Anträgen danach suchen"
                      className="ml-1.5 inline-flex translate-y-[1px] text-muted-foreground hover:text-primary">
                      <Search className="h-3 w-3" strokeWidth={2.2} />
                      <span className="sr-only">In Beschlüssen und Anträgen nach „{name}“ suchen</span>
                    </Link>
                    {detailInfo(z) && (
                      <span className="mt-0.5 block text-[10.5px] leading-snug text-muted-foreground">
                        {/* Die Sachkonto-Zeilen des Dokuments — sie sagen, was
                            hinter einem generischen Namen steckt (der
                            „Eigenkapitalzuschuss“ geht an die Stadion-GmbH). */}
                        {detailInfo(z)}
                      </span>
                    )}
                  </span>
                  <span className={cn("shrink-0 font-mono text-[12px] tabular-nums",
                    aus ? "font-medium text-signal" : "text-foreground")}>
                    {aus ? "−" : ""}{deMio(z.gesamtsumme / 1e6)}&#8239;Mio.&nbsp;€
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-[10.5px] leading-relaxed text-muted-foreground">
            Warum diese Auswahl — und so viel Fliegerhorst? Das Programm nennt nur
            einen Teil seiner Vorhaben einzeln: Straßenbau sehr genau, Schulen
            dagegen nur als Sammelposten. Hier stehen die größten <em>benannten</em>{" "}
            Einzelmaßnahmen — die Gewichtung ist die des Dokuments, nicht unsere.
          </p>
          <p className="mt-2 border-t border-dashed border-border pt-2 text-[11.5px] leading-relaxed">
            {gestrichen > 0 ? (
              <>
                <strong>{deMio(gestrichen / 1e6)}&#8239;Mio.&nbsp;€ Gesamtkosten gestrichen</strong> —
                das entlastet Kasse und Schuldenpfad über die kommenden Jahre. Das Minus
                im Ergebnis bewegt es fast nicht: Dort landen nur die Abschreibungen.
              </>
            ) : (
              <span className="text-muted-foreground">
                Noch nichts gestrichen. Die Beträge sind Gesamtkosten über alle Jahre —
                eine Jahresaufteilung führt das Programm nicht.
              </span>
            )}
          </p>
          <Link href="/haushalt/investitionen#plan"
            className="mt-2 inline-flex text-[12px] font-semibold text-primary">
            Alle Vorhaben durchsuchen →
          </Link>
        </div>
      )}

      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="pt-0.5">
            <Schalter an={kredit} label="Kredite aufnehmen statt Rücklage abschmelzen"
              onClick={() => setKredit(!kredit)} />
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-semibold">
              Kredite aufnehmen statt Rücklage abschmelzen
            </p>
            <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
              {ohneKredit > 0 ? (
                <>Die Haushaltssatzung sagt {ohneKredit === satzSelbst.length
                  ? <>in allen {ohneKredit} Jahrgängen</>
                  : <>in {ohneKredit} von {satzSelbst.length} Jahrgängen</>} dasselbe:
                Kredite für Investitionen „nicht veranschlagt“<Beleg q="haushaltssatzung" /> —
                die Stadt zehrt lieber die Rücklage auf. </>
              ) : null}
              Der Schalter zeigt den Preis der Alternative — oben im Ergebnis, hier die
              Zahlen dahinter.
            </p>
          </div>
        </div>

        <div className="mt-3 grid gap-2.5 @md/labor:grid-cols-2">
          <div className="rounded-xl bg-muted/50 p-3">
            <p className="text-[11px] text-muted-foreground">Was die Stadt zuletzt zahlte</p>
            {spanne && zinsLetzte ? (
              <>
                <p className="font-display text-[17px] font-bold tabular-nums">
                  {zinsProzent(spanne.von)}–{zinsProzent(spanne.bis)}&nbsp;%
                </p>
                <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted-foreground">
                  Zinsaufwand ÷ Schuldenstand, Abschlüsse {spanne.jahre[0]}–{spanne.jahre[1]}
                  <Beleg q="jahresabschluss" /> — zuletzt {deMio(zinsLetzte.aufwand / 1e6)}&#8239;Mio.&nbsp;€
                  Zinsen im Jahr {zinsLetzte.year}. Neue Kredite bekämen heutige Sätze;
                  mehr als die gezahlte Spanne behaupten wir nicht.
                </p>
              </>
            ) : (
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                Ohne eingelesene Abschlüsse keine Spanne — wir raten keinen Zinssatz.
              </p>
            )}
          </div>
          <div className="rounded-xl bg-muted/50 p-3">
            <p className="text-[11px] text-muted-foreground">Wo die Schulden stehen</p>
            {schuldenLetzte ? (
              <>
                <p className="font-display text-[17px] font-bold tabular-nums">
                  {deMio(schuldenLetzte.insgesamt / 1e6)}&#8239;Mio.&nbsp;€
                </p>
                <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted-foreground">
                  Stand {schuldenLetzte.year}<Beleg q="schulden" />
                  {spanne && neuesDefizit > 0 && (
                    <>
                      {" "}— liefe das Minus dieses Planjahres ({deMio(neuesDefizit)}&#8239;Mio.&nbsp;€)
                      über Kredit, kämen bei der gezahlten Spanne{" "}
                      {deMio(neuesDefizit * spanne.von)}–{deMio(neuesDefizit * spanne.bis)}&#8239;Mio.&nbsp;€
                      Zins im Jahr dazu.
                    </>
                  )}
                  {dispo?.liquiditaetskredite != null && (
                    <>
                      {" "}Für den Alltag erlaubt sich die Stadt daneben bis zu{" "}
                      {deMio(dispo.liquiditaetskredite / 1e6)}&#8239;Mio.&nbsp;€ Kassenkredit ({dispo.year}).
                    </>
                  )}
                </p>
              </>
            ) : (
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                Die Schuldenreihe liegt gerade nicht vor.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Die Lektion — abgetönt statt als weiße Karte, weil sie kein
          Datenbaustein ist, sondern der Merksatz der Werkbank. */}
      <div className="rounded-2xl border border-border bg-muted/40 p-4">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was diese Werkbank zeigt
        </p>
        <p className="mt-1.5 max-w-[66ch] text-[12.5px] leading-relaxed">
          Ein gestrichenes Vorhaben verändert das geplante Jahresergebnis zunächst kaum,
          weil dort nur die späteren Abschreibungen erscheinen. Es senkt jedoch die
          Auszahlungen und damit den möglichen Finanzierungsbedarf. Daran wird der
          Unterschied zwischen Ergebnis- und Finanzhaushalt sichtbar.
        </p>
      </div>
    </div>
  );
}
