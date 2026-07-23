"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ChevronDown, ChevronUp, ExternalLink, FileText, FileDown, Newspaper, Tag } from "lucide-react";
import { DecisionDetail, CouncilDecision } from "@/lib/types";
import { Card, DetailSkeleton, EmptyState, formatDate } from "@/components/ui";
import { OutcomeDot, OUTCOME_META, VoteBar, FieldBadge, PartyBadge, DecisionLinkCard, ImportanceMeter, formatEuro, normalizeParty, PartyAttendanceBadge } from "@/components/decision-ui";
import { decisionHref, themaHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { ShareButton } from "@/components/share-button";
import { nwzSearchUrl } from "@/components/nwz-link";
import { trackRecentDecision } from "@/lib/recent";
import { Mascot } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import { cn } from "@/lib/utils";
import { useFetch } from "@/lib/use-fetch";

function MetaCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold text-muted-foreground">{title}</h2>
      <div className="mt-2">{children}</div>
    </Card>
  );
}

/** Vorlagenart lesbar machen: Das RIS führt die alten Arten als
 *  „Beschlussvorlage (bis 31.12.2022)" — die Gültigkeits-Klammer ist ein
 *  Katalog-Detail und hat in einem erklärenden Satz nichts verloren. */
function vorlageArt(art: string | null | undefined): string {
  return (art || "").replace(/\s*\(bis[^)]*\)\s*$/, "").trim() || "Vorlage";
}

/** `subtitle` trägt den Fachbegriff, während die Überschrift in Alltagssprache
 *  sagt, was man hier liest — Ratsmitglieder finden den amtlichen Namen also
 *  weiterhin, ohne dass Erstbesucher:innen über ihn stolpern. */
function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-6">
      <h2 className="text-sm font-semibold text-muted-foreground">{title}</h2>
      {subtitle && <p className="text-xs text-muted-foreground/70">{subtitle}</p>}
      <div className={subtitle ? "mt-2" : "mt-2.5"}>{children}</div>
    </div>
  );
}

/** RL-904 / Design 25a: „Lotti erklärt's einfach" ist der **Aufmacher** der
 *  Seite — vorher stand die Amtssprache zuerst und die Kurzfassung darunter.
 *  Der amtliche Wortlaut bleibt verbindlich (siehe OfficialTextCard), rückt
 *  aber eine Position nach unten. */
function SimpleSummaryHero({ text }: { text: string }) {
  const theme = useMascotTheme();
  return (
    <div className="rounded-2xl border border-signal/30 bg-gradient-to-br from-signal/[0.07] to-transparent p-4 sm:p-5">
      <div className="flex items-center gap-2.5">
        <Mascot pose="point" theme={theme} decorative className="h-11 w-11 shrink-0" />
        <div className="min-w-0">
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-signal">
            Lotti erklärt&rsquo;s einfach
          </p>
          <p className="font-display text-base font-bold leading-tight text-foreground">Das Wichtigste in Kürze</p>
        </div>
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-foreground">{text}</p>
      <p className="mt-2.5 text-xs text-muted-foreground">
        KI-Kurzfassung — verbindlich ist der amtliche Wortlaut.
      </p>
    </div>
  );
}

/** Design 25a: Der amtliche Beschlusstext — verbindlich, aber sperrig. Er steht
 *  jetzt unter der Kurzfassung und lässt sich zuklappen. Bewusst **offen**
 *  voreingestellt: Was rechtlich gilt, versteckt man nicht hinter einem Klick;
 *  wer die Kurzfassung gelesen hat, klappt selbst zu. */
function OfficialTextCard({ text }: { text: string }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/50"
      >
        <span className="inline-flex flex-wrap items-center gap-x-1.5 text-[13px] font-semibold text-foreground">
          <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          Amtlicher Wortlaut
          <span className="font-normal text-muted-foreground">— aus dem Sitzungsprotokoll</span>
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      {open && (
        <div className="border-t border-border px-4 pb-4">
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{text}</p>
        </div>
      )}
    </div>
  );
}

/** Ein Feld innerhalb von „Auf einen Blick" — durch eine Linie vom vorigen
 *  getrennt, damit die gebündelten Werte nicht ineinanderlaufen. */
