/**
 * Öffentliche Ansicht einer geteilten „Frag den Rat"-Antwort (Task 31):
 * ratslotse.de/g?t=<token> zeigt EXAKT die Antwort, die geteilt wurde.
 *
 * Server-Komponente mit dynamischer Metadata (Task 31b): Messenger-Crawler
 * (WhatsApp, Signal, Slack …) lesen og:title/description aus dem initialen
 * HTML ohne JavaScript — deshalb passiert der Snapshot-Fetch hier auf dem
 * Server. Im MOBILE-Export existiert diese Route nicht (build-mobile.mjs
 * stasht app/g wie app/api): geteilte Links öffnen immer im Browser.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { BrandMark } from "@/components/brand";
import { ShareAktionen } from "@/components/share-aktionen";
import {
  AnlagenBlock, DebattenBlock, GeteilterAntwortText, ParteienListe, PresseBlock,
  type AnlagenHinweis, type DebattenHinweis, type ParteiMeinung, type PresseHinweis,
} from "@/components/qa-bausteine";
import { anlagenBuchstaben } from "@/lib/qa-belege";

export const dynamic = "force-dynamic";

type ShareQuelle = {
  id: number; title: string;
  session_date: string | null; committee: string | null; outcome: string | null;
};
type Share = {
  question: string; answer: string; sources: ShareQuelle[]; created: string;
  /** Bausteine neben den Beschlüssen — vor dem Nachtrag geteilte Antworten
   *  haben sie nicht, dann bleiben die Listen leer. */
  debatten?: DebattenHinweis[]; presse?: PresseHinweis[];
  anlagen?: AnlagenHinweis[]; parteien?: ParteiMeinung[];
};

// Server-seitig direkt ans Backend (gleiche env wie der /api-Rewrite).
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

