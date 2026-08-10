"use client";

/**
 * Öffentliche Ansicht einer geteilten „Frag den Rat"-Antwort (Task 31):
 * ratslotse.de/g?t=<token> zeigt EXAKT die Antwort, die geteilt wurde —
 * der alte ?q=-Link ließ Empfänger die Frage neu ausführen und eine andere
 * Antwort sehen. Query-Param statt Pfad-Segment wegen des statischen
 * Exports (Capacitor), useSearchParams deshalb hinter Suspense.
 */
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Sparkles } from "lucide-react";
import { BrandMark } from "@/components/brand";
import { apiUrl } from "@/lib/api";

type ShareQuelle = {
  id: number; title: string;
  session_date: string | null; committee: string | null; outcome: string | null;
};
type Share = { frage: string; antwort: string; quellen: ShareQuelle[]; created: string };

function fmtDatum(iso: string | null | undefined): string {
  if (!iso || iso.length < 10) return "";
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}`;
}

/** [id]-Zitatmarker der gespeicherten Antwort → hochgestellte Fußnoten,
 *  nummeriert nach der Reihenfolge der gespeicherten Quellen. */
function AntwortMitFussnoten({ text, quellen }: { text: string; quellen: ShareQuelle[] }) {
  const idZuNum = useMemo(() => {
    const m = new Map<number, number>();
    quellen.forEach((q, i) => m.set(q.id, i + 1));
    return m;
  }, [quellen]);
  const absaetze = text.split(/\n{2,}/);
  return (
    <div className="space-y-3">
      {absaetze.map((abs, ai) => (
        <p key={ai} className="text-[15px] leading-relaxed text-foreground/90">
          {abs.split(/(\[[^\]\n]{1,160}\])/).map((teil, ti) => {
            if (!/^\[[^\]\n]+\]$/.test(teil)) return <span key={ti}>{teil}</span>;
            const nums = [...teil.matchAll(/\d+/g)]
              .map((m) => idZuNum.get(Number(m[0])))
              .filter((n): n is number => n != null);
            if (nums.length === 0) return null; // unzitierte Marker still schlucken
            return nums.map((n, ni) => (
              <a key={`${ti}-${ni}`} href={`#quelle-${n}`}
                className="mx-px inline-flex h-4 min-w-4 items-center justify-center rounded bg-primary/10 px-0.5 align-super text-[10px] font-bold text-primary no-underline">
                {n}
              </a>
            ));
          })}
        </p>
      ))}
    </div>
  );
}

function GeteilteAntwort() {
  const token = useSearchParams().get("t") ?? "";
  const [share, setShare] = useState<Share | null>(null);
  const [zustand, setZustand] = useState<"laden" | "fertig" | "fehlt">("laden");
  useEffect(() => {
    if (!token) { setZustand("fehlt"); return; }
    fetch(apiUrl(`/council/qa-share/${encodeURIComponent(token)}`))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((b) => { setShare(b as Share); setZustand("fertig"); })
      .catch(() => setZustand("fehlt"));
  }, [token]);

  if (zustand === "laden") {
    return (
      <div aria-hidden className="mt-8 space-y-3">
        {[92, 88, 60].map((w, i) => (
          <div key={i} className="h-3.5 animate-pulse rounded bg-muted" style={{ width: `${w}%` }} />
        ))}
      </div>
    );
  }
  if (zustand === "fehlt" || !share) {
    return (
      <div className="mt-10 rounded-2xl border border-border bg-card p-6 text-center">
        <p className="font-semibold">Diese geteilte Antwort gibt es nicht mehr.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Der Link ist abgelaufen oder wurde gelöscht — du kannst dem Rat die Frage selbst stellen.
        </p>
      </div>
    );
  }
  return (
    <>
      <div className="mt-8 ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md border border-primary/20 bg-primary/5 px-4 py-2.5 text-[15px]">
        {share.frage}
      </div>
      <div className="mt-4">
        <AntwortMitFussnoten text={share.antwort} quellen={share.quellen} />
      </div>
      {share.quellen.length > 0 && (
        <div className="mt-6 rounded-xl border border-border bg-card p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            Zitierte Beschlüsse
          </p>
          <ol className="mt-2 space-y-1.5">
            {share.quellen.map((q, i) => (
              <li key={q.id} id={`quelle-${i + 1}`} className="flex items-baseline gap-2 text-[13px]">
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
      <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground/80">
        Automatische Antwort von „Frag den Rat" auf ratslotse.de, geteilt am {fmtDatum(share.created)} —
        Stand des Ratsinformationssystems zu diesem Zeitpunkt. Kann unvollständig sein; Quellen prüfen.
      </p>
    </>
  );
}

export default function GeteiltPage() {
  return (
    <main className="mx-auto min-h-dvh w-full max-w-2xl px-4 py-8">
      <div className="flex items-center justify-between gap-3">
        <Link href="/" className="flex items-center gap-2">
          <BrandMark className="h-7 w-7" />
          <span className="font-display text-lg font-bold tracking-tight">Ratslotse</span>
        </Link>
        <Link href="/council?tab=decisions&mode=fragen"
          className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          <Sparkles className="h-3.5 w-3.5" aria-hidden /> Selbst den Rat fragen
        </Link>
      </div>
      <Suspense fallback={null}>
        <GeteilteAntwort />
      </Suspense>
    </main>
  );
}
