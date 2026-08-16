"use client";

// /haushalt — Stadtfinanzen-Übersicht (Entwürfe H2-01 Desktop, H2-11 mobil,
// H2-12 dunkel; die Bereichstabelle ist H2-03).
//
// Leserichtung: Jahr wählen → Anzeigetafel mit der Kernzahl und dem
// Kern-Visual (Gegenbalken, umschaltbar auf die 100-Euro-Ansicht) → was der
// Haushalt überhaupt ist → der Kassenzettel pro Kopf samt Ersparten (die
// eigentliche Story) → die Bereiche als Tabelle → Wegweiser → woher das Geld
// kommt (Flussbild) → Zeitreihe. Jede Karte trägt ihre Quelle.
//
// Drei Dinge, die hier bewusst NICHT stehen:
//
//  * **Kein zweiter Seitentitel über der Tafel.** Die Kernzahl IST die
//    Überschrift (`<h1>` in `tafel.tsx`); ein „Wohin fließt das Geld der
//    Stadt?" darüber wäre eine zweite Überschrift für dieselbe Sache.
//  * **Keine drei Kernzahl-Karten mehr.** Ein­nahmen, Ausgaben und Differenz
//    stehen auf der Tafel neben der großen Zahl — als Karten daneben nannte
//    die Seite dieselben drei Zahlen zweimal.
//  * **Kein `LottiVergleich` und kein eigener Rücklagen-Hinweis mehr.** Beide
//    standen bis 08/2026 hier und sagten zusammen mit dem Kassenzettel
//    dieselbe Pro-Kopf-Zahl dreimal. Der Zettel (`kassenzettel.tsx`) hat sie
//    abgelöst und trägt beides: die Division und die Reichweite des Ersparten.
//    Er läuft nur fürs jüngste Planjahr — `council_einwohner` endet mit dem
//    Haushaltsjahr 2025, und den Plan von 2020 durch die Einwohnerzahl von
//    2025 zu teilen wäre ein stiller Fehler von rund 4 %.

import { useEffect, useMemo, useRef, useState } from "react";
import { Segmented } from "@/components/ui";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { Wegweiser } from "@/components/haushalt/wegweiser";
import { Datenstand } from "@/components/haushalt/datenstand";
import { useFetch } from "@/lib/use-fetch";
import { Tafel } from "@/components/haushalt/tafel";
import { Bereichstabelle } from "@/components/haushalt/bereichstabelle";
import { Gegenbalken } from "@/components/haushalt/gegenbalken";
import { Flussbild } from "@/components/haushalt/flussbild";
import { Kassenzettel, kassenzettelQuellen } from "@/components/haushalt/kassenzettel";
import { Steuereuro } from "@/components/haushalt/steuereuro";
import { Zeitreihe } from "@/components/haushalt/zeitreihe";
import {
  HaushaltDaten,
  deMio, fehlendeJahre, flussJahre, jahreSortiert, mio, quellenLabel, summe,
} from "@/lib/haushalt";