function GlanceRow({ label, first, children }: { label?: string; first?: boolean; children: React.ReactNode }) {
  return (
    <div className={first ? "" : "mt-3.5 border-t border-border pt-3.5"}>
      {label && (
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      )}
      {children}
    </div>
  );
}

/** Design 25a: Betrag, Abstimmung, Antrag von und Wichtigkeit lagen als vier
 *  einzelne Karten in der rechten Spalte — zusammen mit Dokumenten und
 *  Anwesenheit waren das sechs. Gebündelt sind es drei, und die Kennzahlen
 *  stehen dort, wo man sie zusammen liest. Inhaltlich unverändert; „Abstimmung"
 *  und „Betrag" erklären ihr Fehlen weiterhin, statt zu verschwinden. */
function GlanceCard({
  d,
  data,
  present,
  unanimous,
  className,
}: {
  d: CouncilDecision;
  data: DecisionDetail;
  present: number;
  unanimous: boolean;
  className?: string;
}) {
  const hasVote = d.outcome === "angenommen" || d.outcome === "abgelehnt" || !!d.vote;
  return (
    <Card className={cn("p-4", className)}>
      <h2 className="font-display text-sm font-bold text-foreground">Auf einen Blick</h2>

      <GlanceRow first label="Betrag">
        {d.amount_eur != null ? (
          <>
            <p className="mt-0.5 font-display text-[26px] font-extrabold leading-none tracking-tight text-signal">
              {formatEuro(d.amount_eur)}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">im Beschlusstext genannt (automatisch erkannt)</p>
          </>
        ) : (
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Im Beschlusstext wird kein Betrag genannt.
          </p>
        )}
      </GlanceRow>

      <GlanceRow label="Abstimmung">
        {hasVote ? (
          <div className="mt-1.5">
            <VoteBar d={d} presentCount={present || undefined} />
            {unanimous && data.present_parties.length > 0 && (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span className="w-full text-xs text-muted-foreground">Einstimmig — dafür stimmten:</span>
                {data.present_parties.map((p) => <PartyBadge key={p} party={p} />)}
              </div>
            )}
            {d.raw_result && (
              <p className="mt-2 text-xs italic text-muted-foreground">
                „{d.raw_result.replace(/^[-\s]+|[-\s]+$/g, "")}"
              </p>
            )}
          </div>
        ) : (
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Zu diesem Vorgang ist im Protokoll keine Abstimmung erfasst.
          </p>
        )}
      </GlanceRow>

      {d.parties.length > 0 && (
        <GlanceRow label="Antrag von">
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {d.parties.map((p) => <PartyBadge key={p} party={p} />)}
          </div>
        </GlanceRow>
      )}

      {d.kind !== "subvote" && data.importance_breakdown && (
        <GlanceRow>
          {/* ImportanceMeter bringt Kopfzeile, Balken und die aufklappbare
              Signal-Aufschlüsselung schon mit — hier ohne eigenen Rahmen, damit
              die Karte nicht doppelt umrandet wirkt. */}
          <ImportanceMeter
            className="border-0 p-0"
            score={data.importance_breakdown.score}
            signals={data.importance_breakdown.signals}
            contributions={data.importance_breakdown.contributions}
            baseScore={data.importance_breakdown.base_score}
            impact={data.importance_breakdown.impact}
            impactReason={data.importance_breakdown.impact_reason}
          />
        </GlanceRow>
      )}
    </Card>
  );
}

/** Kurze Ergebnis-Zeile aus vote/gegenstimmen/enthaltungen (z. B.
 *  „mehrheitlich · 18 dagegen · 2 Enth."). */
function voteSummary(d: CouncilDecision): string {
  const parts: string[] = [];
  if (d.vote) parts.push(d.vote);
  if (d.gegenstimmen) parts.push(`${d.gegenstimmen} dagegen`);
  if (d.enthaltungen) parts.push(`${d.enthaltungen} Enth.`);
  return parts.join(" · ");
}

/** Antragsart für den Kicker — rein am Titel erkannt, ohne den Text
 *  umzuschreiben. Fallback „Teilabstimmung", wenn nichts davon passt. */
