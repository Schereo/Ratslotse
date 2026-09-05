"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, CalendarPlus, Check, Link2, RefreshCw } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { vertrag } from "@/lib/vertrag";
import type { CommitteeDetail } from "@/lib/types";
import { Button, CardListSkeleton, ErrorState, PageHeader, formatDate, toast } from "@/components/ui";
import { wochentagKurz } from "@/lib/utils";
import { committeeExplains, committeeIcon, committeeRank, shortCommittee } from "@/lib/committees";

/** Der Termin in zwei Längen — oder gar nicht.
 *
 *  Ohne Termin gibt es keine Zeile: Einen zu erfinden wäre schlimmer als
 *  keinen zu zeigen. Und ohne Uhrzeit bleibt es beim Datum; das Ratsinfo
 *  führt sie nicht immer.
 *
 *  Zwei Längen, weil die Zeile neben dem Knopf steht: Auf 390 px schnitt
 *  „MO 14.09.2026 · 17:00" genau die Uhrzeit ab — also die Angabe, für die
 *  die Zeile da ist. Kurz fällt das Jahr weg, das bei einem Termin in den
 *  nächsten Wochen ohnehin nichts beiträgt.
 */
function terminText(d: CommitteeDetail): { kurz: string; lang: string } | null {
  if (!d.next_date) return null;
  const tag = wochentagKurz(d.next_date);
  const voll = formatDate(d.next_date);                 // 14.09.2026
  const ohneJahr = voll.split(".").slice(0, 2).join(".") + ".";
  const zeit = d.next_time ? ` · ${d.next_time.slice(0, 5)}` : "";
  const praefix = tag ? `${tag} ` : "";
  return { kurz: `${praefix}${ohneJahr}${zeit}`, lang: `${praefix}${voll}${zeit}` };
}

/** Das Zeichen des Gremiums auf getönter Scheibe — dieselbe Bauform wie im
 *  Einrichtungs-Assistenten (`GremiumZeichen` in onboarding-flow.tsx), damit
 *  ein Gremium überall gleich aussieht: Kelle für den Bau, Blatt fürs Grün.
 *  Abonniert = gefüllt, wie dort „gewählt = gefüllt". */
function GremiumZeichen({ committee, aktiv }: { committee: string; aktiv: boolean }) {
  const Icon = committeeIcon(committee);
  return (
    <span aria-hidden className={
      "flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px] transition-colors "
      + (aktiv ? "bg-primary text-primary-foreground" : "bg-primary/[0.08] text-primary")
    }>
      <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
    </span>
  );
}

/** Eine Kachel je Gremium — Zeichen, Name, Erklärsatz, Termin, Beschlusszahl,
 *  Knopf.
 *
 *  Bis 09/2026 war das eine flache Zeile in einer geteilten Liste. Sie trug
 *  dieselben Angaben, aber sie sahen alle gleich aus: sechzehn Zeilen Text
 *  untereinander, die man lesen musste, um sie zu unterscheiden — genau der
 *  Einwand, der im Einrichtungs-Assistenten schon zu den Kacheln geführt hat
 *  („sehr plain, sehr langweilig", Tim, 01.09.2026). Jetzt steht hier dieselbe
 *  Kachel wie dort, nur um das erweitert, was die Abo-Seite mehr weiß.
 *
 *  Nichts fällt dabei weg: Die Beschlusszahl stand vorher erst ab 576 px
 *  Blattbreite in der Zeile (`@xl:inline`) — auf dem Telefon war sie gar nicht
 *  zu sehen. In der Kachel hat sie ihre eigene Fußzeile und gilt auf jeder
 *  Breite. */