export default function HaushaltPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const jahre = useMemo(() => (data ? jahreSortiert(data) : []), [data]);
  const [jahr, setJahr] = useState<number | null>(null);
  const [visual, setVisual] = useState<"balken" | "euro">("balken");
  const jahrLeiste = useRef<HTMLDivElement>(null);

  const aktJahr = jahr ?? jahre[jahre.length - 1] ?? null;
  const zeilen = aktJahr && data ? data.jahre[String(aktJahr)] ?? [] : [];
  const gesamt = summe(zeilen);
  // Aus Rohwerten gerundet — 883,9 − 812,9 ergäbe 71,0, tatsächlich sind es 71,1.
  const defizit = gesamt?.ertraege != null && gesamt?.aufwendungen != null
    ? mio(gesamt.aufwendungen - gesamt.ertraege) : null;
  const luecken = fehlendeJahre(jahre);
  const quelle = aktJahr ? quellenLabel(zeilen, aktJahr) : null;

  // Das gewählte Jahr in die Scrollzeile holen — NUR waagerecht.
  // Sieben Jahre passen auf 375 px nicht nebeneinander, und die Voreinstellung
  // ist das jüngste, also das letzte: Ohne das hier stand beim Öffnen „2020"
  // links und die aktive Pille lag außerhalb des Bildes. `scrollLeft` statt
  // `scrollIntoView`, weil letzteres auch die SEITE scrollt und damit die
  // Anzeigetafel unter die Kopfzeile schieben würde.
  useEffect(() => {
    const leiste = jahrLeiste.current;
    if (!leiste || aktJahr == null) return;
    const pille = leiste.querySelector<HTMLElement>(`[data-jahr="${aktJahr}"]`);
    if (!pille) return;
    const ziel = pille.offsetLeft - (leiste.clientWidth - pille.offsetWidth) / 2;
    leiste.scrollLeft = Math.max(0, ziel);
  }, [aktJahr]);

  if (loading || !data || !aktJahr) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>;
  }

  // Der Kassenzettel braucht die amtliche Einwohnerzahl und läuft nur fürs
  // jüngste Planjahr (Begründung im Kopf dieser Datei).
  const zeigtZettel = aktJahr === jahre[jahre.length - 1] && data.einwohner != null;

  // Angemeldet wird nur, was auf DIESER Seite auch zitiert wird — sonst stünde
  // im Verzeichnis ein Beleg für nichts, und die seitenweise Nummerierung
  // zeigte ins Leere. Reihenfolge = Leserichtung der Seite: Tafel, Zettel,
  // Flussbild.
  const quellen: QuellenSchluessel[] = [
    "plan",
    ...(zeigtZettel ? kassenzettelQuellen(data, aktJahr) : []),
    ...(flussJahre(data).length > 0 ? (["jahresabschluss"] as const) : []),
  ];

  return (
    <Quellenkontext schluessel={quellen} jahr={aktJahr}>
    <div className="flex flex-col gap-4">
      {/* Kopf: Jahr-Umschalter und Quelle. Der Titel der Seite steht auf der
          Anzeigetafel — hier oben nur der Kicker, damit klar ist, wo man ist. */}
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-end sm:justify-between sm:gap-5">
        <div className="min-w-0">
          <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stadtfinanzen Oldenburg
          </p>
          {/* Scrollt statt überzulaufen: Sieben Jahre passen auf 375 px nicht in
              eine Zeile (Tim, 16.08.). Umbrechen zerrisse die Pill-Gruppe,
              deshalb dieselbe Fade-Scrollzeile wie bei den Chips im
              Ratsgespräch — Scrollbalken ausgeblendet. */}
          <div ref={jahrLeiste}
            className="scrollbar-none -mx-1 mt-1.5 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
            <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
              {(() => {
                const alle: number[] = [];
                for (let y = jahre[0]; y <= jahre[jahre.length - 1]; y++) alle.push(y);
                return alle.map((y) =>
                  jahre.includes(y) ? (
                    <button key={y} type="button" data-jahr={y} onClick={() => setJahr(y)}
                      className={
                        "rounded-full px-3 py-1 text-[12.5px] " + (y === aktJahr
                          ? "bg-primary font-semibold text-primary-foreground"
                          : "text-foreground/75 hover:bg-accent")
                      }>
                      {y}
                    </button>
                  ) : (
                    <span key={y} title="Für dieses Jahr fehlen uns die Daten"
                      className="rounded-full border border-dashed border-border px-2.5 py-1 text-[12.5px] text-muted-foreground">
                      {y}
                    </span>
                  ));
              })()}
            </div>
          </div>
          {luecken.length > 0 && (
            <span className="mt-1 block text-[11.5px] text-muted-foreground">
              Für {luecken.join(", ")} fehlen uns die Daten — die Zeitreihe zeigt die Lücke.
            </span>
          )}
        </div>
        {/* Hier stand bis 16.08. ein Knopf „Haushaltsplan als PDF". Er war die
            einzige prominent verlinkte Quelle der Seite und ließ sie deshalb
            wie die einzige aussehen (Tim). Verloren ist nichts: Er trug die
            jahresgenaue PDF-Adresse — genau die zeigt der Beleg „Beschlossener
            Haushaltsplan" im Quellenverzeichnis jetzt selbst, statt wie früher
            auf die Finanz-Übersichtsseite der Stadt. */}
      </div>

      {/* Anzeigetafel (H2-01/H2-11/H2-12): Kernzahl, die drei Summen und das
          Kern-Visual auf einer Fläche, die in beiden Themes dunkel ist. */}
      <Tafel
        zeilen={zeilen}
        jahr={aktJahr}
        aktuell={aktJahr === jahre[jahre.length - 1]}
        aktion={
          <Segmented value={visual} onChange={setVisual} options={[
            { value: "balken", label: "Balken" },
            { value: "euro", label: "100-Euro-Ansicht" },
          ]} />
        }
      >
        {visual === "balken"
          ? <Gegenbalken zeilen={zeilen} jahr={aktJahr} />
          : <Steuereuro zeilen={zeilen} jahr={aktJahr} />}
      </Tafel>
      {quelle && (
        <p className="-mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
          Quelle: {quelle.url
            ? <a href={quelle.url} target="_blank" rel="noopener noreferrer" className="underline decoration-dotted">{quelle.text}</a>
            : quelle.text} · Ergebnishaushalt, ordentliche Erträge und Aufwendungen ·
          Rundung auf eine Nachkommastelle.
        </p>
      )}

      {/* „Haushaltsbuch" stand hier bis 16.08. — das Wort fing die
          Glossar-Erklärung zu „Haushalt" ein und erklärte das Bild mit der
          Sache, die es erklären sollte. „Kassenbuch" kollidiert mit keinem
          Eintrag. Die Einwohnerzahl kommt aus den Daten statt fest im Text:
          Sie steht auf dem Kassenzettel gleich darunter noch einmal, und zwei
          Stände derselben Zahl auf einer Seite sind eine Frage zu viel. */}
      <LottiErklaert
        titel="Was ist der Haushalt überhaupt?"
        text={"Einmal im Jahr legt die Stadt fest, wofür sie ihr Geld ausgeben will — wie ein "
          + "Kassenbuch für "
          + (data.einwohner
            ? `${data.einwohner.einwohner.toLocaleString("de-DE")} Menschen`
            : "eine ganze Stadt")
          + ". Der Rat beschließt diesen Plan; danach darf die Verwaltung nur ausgeben, "
          + "was darin steht."}
      />

      {/* Der Kassenzettel (H2-02): die Kernzahl in einer Einheit, die man
          fühlt — und die Zeile, um die es politisch geht, als letzte des Bons
          („aus dem Ersparten"). */}
      {zeigtZettel && data.einwohner ? (
        <Kassenzettel daten={data} jahr={aktJahr} einwohner={data.einwohner} />
      ) : defizit != null && defizit > 0 ? (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Abgeschlossenes Haushaltsjahr
          </p>
          <p className="mt-1.5 max-w-[74ch] text-sm leading-relaxed text-foreground/90">
            Für {aktJahr} plante die Stadt ein Minus von {deMio(defizit)}&#8239;Mio.&nbsp;€. Wie viel
            davon am Ende wirklich fehlte und wie hoch die Rücklage damals war, steht im
            Jahresabschluss — den lesen wir noch ein. Die Reichweite der heutigen Rücklage
            zeigen wir nur beim aktuellen Haushaltsjahr, weil sie sonst eine Rechnung wäre,
            die es so nie gab.
          </p>
        </div>
      ) : null}

      {/* Die Bereiche als Tabelle (H2-03): löst die untere Hälfte der
          Anzeigetafel auf — welcher Bereich wie viel ausgibt und wie viel
          davon die Stadt selbst trägt. */}
      <Bereichstabelle zeilen={zeilen} jahr={aktJahr} />

      <Wegweiser />

      {/* Flussbild (H-18): Einnahmearten → eine Kasse → Bereiche. Steht NACH
          dem Gegenbalken, weil es dessen linke Seite auflöst: Der Balken zeigt,
          welcher Bereich das Geld verbucht („Finanzmanagement und Recht" —
          dort laufen alle Steuern auf), das Flussbild, woher es kommt. */}
      {flussJahre(data).length > 0 && (
        <>
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
            <Flussbild daten={data} jahr={aktJahr} />
            <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
              Quelle: Ergebnisrechnung des jeweiligen Jahresabschlusses<Beleg q="jahresabschluss" /> —
              Einnahmearten (Posten 01–11) und Aufwendungen je Teilhaushalt (Posten 20) aus
              derselben Tabelle desselben Jahres.
            </p>
          </div>

          <LottiErklaert
            titel="Warum die Gewerbesteuer nicht der Feuerwehr gehört"
            text="Was die Stadt einnimmt, ist fast nie für einen bestimmten Zweck reserviert: Steuern, Gebühren und Zuweisungen landen erst alle zusammen in einer Kasse, und aus dieser einen Kasse wird dann jede Aufgabe bezahlt. Nur wenige Zuschüsse von Bund und Land sind ausdrücklich an einen Zweck gebunden. Deshalb lässt sich nicht sagen, welche Einnahme welche Ausgabe trägt."
          />
        </>
      )}

      {/* Zeitreihe (H-07) */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
        <Zeitreihe daten={data} />
        <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
          Quelle: Beschlossene Haushaltspläne {jahre[0]}–{jahre[jahre.length - 1]}, Stadt Oldenburg · jeweils Planwerte, nicht Jahresabschluss.
        </p>
      </div>

      {/* Steht am Fuß und gilt für den ganzen Bereich: Wer hier ankommt, hat
          die Zahlen gesehen und fragt sich, bis wann sie reichen. */}
      <Datenstand />

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}
