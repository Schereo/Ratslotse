"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Button, Card, EmptyState, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";

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
 *  obwohl alle Detailseiten dieselbe Seite benutzen.
 *
 *  Der Hinweis gehört mit in die Tabelle: Er stand früher als ein fester Satz
 *  daneben („Vielleicht wurde **er** zusammengeführt … findet **ihn** meist")
 *  und passte damit nur zum Beschluss. Bei „Dieses Thema" und „Dieses
 *  Ratsmitglied" war das schlicht falsches Deutsch — und Ratsmitglieder werden
 *  ohnehin nicht zusammengeführt. */
const NOMEN: [test: RegExp, titel: string, hinweis: string][] = [
  [/^\/council\/decision/, "Diesen Beschluss finde ich nicht",
   "Vielleicht hat sich die Adresse geändert. Über die Suche findest du ihn meist trotzdem."],
  [/^\/council\/person/, "Dieses Ratsmitglied finde ich nicht",
   "Vielleicht ist der Name anders geschrieben oder die Person sitzt nicht mehr im Rat."],
  [/^\/council\/thema/, "Dieses Thema finde ich nicht",
   "Vielleicht wurde es mit einem anderen zusammengeführt oder die Adresse hat sich geändert."],
];

const FALLBACK: [string, string] = [
  "Diesen Inhalt finde ich nicht",
  "Vielleicht hat sich die Adresse geändert.",
];

export default function AppNotFound() {
  const router = useRouter();
  const pfad = usePathname();
  const { user } = useAuth();
  const [q, setQ] = useState("");

  const treffer = NOMEN.find(([re]) => re.test(pfad ?? ""));
  const [titel, hinweis] = treffer ? [treffer[1], treffer[2]] : FALLBACK;

  const suchen = (e: React.FormEvent) => {
    e.preventDefault();
    const ziel = q.trim();
    router.push(ziel ? `/council?q=${encodeURIComponent(ziel)}` : "/council");
  };

  return (
    <div className="mx-auto max-w-xl py-6">
      <EmptyState mascot="confused" title={titel} hint={hinweis} />
      {/* Die Suche gibt es nur für Angemeldete: `/council` verlangt ein Konto,
          Gästen (geteilter Link auf einen gelöschten Beschluss) hätte der Knopf
          also bloß die Anmeldewand vorgesetzt — eine Sackgasse hinter der
          nächsten. Für sie steht hier, was die App überhaupt ist. */}
      {user ? (
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
      ) : (
        <Card className="mt-4 p-4 text-center">
          <p className="text-sm text-muted-foreground">
            Ratslotse macht die Arbeit des Oldenburger Stadtrats durchsuchbar und
            verständlich.
          </p>
          <Button asChild className="mt-3">
            <Link href="/">Zur Startseite</Link>
          </Button>
        </Card>
      )}
    </div>
  );
}
