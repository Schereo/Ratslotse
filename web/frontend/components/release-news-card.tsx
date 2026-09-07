"use client";

/**
 * „Neu bei Ratslotse" — was eine neue Ausgabe gebracht hat, auf der Übersicht.
 *
 * Ratslotse liefert laufend aus; wer alle paar Wochen vorbeikommt, merkt von
 * einem neuen Feature sonst nichts. Die Karte steht im Hinweis-Slot der
 * Heute-Seite und **nicht** als Dialog vor der Seite: Wer die App öffnet, will
 * zum Rat, nicht zu uns (Tims Entscheidung 07.09.2026).
 *
 * **Eine Bühne, keine Stichpunktliste** (Tims Befund 07.09.2026: „das ist
 * schon sehr plain"). Jedes Highlight bringt eine echte Aufnahme aus der App
 * mit — beim Teilen einen kurzen Clip, sonst ein Bild —, und man blättert
 * durch sie. Ein Feature in einem Satz zu behaupten ist etwas anderes, als es
 * zu zeigen. Ohne Medien fällt die Karte auf die Listenform zurück
 * (``kern/releases.py`` verlangt: alle oder keines).
 *
 * **Kein Selbstlauf.** Die Bühne wechselt nur auf Klick, Pfeiltaste oder Wisch.
 * Eine Karte, die von allein weiterschaltet, zieht den Text unter der lesenden
 * Person weg — und „Bewegung erklärt einen Zusammenhang oder sie fällt weg"
 * (DESIGNSPRACHE §7). Bewegt sich hier etwas von selbst, dann der Clip, und
 * der zeigt das Feature.
 *
 * **Wer sie sieht, entscheidet der Server** (`GET /news`). Dieselbe Regel wie
 * beim Einrichtungs-Assistenten: Web und native App bekommen dieselbe Antwort,
 * statt die Bedingung je Client nachzubauen.
 *
 * **„Alles klar" setzt eine Hochwassermarke am Konto**, nicht im Browser: Auf
 * dem Telefon weggewischt heißt auch am Laptop weg. Gemeldet wird die Version,
 * die diese Karte GEZEIGT hat — käme zwischen Laden und Klick ein Deploy,
 * würde „die neueste" ein Release miterledigen, das niemand sah.
 */

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { Button, Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { cn } from "@/lib/utils";

type NewsState = ApiAntwort<"/news">;
type Release = NewsState["releases"][number];
type Highlight = Release["highlights"][number];

const NEWS_QUERY_KEY = ["news"] as const;

const KICKER =
  "font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-primary";

/** „2.3.0" → „2.3" — die Patch-Null sagt niemandem etwas. */
export function kurzVersion(version: string): string {
  return version.replace(/\.0$/, "");
}

/** Der Kicker über der Karte: eine Ausgabe nennt ihre Nummer, mehrere sagen,
 *  dass hier Liegengebliebenes steht. */
export function kickerText(versionen: string[]): string {
  if (versionen.length <= 1) {
    return `Neu bei Ratslotse · ${kurzVersion(versionen[0] ?? "")}`;
  }
  return `Neu seit deinem letzten Besuch · ${versionen.map(kurzVersion).join(" und ")}`;
}

/** Hat diese Ausgabe Bilder? Die Registry verlangt alle oder keines; hier
 *  entscheidet es zwischen Bühne und Liste. */
export function mitBuehne(release: Release | undefined): boolean {
  return !!release?.highlights.length && release.highlights.every((h) => !!h.media);
}

/** Läuft die Person mit abgeschalteter Bewegung? Dann steht das Standbild
 *  statt des Clips — die Regel aus DESIGNSPRACHE §7 gilt auch für Video. */
function useRuhigeBewegung(): boolean {
  const [ruhig, setRuhig] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const lies = () => setRuhig(mq.matches);
    lies();
    mq.addEventListener("change", lies);
    return () => mq.removeEventListener("change", lies);
  }, []);
  return ruhig;
}

/** Das Medium eines Highlights, hell und dunkel.
 *
 *  Zwei Elemente statt einer Quelle mit JavaScript: Die Umschaltung hängt an
 *  derselben `.dark`-Klasse wie alles andere, ohne einen zweiten Weg, auf dem
 *  Theme und Bild auseinanderlaufen könnten. */