const SUBVOTE_KINDS = [
  "Änderungsantrag", "Vertagungsantrag", "Verweisungsantrag", "Geschäftsordnungsantrag",
  "Dringlichkeitsantrag", "Ergänzungsantrag", "Zusatzantrag",
  "Antrag", // zuletzt: die zusammengesetzten Arten sollen zuerst greifen
] as const;

function subvoteKind(title: string | null | undefined): string {
  const t = (title ?? "").toLowerCase();
  return SUBVOTE_KINDS.find((k) => t.includes(k.toLowerCase())) ?? "Teilabstimmung";
}

/** Trägt der Titel eigenen Inhalt — oder sagt er nur, was der Kicker ohnehin
 *  schon zeigt („Änderungsantrag der SPD-Fraktion")? Entscheidet nur über
 *  anzeigen/verbergen; der Titel selbst wird nie beschnitten. In den echten
 *  Daten haben rund drei Viertel der Teilabstimmungen inhaltliche Titel.
 *  Ziffern zählen bewusst nicht als Inhalt, sonst genügte schon ein
 *  angehängtes Antragsdatum („… vom 22.06.2018") für den Kasten. */
function hasOwnContent(title: string | null | undefined, kind: string, factions: string[]): boolean {
  if (!title) return false;
  // Fraktionsnamen kommen im Titel oft leicht abweichend vor („Gruppe
  // Linke./Piraten" vs. „Gruppe Die Linke./Piratenpartei") — daher zusätzlich
  // jedes hinreichend lange Wort aus dem Fraktionsnamen einzeln entfernen.
  const factionWords = factions.flatMap((f) => f.split(/[^\p{L}]+/u).filter((w) => w.length >= 4));
  let rest = title.toLowerCase();
  for (const term of [kind, ...factions, ...factionWords, "fraktion", "gruppe", "geänderter", "antrag"]) {
    rest = rest.split(term.toLowerCase()).join(" ");
  }
  rest = rest
    .replace(/\b(der|des|die|von|vom|dem|den|und|am|ratsherr|ratsfrau|ratsherrn)\b/g, " ")
    .replace(/[^\p{L}]+/gu, ""); // Ziffern und Satzzeichen raus
  // Schwelle 6 (an den echten Daten geprüft): lässt knappe, aber echte Hinweise
  // durch („zu Pkten. 1.10 und 1.11", „(Absatz 3)", „zum Änderungsantrag der
  // CDU") und hält reine Antragsteller-Nennungen samt Datum draußen.
  return rest.length >= 6;
}

/** Abstand zwischen zwei Knoten beim Aufbau — knapp genug, dass die ganze
 *  Zeitachse in unter einer Sekunde steht. */
const TIMELINE_STEP_MS = 130;

/** Die Zeitachse baut sich beim Öffnen der Beschluss-Seite einmal auf: die
 *  Linie wächst nach unten, die Knoten erscheinen der Reihe nach. So sieht man
 *  die Reihenfolge — erst die Anträge, dann der endgültige Beschluss.
 *
 *  Bewusst am Mounten statt am Sichtbereich (IntersectionObserver) gekoppelt:
 *  ein Observer meldet in einem nicht gerenderten Dokument gar nichts, und dann
 *  bliebe echter Inhalt dauerhaft unsichtbar — auch im Ausdruck, den die
 *  Beschluss-Seiten ausdrücklich unterstützen. Der kurze Timeout lässt den
 *  Startzustand einmal malen (sonst fasst React beides zu einem Paint zusammen
 *  und der Übergang entfällt) und läuft auch im Hintergrund-Tab ab. Bei
 *  prefers-reduced-motion sofort im Endzustand — Idiom wie
 *  components/reveal.tsx. */
function useTimelineReveal() {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(true); return; }
    const id = setTimeout(() => setShown(true), 50);
    return () => clearTimeout(id);
  }, []);
  return shown;
}

/** Design 23a: „Anträge & Teilabstimmungen" als Zeitachse Änderung → Ergebnis.
 *  Jeder Änderungsantrag ist ein Knoten (Fraktion, Ergebnis, was beantragt
 *  wurde); den Abschluss bildet der endgültige Beschluss. Bewusst kein
 *  erfundener alt/neu-Diff — gezeigt wird nur, was in den Daten steht.
 *  Der Antragsinhalt steckt bei Teilabstimmungen in `title` (die Extraktion
 *  legt ihn dort ab, `beschluss` bleibt für sie leer). */