function Kachel({ d, abonniert, onToggle, busy, laeutet }: {
  d: CommitteeDetail; abonniert: boolean; onToggle: () => void; busy: boolean;
  /** Gerade abonniert — die Glocke schwingt einmal aus. */
  laeutet: boolean;
}) {
  const termin = terminText(d);
  const erklaerung = committeeExplains(d.name);
  return (
    <div className={
      "flex flex-col rounded-xl border p-3.5 transition-colors "
      + (abonniert ? "border-primary bg-primary/5" : "border-border bg-card")
    }>
      <div className="flex items-start gap-3 pb-3">
        <GremiumZeichen committee={d.name} aktiv={abonniert} />
        <div className="min-w-0 flex-1">
          {/* Der amtliche Name bleibt im title erreichbar — angezeigt wird der
              Kurzname, wie im Einrichtungs-Assistenten (Design 28a/R3). */}
          <p className="text-[13.5px] font-semibold leading-snug text-foreground" title={d.name}>
            {shortCommittee(d.name)}
          </p>
          {/* Der Erklärsatz kam mit Design 28a/R3 dazu, weil ein Gremienname
              allein nicht sagt, worüber dort entschieden wird — und genau das
              ist die Frage vor einem Abo. Ein unbekanntes Gremium bekommt
              keinen erfundenen Satz, dann bleibt es beim Namen. */}
          {erklaerung && (
            <p className="mt-0.5 text-[12px] leading-snug text-muted-foreground">{erklaerung}</p>
          )}
        </div>
      </div>

      {/* Die Fußzeile trägt die harten Angaben und den Knopf. `mt-auto` hält
          sie am Boden: Im zweispaltigen Raster stehen zwei Kacheln
          nebeneinander, deren Erklärsätze verschieden lang umbrechen — ohne
          das säßen ihre Knöpfe auf verschiedenen Höhen. */}
      <div className="mt-auto flex items-end justify-between gap-3 border-t border-border/60 pt-3">
        <div className="min-w-0">
          {/* Mobil ohne das Wort „Nächste Sitzung": Es kostete so viel Zeile,
              dass die Uhrzeit dahinter abgeschnitten wurde — also genau die
              Angabe, für die die Zeile da ist. Neben einem Datum in der Zukunft
              sagt der Zusatz ohnehin wenig; auf dem Desktop ist Platz für ihn. */}
          {termin && (
            <p className="truncate font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
              <span className="hidden @2xl:inline">Nächste Sitzung · {termin.lang}</span>
              <span className="@2xl:hidden">{termin.kurz}</span>
            </p>
          )}
          {d.decisions_year > 0 && (
            <p className="mt-1 truncate text-[11px] text-muted-foreground">
              {d.decisions_year} {d.decisions_year === 1 ? "Beschluss" : "Beschlüsse"} {new Date().getFullYear()}
            </p>
          )}
        </div>
        <button
          type="button" onClick={onToggle} disabled={busy}
          aria-pressed={abonniert}
          aria-label={`${d.name} ${abonniert ? "abbestellen" : "abonnieren"}`}
          className={
            abonniert
              ? "inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl border border-border bg-card px-3 text-[13px] font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50"
              : "inline-flex h-8 shrink-0 items-center whitespace-nowrap rounded-xl bg-primary px-3 text-[13px] font-medium text-primary-foreground shadow-[0_1px_2px_hsl(var(--primary)/0.25)] transition-opacity hover:opacity-90 disabled:opacity-50"
          }
        >
          {/* Direkt nach dem Abonnieren läutet kurz die Glocke — sie sagt, was
              das Abo zusagt („ab jetzt melde ich mich"). Danach steht dort
              wieder das ruhige Häkchen; ein dauerhaftes Glockensymbol wäre in
              einer Liste mit sechzehn Kacheln nur Unruhe. */}
          {laeutet
            ? <Bell className="glocke-laeutet h-3.5 w-3.5" aria-hidden />
            : abonniert && <Check className="h-3.5 w-3.5" aria-hidden />}
          {abonniert ? "Abonniert" : "Abonnieren"}
        </button>
      </div>
    </div>
  );
}

/** „Im Kalender abonnieren" — die Karte des Kalender-Abos.
 *
 *  Sie steht auf der Anzeigetafel (`hh-tafel`), weil sie das eine Besondere
 *  der Seite ist: Alles andere sind Schalter, das hier ist ein Weg nach
 *  draußen. Genau davor hatte Tim Bedenken (05.09.2026): Wer den Kalender
 *  hat, kommt vielleicht nie wieder. Deshalb sagt der Text, was jeder Termin
 *  mitbringt — die wichtigsten Punkte und den Link zu Tagesordnung, Vorlagen
 *  und Ergebnis — und der Feed hält das (`kern/calendar_feed.py`).
 *
 *  `webcal://` öffnet auf Telefon und Mac direkt den Abo-Dialog der
 *  Kalender-App; die https-Adresse ist zum Einfügen bei Google und Outlook.
 *  „Neue Adresse" ist absichtlich klein und fragt nach: Sie macht jeden
 *  bestehenden Kalender-Eintrag stumm. */