function Medium({ media, aktiv }: { media: NonNullable<Highlight["media"]>; aktiv: boolean }) {
  const ruhig = useRuhigeBewegung();
  const gemeinsam = "h-full w-full object-cover object-center";

  if (media.kind === "video" && !ruhig) {
    return (
      // `key` am aktiven Index: Beim Wechsel startet der Clip von vorn, statt
      // in der Mitte weiterzulaufen.
      <video
        key={aktiv ? "an" : "aus"}
        className={gemeinsam}
        poster={media.poster ?? undefined}
        src={media.src}
        autoPlay muted loop playsInline preload="metadata"
        aria-label={media.alt}
      />
    );
  }
  // Bild — und bei abgeschalteter Bewegung auch das Standbild des Clips.
  const quelle = media.kind === "video" ? (media.poster ?? media.src) : media.src;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- die Maße stehen
    // erst zur Laufzeit fest (Registry), und `next/image` bringt für vier
    // statische Dateien im Export nichts.
    <img src={quelle} alt={media.alt} className={gemeinsam} loading="lazy" />
  );
}

/** Die Bühne: das Bild, der Satz — und ein geführter Durchgang.
 *
 *  **Warum geführt** (Tims Befund 07.09.2026): In der ersten Fassung stand
 *  „Alles klar" gleichberechtigt neben den Reitern. Man klickte es sofort, und
 *  drei von vier Neuerungen hatte nie jemand gesehen — die Karte hatte ihren
 *  einzigen Zweck damit verfehlt. Jetzt ist **„Weiter" der Hauptknopf**, und
 *  erst auf der letzten Station wird daraus „Alles klar". Vier Klicks für vier
 *  Neuerungen; wer springen will, nimmt die Reiter.
 *
 *  Die Reiter sind nummeriert und haken sich ab. Nummer, Haken und der Zähler
 *  („2 von 4") sagen zusammen, dass hier etwas zum Durchgehen steht — bloße
 *  Pillen taten das nicht.
 */
