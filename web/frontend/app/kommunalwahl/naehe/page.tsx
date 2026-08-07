// /kommunalwahl/naehe — Ähnlichkeit aller Paare (Design 3c).
// Erklärung ZUERST, dann Zahlen; Grenzen direkt darunter, nicht auf einer
// anderen Seite (Bauplan §4.4).

import type { Metadata } from "next";
import { Landkarte } from "@/components/kommunalwahl/landkarte";
import { NaeheAnsicht } from "@/components/kommunalwahl/naehe";
import { KwCrumb, KwFuss, KwKopf } from "@/components/kommunalwahl/ui";
import { landkarte, naeheDaten, stand } from "@/lib/kommunalwahl";

export const metadata: Metadata = {
  title: "Wer steht wem nahe?",
  description:
    "Ähnlichkeit aller Listen-Paare zur Ratswahl Oldenburg 2026 — gerechnet nur über Thesen, zu denen sich beide äußern, mit n neben jedem Wert.",
};

const GRENZEN = [
  [
    "Programmumfang verzerrt.",
    "Wer zu wenig Thesen etwas sagt, hat kleine n — die Werte streuen stärker.",
  ],
  [
    "Die Thesenauswahl ist eine Entscheidung.",
    "44 Thesen, abgeleitet aus den Programmen — ein anderer Katalog ergäbe andere Prozente.",
  ],
  [
    "Schweigen ist keine Position.",
    "Was ein Programm nicht erwähnt, geht nicht in den Wert ein — dafür steht n immer daneben.",
  ],
  [
    "Beidseitiges „teils“ zählt als Übereinstimmung.",
    "Äußern sich beide nur unbestimmt, wertet die Formel das als Einigkeit — das Paar-Detail weist diese Thesen eigens aus.",
  ],
] as const;

export default function NaeheSeite() {
  const daten = naeheDaten();
  const karte = landkarte();
  return (
    <>
      <KwKopf crumb={<KwCrumb teil="Wer steht wem nahe?" />} />
      <main className="mx-auto w-full max-w-[1080px] px-4 pb-16 pt-9 sm:px-6 sm:pt-11 lg:px-10">
        <h1 className="font-display text-[26px] font-bold leading-[1.08] tracking-tight sm:text-[42px]">
          Wer steht wem nahe?
        </h1>
        <p className="mt-3.5 max-w-[76ch] text-[14px] leading-relaxed text-muted-foreground sm:text-[15.5px]">
          Für jedes Paar zählen nur die Thesen, zu denen sich{" "}
          <strong className="font-semibold text-foreground">beide</strong> Listen äußern (das ist{" "}
          <strong className="font-semibold text-foreground">n</strong>). Ein hoher Wert heißt: Dort stimmen
          sie oft überein — <strong className="font-semibold text-foreground">nicht</strong>, dass die
          Programme gleich sind. Unter n&thinsp;=&thinsp;{daten.minN} gilt ein Wert als nicht belastbar.
        </p>

        <div className="mt-7">
          <Landkarte punkte={karte.punkte} kanten={karte.kanten} />
        </div>

        <NaeheAnsicht daten={daten} />

        <div className="mt-6 rounded-2xl border border-border bg-background/70 p-5 sm:p-6">
          <p className="mb-2.5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
            Grenzen dieser Zahl
          </p>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {GRENZEN.map(([fett, rest]) => (
              <p key={fett} className="text-[12.5px] leading-relaxed text-muted-foreground">
                <strong className="font-semibold text-foreground">{fett}</strong> {rest}
              </p>
            ))}
          </div>
        </div>

        <KwFuss
          stand={stand()}
          links={[
            { href: "/kommunalwahl", label: "Zurück zum Überblick" },
            { href: "/kommunalwahl/methodik", label: "Methodik & Quellen" },
          ]}
        />
      </main>
    </>
  );
}
