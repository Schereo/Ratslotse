"use client";

// Live-Prüfung der Programm-Quelle: Führt der Partei-Link noch zu genau der
// Datei, die ausgewertet wurde? Das Backend vergleicht die Prüfsumme
// (/api/kommunalwahl/quelle/{slug}, 24-h-Cache) — hier wird das Ergebnis in
// Alltagssprache übersetzt. Kein „SHA256", kein „Hash": Wer das Detail will,
// findet es auf der Methodikseite.

import { useEffect, useState } from "react";
import { apiBase } from "@/lib/platform";

type Status = "laeuft" | "unveraendert" | "veraendert" | "nicht_erreichbar";

export function QuellenCheck({ slug, stand }: { slug: string; stand: string }) {
  const [status, setStatus] = useState<Status>("laeuft");

  useEffect(() => {
    let aktiv = true;
    fetch(`${apiBase()}/api/kommunalwahl/quelle/${slug}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: { status: Status }) => aktiv && setStatus(d.status))
      .catch(() => aktiv && setStatus("nicht_erreichbar"));
    return () => {
      aktiv = false;
    };
  }, [slug]);

  if (status === "laeuft") {
    return (
      <p className="text-xs text-muted-foreground" aria-live="polite">
        <span className="mr-1.5 inline-block h-2 w-2 animate-pulse rounded-full bg-muted-foreground/40 align-middle" />
        Wir prüfen gerade, ob hinter dem Link noch dasselbe Programm steht …
      </p>
    );
  }
  if (status === "unveraendert") {
    return (
      <p className="text-xs text-emerald-800 dark:text-emerald-300" aria-live="polite">
        <span aria-hidden className="mr-1 font-bold">✓</span>
        Geprüft: Der Link führt noch zu genau dem Programm, das wir ausgewertet haben.
      </p>
    );
  }
  if (status === "veraendert") {
    return (
      <p className="max-w-[52ch] text-xs leading-relaxed text-amber-800 dark:text-amber-300" aria-live="polite">
        <span aria-hidden className="mr-1 font-bold">!</span>
        Die Partei hat die Datei hinter dem Link verändert, seit wir sie ausgewertet haben. Unsere
        Auswertung bezieht sich auf den Stand vom {stand}.
      </p>
    );
  }
  return (
    <p className="text-xs text-muted-foreground" aria-live="polite">
      Ob der Link noch dieselbe Datei liefert, ließ sich gerade nicht prüfen.
    </p>
  );
}