function Buehne({
  highlights, aufKlar, klarLaeuft,
}: { highlights: Highlight[]; aufKlar: () => void; klarLaeuft: boolean }) {
  const [i, setI] = useState(0);
  // Die erste Station hat man mit dem Aufschlagen der Karte gesehen.
  const [gesehen, setGesehen] = useState<number[]>([0]);
  const basis = useId();
  const reiter = useRef<(HTMLButtonElement | null)[]>([]);
  const h = highlights[i];
  const n = highlights.length;
  const alleGesehen = gesehen.length >= n;
  // Alle Medien einer Ausgabe tragen dasselbe Verhältnis (Wächter im Backend);
  // das erste genügt also für den Rahmen. Ohne Medium bleibt es beim Querformat.
  const rahmen = h.media?.aspect ?? "16/9";
  const hochkant = (() => {
    const [b, hh] = rahmen.split("/").map(Number);
    return Number.isFinite(b) && Number.isFinite(hh) && hh > b;
  })();

  const zeige = useCallback((ziel: number, fokus = false) => {
    const neu = ((ziel % n) + n) % n;
    setI(neu);
    setGesehen((alt) => (alt.includes(neu) ? alt : [...alt, neu]));
    if (fokus) reiter.current[neu]?.focus();
  }, [n]);

  /** „Weiter" springt zur nächsten Station, die noch NICHT abgehakt ist —
   *  wer zwischendurch über die Reiter gesprungen ist, bekommt dadurch trotzdem
   *  jede Neuerung einmal zu sehen, statt am Ende in einer Schleife zu landen. */
  const weiter = useCallback(() => {
    for (let s = 1; s <= n; s += 1) {
      const kandidat = (i + s) % n;
      if (!gesehen.includes(kandidat)) return zeige(kandidat);
    }
    zeige(i + 1);
  }, [gesehen, i, n, zeige]);

  return (
    <div className="mt-3">
      <div className="flex flex-col gap-4 @2xl:flex-row @2xl:items-center">
        {/* `aspect-video`: Alle Aufnahmen entstehen im selben 16:9-Rahmen
            (s. kern/releases.py) — der Kasten hat damit dieselbe Form wie sein
            Inhalt, füllt sich randlos und behält beim Blättern seine Höhe.
            Ein Sprung beim Wechsel ist genau das, was die Bewegungsregeln
            vermeiden (DESIGNSPRACHE §7). */}
        <div
          id={`${basis}-panel`}
          role="tabpanel"
          aria-labelledby={`${basis}-tab-${i}`}
          // Das Verhältnis kommt aus dem Medium (`kern/releases.py`), es wird
          // nicht geraten: Im Browser sind die Aufnahmen querformatige
          // Fenster, in der App hochkante Telefon-Bildschirme. Alle Medien
          // einer Ausgabe teilen sich eines, der Kasten springt also nicht.
          style={{ aspectRatio: rahmen }}
          className={cn(
            "relative shrink-0 overflow-hidden rounded-xl border border-border bg-background",
            // Querformat nimmt sich die Breite, Hochformat die HÖHE: Ein
            // Telefon-Bildschirm über die halbe Kartenbreite wäre 700 px hoch
            // und ließe rechts neben dem Satz ein leeres Feld — genau der
            // halb leere Kasten, den die Designsprache verbietet.
            hochkant ? "h-[300px] w-auto self-center @2xl:h-[420px] @2xl:self-auto"
                     : "@2xl:w-[52%]",
          )}
        >
          {/* Der Wechsel blendet nur — eine Strecke gäbe es hier nicht zu
              zeigen, und `opacity` allein kostet kein Layout. */}
          <div key={i} className="h-full w-full animate-in fade-in-0 duration-fluss ease-out-strong">
            {h.media ? <Medium media={h.media} aktiv /> : null}
          </div>
        </div>

        <div className="min-w-0 flex-1">
          {/* Der Zähler sagt vor dem ersten Klick, dass es mehr als das eine
              gibt — das tat die Karte vorher nirgends. */}
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
            {i + 1} von {n}
          </p>
          <div key={i} className="animate-in fade-in-0 duration-fluss ease-out-strong">
            <h3 className="mt-1 font-display text-[15px] font-bold leading-snug text-foreground">
              {h.title}
            </h3>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{h.text}</p>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {/* Der Hauptknopf führt durch die Ausgabe und wird erst am Ende
                zum Wegräumen. */}
            {alleGesehen ? (
              <Button size="sm" onClick={aufKlar} disabled={klarLaeuft}>
                <Check className="!size-3.5" />
                Alles klar
              </Button>
            ) : (
              <Button size="sm" onClick={weiter}>
                Weiter <ArrowRight className="!size-3.5" />
              </Button>
            )}
            <Button variant="ghost" size="sm" asChild>
              <Link href={h.url}>
                Ansehen <ArrowRight className="!size-3.5" />
              </Link>
            </Button>
          </div>
        </div>
      </div>

      {/* Die Reiter tragen Nummer und Titel, nicht bloß Punkte: Man soll
          vorher wissen, wohin man blättert, und hinterher sehen, was man schon
          hatte.
          Schmal scrollt die Leiste seitwärts (dieselbe Bauform wie im
          Admin-Panel, und der halb sichtbare nächste Reiter sagt, dass es
          weitergeht); breit bricht sie um. Ein abgeschnittener Reiter auf
          einer 1.100 px breiten Karte sieht dagegen nach Fehler aus, nicht
          nach Scrollbarkeit. */}
      <div
        role="tablist"
        aria-label="Neuerungen dieser Ausgabe"
        className="scrollbar-none -mx-1 mt-4 flex flex-nowrap gap-1.5 overflow-x-auto px-1 [-webkit-overflow-scrolling:touch] @2xl:flex-wrap @2xl:overflow-x-visible"
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") { e.preventDefault(); zeige(i + 1, true); }
          if (e.key === "ArrowLeft") { e.preventDefault(); zeige(i - 1, true); }
        }}
      >
        {highlights.map((k, m) => {
          const aktiv = m === i;
          const fertig = gesehen.includes(m) && !aktiv;
          return (
            <button
              key={k.url + k.title}
              ref={(el) => { reiter.current[m] = el; }}
              type="button"
              role="tab"
              id={`${basis}-tab-${m}`}
              aria-selected={aktiv}
              aria-controls={`${basis}-panel`}
              tabIndex={aktiv ? 0 : -1}
              onClick={() => zeige(m)}
              className={cn(
                "group inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-[11.5px] font-medium transition-colors duration-tipp",
                aktiv
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-card text-muted-foreground hover:border-primary/30 hover:text-foreground",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold tabular-nums",
                  aktiv ? "bg-primary text-primary-foreground"
                        : fertig ? "bg-primary/15 text-primary"
                                 : "bg-muted text-muted-foreground",
                )}
              >
                {fertig ? <Check className="h-2.5 w-2.5" /> : m + 1}
              </span>
              {k.title}
            </button>
          );
        })}
      </div>
    </div>
  );
}


