"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Button, Card, EmptyState, Input } from "@/components/ui";

/** 404 **innerhalb** der App (Design 29a, P5).
 *
 *  `app/not-found.tsx` ganz außen wirft aus der Anwendung heraus: keine
 *  Navigation, keine Suche, kein Weg zurück außer dem Browser-Pfeil. Wer einem
 *  alten Link aus einer E-Mail folgt — etwa auf einen inzwischen
 *  zusammengeführten Beschluss —, steht damit vor einer nackten Seite.
 *
 *  Diese hier erbt die App-Hülle automatisch (Sidebar, Topbar, Bottom-Nav) und
 *  macht aus der Sackgasse einen Einstieg. Ausgelöst wird sie von den
 *  Detailseiten per `notFound()`, sobald die API den Datensatz nicht kennt.
 */

/** Wonach gesucht wurde, steht im Pfad — so bleibt die Meldung konkret,
 *  obwohl alle Detailseiten dieselbe Seite benutzen. */
const NOMEN: [test: RegExp, satz: string][] = [
  [/^\/council\/decision/, "Diesen Beschluss finde ich nicht"],
  [/^\/council\/person/, "Dieses Ratsmitglied finde ich nicht"],
  [/^\/council\/thema/, "Dieses Thema finde ich nicht"],
];

export default function AppNotFound() {
  const router = useRouter();
  const pfad = usePathname();
  const [q, setQ] = useState("");

  const titel = NOMEN.find(([re]) => re.test(pfad ?? ""))?.[1] ?? "Diesen Inhalt finde ich nicht";

  const suchen = (e: React.FormEvent) => {
    e.preventDefault();
    const ziel = q.trim();
    router.push(ziel ? `/council?q=${encodeURIComponent(ziel)}` : "/council");
  };

  return (
    <div className="mx-auto max-w-xl py-6">
      <EmptyState
        mascot="confused"
        title={titel}
        hint="Vielleicht wurde er zusammengeführt oder die Adresse hat sich geändert. Die Suche findet ihn meist trotzdem."
      />
      <Card className="mt-4 p-4">
        <form onSubmit={suchen} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="pl-9"
              placeholder="Stattdessen suchen …"
              aria-label="In den Beschlüssen suchen"
              enterKeyHint="search"
            />
          </div>
          <Button type="submit">Suchen</Button>
        </form>
      </Card>
    </div>
  );
}
