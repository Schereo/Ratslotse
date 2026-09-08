"use client";

import { Suspense, useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { meldeAufruf } from "@/lib/aufrufe-melden";
import { isNativeApp, clientMarke } from "@/lib/platform";
import { pfad } from "@/lib/utils";

/**
 * Zählt Seitenaufrufe — die einzige Stelle, an der das passiert.
 *
 * Hängt bewusst in der App-Hülle und nicht in einzelnen Seiten: Ein Zähler,
 * den jede neue Seite selbst einbauen muss, fehlt irgendwann auf der Hälfte
 * von ihnen, und die Lücke sieht aus wie „diese Seite wird nicht benutzt".
 *
 * `usePathname` liefert den Pfad OHNE Query — genau richtig, denn die Query
 * trägt hier alles Persönliche (`?id=`, `?q=`). Ein Filterklick, der nur die
 * Query ändert, erzeugt deshalb keinen zweiten Aufruf; das ist gewollt.
 *
 * **Eine Ausnahme: `?tab=` auf /council.** Suche, Sitzungen, Themen und
 * Analyse sind nicht vier Seiten, sondern eine mit vier Reitern. Ohne diesen
 * einen Parameter fielen die vier meistbenutzten Bereiche in eine Zeile
 * zusammen. Der Server nimmt ihn nur mit vier festen Werten an
 * (`kern/seitenaufrufe.py::COUNCIL_TABS`) und wirft jeden anderen Parameter
 * weg — ein Suchbegriff kommt auf diesem Weg nicht durch.
 *
 * Der Anmeldestatus geht als Ja/Nein mit, damit der Server für die Zählung
 * kein Konto auflösen muss (siehe `lib/aufrufe-melden.ts`). Solange der
 * Auth-Zustand noch lädt, wird nicht gemeldet — sonst stünde jeder erste
 * Aufruf einer angemeldeten Person als „anonym" in der Statistik.
 */
function ZaehlerInner() {
  const pathname = usePathname();
  const suchparameter = useSearchParams();
  const { user, loading } = useAuth();
  const tab = suchparameter?.get("tab") ?? "";

  useEffect(() => {
    if (loading) return;
    const p = pfad(pathname);
    const route = p === "/council" && tab ? `${p}?tab=${tab}` : p;
    meldeAufruf(route, Boolean(user), isNativeApp() ? clientMarke() : "web");
  }, [pathname, tab, user, loading]);

  return null;
}

/**
 * `useSearchParams` zwingt jede Seite, die es benutzt, in eine
 * Suspense-Grenze — und ohne eine solche bricht der statische Export
 * (`MOBILE=1`) beim Bauen ab. Weil dieser Zähler in der Wurzel-Hülle hängt,
 * beträfe das die GANZE App. Die Grenze steht deshalb hier, so eng wie
 * möglich um den Hook herum; der Fallback ist nichts, denn die Komponente
 * rendert ohnehin nichts.
 */
export function AufrufZaehler() {
  return (
    <Suspense fallback={null}>
      <ZaehlerInner />
    </Suspense>
  );
}