function SubvoteTimeline({ d, subVotes }: { d: CouncilDecision; subVotes: CouncilDecision[] }) {
  const shown = useTimelineReveal();
  // Die Linie begleitet alle Knoten (inkl. Endknoten) und läuft kurz nach.
  const lineMs = 240 + (subVotes.length + 1) * TIMELINE_STEP_MS;
  return (
    // border-transparent statt border-border: die sichtbare Linie ist das
    // animierte <span> darunter — die Kastengeometrie bleibt unverändert.
    <ol className="relative space-y-5 border-l-2 border-transparent pl-5">
      <span
        aria-hidden
        style={{ transitionDuration: `${lineMs}ms` }}
        className={cn(
          "absolute -left-0.5 top-0 h-full w-0.5 origin-top bg-border transition-transform ease-out-strong",
          shown ? "scale-y-100" : "scale-y-0",
        )}
      />
      {subVotes.map((s, i) => {
        const factions = Array.isArray(s.factions) ? s.factions : [];
        const kind = subvoteKind(s.title);
        const body = s.beschluss || (hasOwnContent(s.title, kind, factions) ? s.title : null);
        return (
          <li
            key={s.id}
            style={{ transitionDelay: `${i * TIMELINE_STEP_MS}ms` }}
            className={cn(
              "relative transition-[opacity,transform] duration-500 ease-out-strong",
              shown ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
            )}
          >
            <span
              style={{ transitionDelay: `${i * TIMELINE_STEP_MS + 80}ms` }}
              className={cn(
                "absolute -left-[26px] top-1 h-3.5 w-3.5 rounded-full border-2 border-card bg-signal transition-transform duration-300 ease-back-out",
                shown ? "scale-100" : "scale-0",
              )}
              aria-hidden
            />
            <p className="text-[11px] font-semibold uppercase tracking-wider text-signal">
              {kind}{factions.length > 0 ? ` · ${factions.join(", ")}` : ""}
            </p>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
              <OutcomeDot outcome={s.outcome} />
              {voteSummary(s) && <span>· {voteSummary(s)}</span>}
            </p>
            {body && (
              <div className="mt-2 rounded-lg border border-border bg-muted/40 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Was beantragt wurde</p>
                <p className="mt-1 text-sm leading-relaxed text-foreground">{body}</p>
              </div>
            )}
          </li>
        );
      })}
      {/* Abschluss: der endgültige Beschluss (Volltext steht oben im
          Beschlusstext-Block — hier nur Ergebnis + optionale Kurzfassung).
          Rastet als Letzter ein — das Ziel der Zeitachse. */}
      <li
        style={{ transitionDelay: `${subVotes.length * TIMELINE_STEP_MS}ms` }}
        className={cn(
          "relative transition-[opacity,transform] duration-500 ease-out-strong",
          shown ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
        )}
      >
        <span
          style={{ transitionDelay: `${subVotes.length * TIMELINE_STEP_MS + 80}ms` }}
          className={cn(
            "absolute -left-[26px] top-1 h-3.5 w-3.5 rounded-full border-2 border-card bg-[#22c55e] transition-transform duration-300 ease-back-out",
            shown ? "scale-100" : "scale-0",
          )}
          aria-hidden
        />
        <p className="text-[11px] font-semibold uppercase tracking-wider text-green-700 dark:text-green-400">Endgültiger Beschluss</p>
        <p className="mt-1 text-sm leading-relaxed text-foreground">
          {(OUTCOME_META[d.outcome ?? "kein_beschluss"]?.label ?? "Beschlossen")}
          {voteSummary(d) ? ` — ${voteSummary(d)}` : ""}
        </p>
        {d.summary && <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{d.summary}</p>}
      </li>
    </ol>
  );
}

function presentMembers(att: DecisionDetail["attendance"]): number {
  return att.filter((a) => a.role === "vorsitz" || a.role === "mitglied" || !a.role).length;
}

/** Design 25a: Nachbarbeschlüsse sind Kontext, keine Hauptsache — standardmäßig
 *  die zwei relevantesten, der Rest auf Klick. */