async function ladeShare(token: string): Promise<Share | null> {
  if (!token || token.length > 64) return null;
  try {
    const r = await fetch(`${BACKEND}/api/council/qa-share/${encodeURIComponent(token)}`,
      { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as Share;
  } catch {
    return null;
  }
}

function fmtDatum(iso: string | null | undefined): string {
  if (!iso || iso.length < 10) return "";
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}`;
}

type PageProps = { searchParams: Promise<{ t?: string }> };

export async function generateMetadata({ searchParams }: PageProps): Promise<Metadata> {
  const { t } = await searchParams;
  const share = await ladeShare(t ?? "");
  if (!share) {
    return { title: "Geteilte Antwort – Ratslotse", robots: { index: false } };
  }
  // V-08: Der geteilte Link ist das Schaufenster für Leute, die Ratslotse
  // noch nicht kennen — die Vorschau zeigt deshalb die FRAGE als Titel (nicht
  // den App-Namen) und als Text den ersten ganzen Satz der Antwort statt
  // eines Schnipsels, der mitten im Wort endet.
  // Zitatmarker putzen — „[8677]" sagt Empfängern nichts.
  const sauber = share.answer.replace(/\[[^\]\n]{1,160}\]/g, "").replace(/\s+/g, " ").trim();
  const ersterSatz = (sauber.match(/^.*?[.!?](?=\s|$)/)?.[0] ?? "").trim();
  const beschreibung = (ersterSatz.length >= 40 && ersterSatz.length <= 200
    ? ersterSatz
    : sauber.slice(0, 160).replace(/\s+\S*$/, "") + (sauber.length > 160 ? " …" : ""));
  const title = share.question.trim() || "Frag den Rat";
  const bild = { url: "/og-teilen.png", width: 1200, height: 630, alt: "Ratslotse — Frag den Rat" };
  return {
    title: `${title} – Ratslotse`,
    description: beschreibung,
    robots: { index: false }, // geteilte Inhalte nicht in Suchmaschinen sammeln
    openGraph: {
      title: title, description: beschreibung, siteName: "Ratslotse", type: "article",
      images: [bild],
    },
    twitter: { card: "summary_large_image", title: title, description: beschreibung,
      images: [bild.url] },
  };
}

export default async function GeteiltPage({ searchParams }: PageProps) {
  const { t } = await searchParams;
  const share = await ladeShare(t ?? "");
  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-4 py-8">
      <div className="flex items-center justify-between gap-3">
        <Link href="/" className="flex items-center gap-2">
          <BrandMark className="h-7 w-7" />
          <span className="font-display text-lg font-bold tracking-tight">Ratslotse</span>
        </Link>
        <Link href="/fragen"
          className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          <Sparkles className="h-3.5 w-3.5" aria-hidden /> Selbst den Rat fragen
        </Link>
      </div>
      {!share ? (
        <div className="mt-10 rounded-2xl border border-border bg-card p-6 text-center">
          <p className="font-semibold">Diese geteilte Antwort gibt es nicht mehr.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Der Link ist abgelaufen oder wurde gelöscht — du kannst dem Rat die Frage selbst stellen.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-8 ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md border border-primary/20 bg-primary/5 px-4 py-2.5 text-[15px]">
            {share.question}
          </div>
          <div className="mt-4 whitespace-pre-wrap text-[14.5px] leading-[1.7] text-foreground sm:leading-[1.75]">
            <GeteilterAntwortText text={share.answer} quellenIds={share.sources.map((q) => q.id)}
              anlagen={share.anlagen} />
          </div>
          {/* RG-09: Die verdichteten Fraktions-Positionen gehören zur Antwort —
              im Gespräch stehen sie direkt unter dem Text, hier genauso. */}
          {(share.parteien?.length ?? 0) >= 2 && (
            <div className="mt-4">
              <ParteienListe parteien={share.parteien ?? []} />
            </div>
          )}
          {share.sources.length > 0 && (
            <div className="mt-6 rounded-xl border border-border bg-card p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                Zitierte Beschlüsse
              </p>
              <ol className="mt-2 space-y-1.5">
                {share.sources.map((q, i) => (
                  <li key={q.id} id={`source-${i + 1}`} className="flex items-baseline gap-2 text-[13px]">
                    <span className="inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded bg-primary/10 px-0.5 text-[10px] font-bold text-primary">{i + 1}</span>
                    <span className="min-w-0 flex-1">
                      <Link href={`/council/decision?id=${q.id}`} className="hover:underline">{q.title}</Link>
                      <span className="ml-1.5 font-mono text-[10.5px] text-muted-foreground">
                        {[fmtDatum(q.session_date), q.committee].filter(Boolean).join(" · ")}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {/* Dieselben Belege-Bausteine wie im Gespräch (Reihenfolge dort:
              Debatten, Anlagen, Presse) — Externes gestrichelt gerahmt. */}
          {((share.debatten?.length ?? 0) > 0 || (share.anlagen?.length ?? 0) > 0
            || (share.presse?.length ?? 0) > 0) && (
            <div className="mt-3.5 flex flex-col gap-3.5">
              {(share.debatten?.length ?? 0) > 0 && <DebattenBlock debatten={share.debatten ?? []} />}
              {(share.anlagen?.length ?? 0) > 0 && (
                <AnlagenBlock anlagen={share.anlagen ?? []} ankerPrefix="anlage"
                  buchstaben={anlagenBuchstaben(share.answer, share.anlagen)} />
              )}
              {(share.presse?.length ?? 0) > 0 && <PresseBlock presse={share.presse ?? []} />}
            </div>
          )}
          <ShareAktionen token={t ?? ""} />
          <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground/80">
            Automatische Antwort von „Frag den Rat" auf ratslotse.de, geteilt am {fmtDatum(share.created)} —
            Stand des Ratsinformationssystems zu diesem Zeitpunkt. Kann unvollständig sein; Quellen prüfen.
          </p>
        </>
      )}
    </main>
  );
}