function KalenderAboKarte({ anzahlAbos }: { anzahlAbos: number }) {
  const qc = useQueryClient();
  const abo = useQuery({
    queryKey: ["calendar-subscription"],
    queryFn: () => vertrag.get("/calendar/subscription"),
  });
  const rotate = useMutation({
    mutationFn: () => vertrag.post("/calendar/subscription/rotate"),
    onSuccess: (daten) => {
      qc.setQueryData(["calendar-subscription"], daten);
      toast.success("Neue Kalender-Adresse erzeugt. Bitte einmal neu abonnieren.");
    },
    onError: () => toast.error("Die Adresse konnte nicht erneuert werden."),
  });

  const kopieren = async () => {
    if (!abo.data) return;
    try {
      await navigator.clipboard.writeText(abo.data.url);
      toast.success("Link kopiert.");
    } catch {
      toast.error("Link konnte nicht kopiert werden.");
    }
  };

  const umfang = anzahlAbos === 0
    ? "Ohne Ausschuss-Abo landen alle Sitzungen im Kalender. Abonniere unten Gremien, dann nur deren Termine – plus jede Sitzung, die eines deiner Themen berührt."
    : `Im Kalender: die Sitzungen ${anzahlAbos === 1 ? "deines abonnierten Gremiums" : `deiner ${anzahlAbos} abonnierten Gremien`} – plus jede Sitzung, die eines deiner Themen berührt, mit Erinnerung am Vorabend.`;

  return (
    <section className="hh-tafel mt-6 rounded-2xl border border-border bg-background p-4 text-foreground @xl:p-5"
      aria-labelledby="kalender-abo-titel">
      <div className="flex items-start gap-3">
        <span aria-hidden className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-primary text-primary-foreground">
          <CalendarPlus className="h-5 w-5" strokeWidth={2} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Kalender-Abo</p>
          <h2 id="kalender-abo-titel" className="text-[15px] font-semibold leading-snug">Im Kalender abonnieren</h2>
          <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
            Deine Sitzungen in Apple Kalender, Google oder Outlook – jeder Termin mit den wichtigsten
            Punkten der Tagesordnung und dem Link zu Vorlagen und Ergebnis auf Ratslotse.
          </p>
        </div>
      </div>

      {abo.isPending && <p className="mt-4 text-[12px] text-muted-foreground">Kalender-Adresse wird geholt …</p>}
      {abo.isError && (
        <p className="mt-4 text-[12px] text-muted-foreground">
          Die Adresse kam nicht durch.{" "}
          <button type="button" className="font-medium text-primary hover:underline" onClick={() => void abo.refetch()}>Noch einmal</button>
        </p>
      )}
      {abo.data && (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild size="sm">
              <a href={abo.data.webcal_url}><CalendarPlus /> Kalender abonnieren</a>
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => void kopieren()}>
              <Link2 /> Link kopieren
            </Button>
          </div>
          <p className="mt-3 text-[12px] leading-snug text-muted-foreground">{umfang}</p>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11.5px] text-muted-foreground">
            <span>Aktualisiert sich alle paar Stunden von selbst.</span>
            <button type="button" disabled={rotate.isPending}
              className="inline-flex items-center gap-1 font-medium text-primary hover:underline disabled:opacity-50"
              onClick={() => {
                if (window.confirm("Neue Kalender-Adresse erzeugen? Die bisherige hört auf zu funktionieren – jeder Kalender, der sie abonniert hat, bekommt dann keine Termine mehr.")) {
                  rotate.mutate();
                }
              }}>
              <RefreshCw className={"h-3 w-3" + (rotate.isPending ? " animate-spin" : "")} aria-hidden /> Neue Adresse
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function AbosView() {
  const qc = useQueryClient();

  const gremienQuery = useQuery({
    queryKey: ["committees"],
    queryFn: () => api.get<{ committees: string[]; details?: CommitteeDetail[] }>("/council/committees"),
  });

  const subsQuery = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => vertrag.get("/subscriptions").then((d) => d.subscriptions),
  });

  /* Welches Gremium gerade läutet. Nur beim Abonnieren, nicht beim Abbestellen
     — die Bewegung feiert die Zusage, und eine Glocke beim Abschalten hieße
     das Gegenteil von dem, was gerade passiert. */
  const [laeutet, setLaeutet] = useState<string | null>(null);
  useEffect(() => {
    if (!laeutet) return;
    const t = setTimeout(() => setLaeutet(null), 950);
    return () => clearTimeout(t);
  }, [laeutet]);

  const subMutation = useMutation({
    mutationFn: ({ committee, subscribed }: { committee: string; subscribed: boolean }) =>
      subscribed
        ? api.del("/subscriptions", { committee_name: committee })
        : api.post("/subscriptions", { committee_name: committee }),
    onSuccess: (_daten, { committee, subscribed }) => {
      if (!subscribed) setLaeutet(committee);
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
    },
    onError: () => toast.error("Abo konnte nicht geändert werden."),
  });

  const HEADER_DESC =
    "Benachrichtigungen, sobald ein Gremium eine Tagesordnung veröffentlicht — "
    + "und noch einmal, wenn sie sich danach ändert.";

  if (gremienQuery.isPending) {
    return (
      <div>
        <PageHeader title="Ausschuss-Abos" description={HEADER_DESC} />
        <div className="mt-6"><CardListSkeleton rows={4} /></div>
      </div>
    );
  }
  if (gremienQuery.isError) {
    return (
      <div>
        <PageHeader title="Ausschuss-Abos" description={HEADER_DESC} />
        <div className="mt-6">
          <ErrorState title="Die Gremien kamen nicht durch"
            onRetry={() => void gremienQuery.refetch()} busy={gremienQuery.isFetching} />
        </div>
      </div>
    );
  }

  const namen = Array.isArray(gremienQuery.data?.committees) ? gremienQuery.data.committees : [];
  const details = Array.isArray(gremienQuery.data?.details) ? gremienQuery.data!.details! : [];
  const abos = Array.isArray(subsQuery.data) ? subsQuery.data : [];

  /* Aus den Namen die Liste bauen, nicht aus `details`: Ein älteres Backend
     (native App auf altem Stand gegen neues Web, oder umgekehrt) liefert die
     Zusatzangaben noch nicht — dann fehlen Termin und Zahl, die Seite steht
     aber vollständig. */
  const perName = new Map(details.map((d) => [d.name, d]));
  const alle: CommitteeDetail[] = namen.map((n) =>
    perName.get(n) ?? { name: n, next_date: null, next_time: null, decisions_year: 0 });

  // Alltagsbezug zuerst, wie im Einrichtungs-Assistenten (Design 28a/R3).
  const sortiert = alle.slice().sort((a, b) =>
    committeeRank(a.name) - committeeRank(b.name)
    || shortCommittee(a.name).localeCompare(shortCommittee(b.name), "de"));

  const anzahlAbos = sortiert.filter((d) => abos.includes(d.name)).length;

  const toggle = (name: string, subscribed: boolean) =>
    subMutation.mutate({ committee: name, subscribed });

  return (
    <div className="@container">
      <PageHeader title="Ausschuss-Abos" description={HEADER_DESC} />

      <KalenderAboKarte anzahlAbos={anzahlAbos} />

      {/* EINE Liste, nicht zwei nach Abo-Status getrennte. Getrennt sprang das
          Gremium beim Abonnieren in die obere Liste, und alles darunter
          verschob sich — man verlor die Stelle, an der man gerade war, und
          traf beim zweiten Klick etwas anderes (Tim, 28.08.2026). Die
          Reihenfolge hängt jetzt nur am Alltagsbezug und ändert sich durch
          einen Klick nie; dass etwas abonniert ist, sagt der Knopf. */}
      <div className="mt-7 flex items-baseline justify-between gap-3 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        <span>Gremien ({sortiert.length})</span>
        <span>{anzahlAbos} abonniert</span>
      </div>
      {/* Zwei Spalten, sobald das Blatt 576 px hergibt (Container-Query, nicht
          Fensterbreite — DESIGNSPRACHE §4), genau wie im Einrichtungs-
          Assistenten: Sechzehn Kacheln untereinander wären eine Reise, neben-
          einander sind sie ein Überblick. */}
      <div className="mt-2 grid gap-2 @xl:grid-cols-2">
        {sortiert.map((d) => {
          const abonniert = abos.includes(d.name);
          return (
            <Kachel key={d.name} d={d} abonniert={abonniert}
              onToggle={() => toggle(d.name, abonniert)} busy={subMutation.isPending}
              laeutet={laeutet === d.name} />
          );
        })}
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-muted/60 px-4 py-3.5">
        <p className="text-[13.5px] text-muted-foreground">
          Nur ein bestimmtes Anliegen verfolgen? Lege dafür ein Thema an — wir durchsuchen jede neue Sitzung danach.
        </p>
        <Link href="/topics" className="whitespace-nowrap text-[13px] font-medium text-primary hover:underline">
          Zu Meinen Themen →
        </Link>
      </div>
    </div>
  );
}