function SimilarList({ items }: { items: DecisionDetail["similar"] }) {
  const [all, setAll] = useState(false);
  const VISIBLE = 2;
  const shown = all ? items : items.slice(0, VISIBLE);
  const rest = items.length - shown.length;
  return (
    <div className="space-y-2">
      {shown.map((s) => (
        <DecisionLinkCard key={s.id} id={s.id} title={s.title} committee={s.committee}
          session_date={s.session_date} field={s.policy_field} score={s.score} />
      ))}
      {(rest > 0 || all) && (
        <button
          type="button"
          onClick={() => setAll((v) => !v)}
          aria-expanded={all}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-border px-3 py-2 text-xs font-medium text-primary transition-colors hover:bg-muted"
        >
          {all ? (
            <><ChevronUp className="h-3.5 w-3.5" />Weniger anzeigen</>
          ) : (
            <><ChevronDown className="h-3.5 w-3.5" />{rest} weitere anzeigen</>
          )}
        </button>
      )}
    </div>
  );
}

/** Sachverhalt/Begründung aus der eingelesenen Vorlage — eingeklappt auf wenige
 *  Zeilen, weil die Auszüge lang sein können. */
function VorlageExcerpt({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 420;
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className={cn("whitespace-pre-line text-sm leading-relaxed text-foreground", !open && long && "line-clamp-5")}>
        {text}
      </p>
      {long && (
        <button onClick={() => setOpen((o) => !o)} className="mt-2 text-xs font-medium text-primary hover:underline">
          {open ? "Weniger anzeigen" : "Mehr anzeigen"}
        </button>
      )}
    </div>
  );
}