/** Ohne Medien: dieselben Sätze als Liste — lesbar, nur eben still. */
function Liste({ highlights }: { highlights: Highlight[] }) {
  return (
    <ul className="mt-2.5 grid gap-x-8 gap-y-2.5 @2xl:grid-cols-2">
      {highlights.map((h) => (
        <li key={h.url + h.title} className="min-w-0">
          <Link href={h.url} className="group block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="text-sm font-semibold text-foreground [@media(hover:hover)]:group-hover:text-primary">
              {h.title}
              <ArrowRight aria-hidden className="ml-1 inline h-3.5 w-3.5 align-[-2px] text-primary transition-transform duration-fluss ease-out-strong [@media(hover:hover)]:group-hover:translate-x-0.5" />
            </span>
            <span className="mt-0.5 block text-sm leading-relaxed text-muted-foreground">{h.text}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function ReleaseNewsCard() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: NEWS_QUERY_KEY,
    queryFn: () => vertrag.get("/news"),
    enabled: !!user,
    // Eine Ausgabe erscheint ein paar Mal im Jahr — einmal je Sitzung reicht.
    staleTime: 60 * 60 * 1000,
  });

  const wegklicken = useMutation({
    mutationFn: (version: string) => api.post("/news/seen", { version }),
    // Optimistisch leeren: Die Karte soll beim Klick verschwinden, nicht nach
    // der Antwort. Ein Fehlschlag bringt sie beim nächsten Laden zurück —
    // besser, als eine weggewischte Karte stehen zu lassen.
    onMutate: () => {
      qc.setQueryData<NewsState>(NEWS_QUERY_KEY, (cur) =>
        cur ? { ...cur, releases: [], older_count: 0 } : cur);
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: NEWS_QUERY_KEY }); },
  });

  const releases = data?.releases ?? [];
  if (releases.length === 0) return null;

  const [neuestes, ...aeltere] = releases;
  const weitere = data?.older_count ?? 0;

  return (
    // `@container`: Die Karte steht im Hinweis-Slot über die volle Breite — auf
    // einem 1440er-Schirm sind das 1030 px. Die Bühne stellt Bild und Text erst
    // dann nebeneinander, wenn beide Platz haben; darunter untereinander.
    <Card className="@container flex flex-col gap-4 border-primary/25 bg-primary/[0.04] p-4 sm:flex-row">
      {/* `hat-idee`: Lotti bringt etwas mit, sie warnt nicht. */}
      <Mascot decorative regung="hat-idee" className="hidden h-14 w-14 flex-none sm:block" />

      <div className="min-w-0 flex-1">
        <p className={KICKER}>
          <Sparkles className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden />
          {kickerText(releases.map((r) => r.version))}
        </p>
        <h2 className="mt-0.5 font-display text-base font-bold text-foreground">
          {neuestes.title}
        </h2>

        {mitBuehne(neuestes)
          ? (
            <Buehne
              highlights={neuestes.highlights}
              aufKlar={() => wegklicken.mutate(neuestes.version)}
              klarLaeuft={wegklicken.isPending}
            />
          )
          : <Liste highlights={neuestes.highlights} />}

        {aeltere.length > 0 && (
          <div className="mt-3.5 border-t border-border pt-3">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
              Außerdem seit deinem letzten Besuch
            </p>
            <ul className="mt-1.5 flex flex-col gap-1">
              {aeltere.map((r) => (
                <li key={r.version} className="text-[13px] leading-snug text-muted-foreground">
                  <span className="font-semibold text-foreground">{kurzVersion(r.version)}</span>
                  {" — "}
                  {r.highlights.map((h) => h.title).join(" · ")}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
          {/* Mit Bühne trägt DEREN Hauptknopf das Wegräumen — er wird erst am
              Ende dazu. Zwei „Alles klar" nebeneinander wären genau der
              Schnellausstieg, der die Karte wirkungslos gemacht hat. */}
          {!mitBuehne(neuestes) && (
            <Button
              size="sm"
              onClick={() => wegklicken.mutate(neuestes.version)}
              disabled={wegklicken.isPending}
            >
              <Check className="!size-3.5" />
              Alles klar
            </Button>
          )}
          {/* „dieser Version" stimmt nur, wenn es wirklich eine ist — bei
              mehreren stünde dort ein falsches Versprechen. */}
          <Link href="/changelog" className="text-[13px] text-muted-foreground underline hover:text-foreground">
            {weitere > 0
              ? `Alle Änderungen — auch ${weitere} ältere Version${weitere === 1 ? "" : "en"}`
              : releases.length > 1
                ? "Alle Änderungen im Einzelnen"
                : "Alle Änderungen dieser Version"}
          </Link>
        </div>
      </div>
    </Card>
  );
}