function DecisionDetailInner() {
  const id = useSearchParams().get("id");
  const router = useRouter();
  const { data, loading } = useFetch<DecisionDetail>(id ? `/council/decision/${id}` : null);

  // Für „Zuletzt angesehen" (Dashboard) und die Command-Palette merken.
  useEffect(() => {
    const dec = data?.decision;
    if (dec) trackRecentDecision({ id: dec.id, title: dec.title ?? "Beschluss", committee: dec.committee, session_date: dec.session_date });
  }, [data]);

  if (loading) return <DetailSkeleton />;
  if (!data) return <EmptyState mascot="confused" title="Beschluss nicht gefunden" />;

  const d = data.decision;
  const unanimous = d.outcome === "angenommen"
    && (d.vote === "einstimmig" || ((d.gegenstimmen ?? 0) === 0 && (d.enthaltungen ?? 0) === 0));
  const present = presentMembers(data.attendance);
  const byParty: Record<string, number> = {};
  for (const a of data.attendance) {
    if (a.role === "verwaltung" || a.role === "protokoll" || a.role === "gast") continue;
    const p = normalizeParty(a.party || "—");
    byParty[p] = (byParty[p] ?? 0) + 1;
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="print-hidden flex items-center justify-between gap-3">
        <button onClick={() => router.back()} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Zurück
        </button>
        <ShareButton path={decisionHref(d.id)} title={d.title ?? "Beschluss des Oldenburger Stadtrats"} />
      </div>

      {/* RL-601: Statuszeile (Punkt+Wort · Gremium·Datum·TOP · Mono-Aktenzeichen
          · Wichtig-Chip), H1 32/700, darunter Dokument-Grid 1fr/300px. */}
      <div className="mt-3">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted-foreground">
          <OutcomeDot outcome={d.outcome} />
          <span title={d.committee}>
            {shortCommittee(d.committee)} · {formatDate(d.session_date)}
            {d.item_number ? ` · TOP ${d.item_number}` : ""}
          </span>
          {d.vorlage_nr && <span className="font-mono text-[11px]">{d.vorlage_nr}</span>}
          {d.kind !== "subvote" && (data.importance_breakdown?.score ?? 0) >= 55 && (
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-700 dark:text-amber-400">
              Wichtig · {data.importance_breakdown!.score}/100
            </span>
          )}
        </div>
        <h1 className="mt-1.5 hyphens-auto font-display text-2xl font-bold leading-tight text-foreground sm:text-[32px] sm:leading-10">
          {d.title}
        </h1>
        {(d.policy_field || d.policy_tags.length > 0) && (
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <FieldBadge field={d.policy_field} />
            {d.policy_tags.map((t) => (
              <span key={t} className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{t}</span>
            ))}
          </div>
        )}
        {data.entities.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {data.entities.map((e) => (
              <Link key={e.slug} href={themaHref(e.slug)}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs text-foreground transition-colors hover:bg-muted"
                title={`Alle Beschlüsse zu „${e.name}"`}>
                <Tag className="h-3 w-3 text-muted-foreground" />{e.name}
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        {/* Linke Spalte (25a): nur noch die inhaltliche Erzählung —
            Kurzfassung → amtlicher Wortlaut → Verlauf & Begründung → Nachbarn.
            Dokumente, Anwesenheit, Beratungsweg und Presse sind Metadaten und
            sitzen rechts. */}
        <div className="min-w-0 space-y-3">
          {d.simple_summary && <SimpleSummaryHero text={d.simple_summary} />}

          {d.beschluss && <OfficialTextCard text={d.beschluss} />}

          {/* Auf Mobil klappt das Grid zu einer Spalte — die Kennzahlen kämen
              dann erst hinter der ganzen Erzählung. Deshalb hier ein zweiter
              Platz, der nur unterhalb von lg sichtbar ist (display:none blendet
              die jeweils andere Instanz auch für Screenreader aus). */}
          <GlanceCard d={d} data={data} present={present} unanimous={unanimous} className="lg:hidden" />

          {/* 25a ③: Teilabstimmungen, Endergebnis und das Warum standen als drei
              getrennte Blöcke untereinander — zusammen erzählen sie den Hergang
              des Vorgangs und stehen deshalb unter einer Überschrift. */}
          {(data.sub_votes.length > 0 || data.vorlage?.excerpt) && (
            <Section title="Verlauf & Begründung">
              <div className="space-y-4">
                {data.sub_votes.length > 0 && <SubvoteTimeline d={d} subVotes={data.sub_votes} />}
                {/* Nicht der Beschlussvorschlag, sondern Sachverhalt/Begründung
                    aus der Verwaltungsvorlage (council/vorlagen.py excerpt) —
                    die Vorgeschichte, die im Beschlusstext nicht vorkommt. */}
                {data.vorlage?.excerpt && (
                  <div>
                    <p className="text-sm font-semibold text-foreground">Warum es dazu kam</p>
                    <p className="mb-2 text-xs text-muted-foreground/70">
                      Sachverhalt und Begründung aus der {vorlageArt(data.vorlage.art)} der Verwaltung
                    </p>
                    <VorlageExcerpt text={data.vorlage.excerpt} />
                  </div>
                )}
              </div>
            </Section>
          )}

          {data.similar.length > 0 && (
            <Section title={`Ähnliche Beschlüsse (${data.similar.length})`}>
              <SimilarList items={data.similar} />
            </Section>
          )}
        </div>

        {/* Rechte Spalte (25a): drei Karten statt sechs — „Auf einen Blick"
            bündelt Betrag/Abstimmung/Antrag/Wichtigkeit, „Dokumente & Anlagen"
            führt alle Datei-Links zusammen, dazu Anwesenheit. Beratungsweg und
            Presse sind ebenfalls Metadaten und schließen unten an. */}
        <aside className="space-y-4">
          <GlanceCard d={d} data={data} present={present} unanimous={unanimous} className="hidden lg:block" />

          <MetaCard title="Dokumente & Anlagen">
            <div className="flex flex-col gap-1">
              {data.vorlage_url && (
                <a href={data.vorlage_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
                  <FileText className="h-3.5 w-3.5" /> Vorlage {d.vorlage_nr}
                </a>
              )}
              {data.vorlage?.document_url && (
                <a href={data.vorlage.document_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
                  <FileDown className="h-3.5 w-3.5" /> Vorlage (PDF)
                </a>
              )}
              {d.protocol_url && (
                <a href={d.protocol_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
                  <FileDown className="h-3.5 w-3.5" /> Protokoll (PDF)
                </a>
              )}
              <a href={data.ratsinfo_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
                <ExternalLink className="h-3.5 w-3.5" /> Im Ratsinfo öffnen
              </a>
            </div>
            {/* 25a: Die Anlagen standen als eigener Abschnitt links. Datei-Links
                gehören sachlich zusammen — hier per Trennlinie abgesetzt. */}
            {(data.anlagen?.length ?? 0) > 0 && (
              <div className="mt-3 border-t border-border pt-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Anlagen zum Beschluss
                </p>
                <div className="mt-1.5 flex flex-col gap-1.5">
                  {data.anlagen!.map((an) => (
                    <a key={an.document_id} href={an.url ?? undefined} target="_blank" rel="noreferrer"
                      className="group flex items-center justify-between gap-2 rounded-lg border border-border px-2.5 py-1.5 text-sm transition-colors hover:bg-muted">
                      <span className="flex min-w-0 items-center gap-2">
                        <FileDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <span className="truncate text-foreground">{an.label || "Dokument"}</span>
                      </span>
                      {an.is_antrag === 1 && an.antragsteller.length > 0 && (
                        <span className="flex shrink-0 items-center gap-1">
                          {an.antragsteller.map((p) => <PartyBadge key={p} party={p} />)}
                        </span>
                      )}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </MetaCard>

          {Object.keys(byParty).length > 0 && (
            <MetaCard title={`Anwesenheit (${data.attendance.length})`}>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(byParty).sort((a, b) => b[1] - a[1]).map(([p, n]) => (
                  <PartyAttendanceBadge key={p} party={p} n={n} />
                ))}
              </div>
            </MetaCard>
          )}

          {(data.beratungsfolge && data.beratungsfolge.length > 0) || data.vorlage_journey.length > 1 ? (
            <MetaCard title={`Weg der Vorlage ${d.vorlage_nr ?? ""}`.trim()}>
              {/* Offizielle Beratungsfolge aus dem Ratsinfo: Ergebnis je Station,
                  geplante künftige Beratungen inklusive; sonst der aus unseren
                  eigenen Sitzungen rekonstruierte Weg. */}
              <div className="ml-1 flex flex-col gap-2.5 border-l-2 border-border pl-3.5">
                {data.beratungsfolge && data.beratungsfolge.length > 0
                  ? data.beratungsfolge.map((b, i) => {
                      const current = b.ksinr != null && b.ksinr === d.ksinr;
                      return (
                        <div key={`${b.ksinr ?? "x"}-${b.datum ?? i}-${b.gremium}`} className="relative">
                          <span className={cn(
                            "absolute -left-[19px] top-1.5 h-2 w-2 rounded-full",
                            current ? "bg-primary" : b.future ? "border border-primary/60 bg-background" : "bg-border",
                          )} />
                          <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
                            <span className={cn("text-[13px]", current ? "font-medium text-foreground" : "text-foreground")}
                              title={b.gremium}>
                              {shortCommittee(b.gremium)}
                            </span>
                            <span className="text-[11px] text-muted-foreground">
                              {b.datum ? formatDate(b.datum) : "Termin offen"}
                              {b.is_public === 0 && " · nichtöffentlich"}
                              {current && " · hier"}
                            </span>
                            {b.future ? (
                              <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">geplant</span>
                            ) : b.ergebnis ? (
                              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">{b.ergebnis}</span>
                            ) : null}
                          </div>
                        </div>
                      );
                    })
                  : data.vorlage_journey.map((stop) => {
                      const current = stop.ksinr === d.ksinr;
                      return (
                        <div key={`${stop.ksinr}-${stop.item_number}`} className="relative">
                          <span className={cn(
                            "absolute -left-[19px] top-1.5 h-2 w-2 rounded-full",
                            current ? "bg-primary" : "bg-border",
                          )} />
                          <span className={cn("text-[13px]", current && "font-medium text-foreground")} title={stop.committee}>
                            {shortCommittee(stop.committee)}
                          </span>
                          <span className="text-[11px] text-muted-foreground"> · {formatDate(stop.session_date)}{current ? " (hier)" : ""}</span>
                        </div>
                      );
                    })}
              </div>
            </MetaCard>
          ) : null}

          {d.title && (
            <MetaCard title="In der Presse">
              <a
                href={nwzSearchUrl(d.title)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
              >
                <Newspaper className="h-4 w-4 shrink-0" /> Bei NWZonline nach Berichten suchen
              </a>
            </MetaCard>
          )}
        </aside>
      </div>
    </div>
  );
}

export default function DecisionDetailPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <DecisionDetailInner />
    </Suspense>
  );
}
