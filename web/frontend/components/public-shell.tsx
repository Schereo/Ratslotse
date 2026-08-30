"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Mascot } from "@/components/mascot";
import { Button, Card } from "@/components/ui";
import { mitRuecksprung } from "@/lib/public-routes";

/** Die Hülle für alle, die ohne Konto hier gelandet sind — praktisch immer über
 *  einen geteilten Link.
 *
 *  Bewusst nicht die App-Hülle mit ausgegrauter Navigation: Deren Ziele
 *  (Dashboard, meine Themen, Quiz) verlangen alle ein Konto, eine Leiste voller
 *  gesperrter Punkte wäre eine Wand aus Absagen. Was bleibt, ist der Inhalt,
 *  ein Weg hinein und am Ende eine Einladung — in dieser Reihenfolge, denn wer
 *  gerade erst liest, weiß noch gar nicht, wofür sich ein Konto lohnen würde.
 */
export function PublicShell({ children }: { children: React.ReactNode }) {
  // Erst nach dem Mounten lesbar; `useSearchParams` würde die Seite in eine
  // Suspense-Grenze zwingen und den statischen Export (MOBILE=1) brechen.
  const [zurueck, setZurueck] = useState("/dashboard");
  useEffect(() => {
    setZurueck(window.location.pathname + window.location.search);
  }, []);

  return (
    <div className="flex min-h-[100dvh] flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Zum Inhalt springen
      </a>

      {/* Ebene „huelle" — dieselbe Stufe wie Kopfzeile und Tab-Leiste der
          App-Hülle; die Leiter steht in app/globals.css. */}
      <header className="sticky top-0 z-[var(--ebene-huelle)] border-b border-border bg-card/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl items-center gap-3 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <Image src="/icon-192.png" alt="" width={32} height={32} className="h-8 w-8 rounded-lg" priority />
            <span className="font-display text-lg font-bold text-foreground">Ratslotse</span>
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link href={mitRuecksprung("/login", zurueck)}>Anmelden</Link>
            </Button>
            <Button asChild variant="signal" size="sm">
              <Link href={mitRuecksprung("/register", zurueck)}>Registrieren</Link>
            </Button>
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex flex-1 flex-col outline-none">
        <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          {children}
          <Einladung zurueck={zurueck} />
        </div>

        <footer className="border-t border-border bg-background/85 py-4 text-center text-xs text-muted-foreground">
          <Link href="/hilfe" className="hover:text-foreground">Hilfe</Link>
          {" · "}
          <Link href="/impressum" className="hover:text-foreground">Impressum</Link>
          {" · "}
          <Link href="/datenschutz" className="hover:text-foreground">Datenschutz</Link>
          {" · "}
          <Link href="/changelog" className="hover:text-foreground">Changelog</Link>
          {" · "}
          <Link href="/barrierefreiheit" className="hover:text-foreground">Barrierefreiheit</Link>
          <span className="mt-1.5 block px-4 text-balance">
            Ratslotse ist ein privates Bürgerprojekt und kein Angebot der Stadt Oldenburg.
          </span>
        </footer>
      </main>
    </div>
  );
}

/** Die Einladung steht am *Ende* der Seite, nicht davor.
 *
 *  Wer den Beschluss gelesen hat, weiß jetzt, worum es geht — das ist der
 *  Moment, in dem das Angebot etwas bedeutet. Deshalb nennt der Text auch
 *  konkret, was ein Konto bringt (eigene Themen, Meldung bei Tagesordnung und
 *  Ergebnis) statt allgemein für „alle Vorteile" zu werben, und die Grenzen
 *  gleich mit: Niemand soll sich anmelden und dann Post im Minutentakt fürchten.
 */
function Einladung({ zurueck }: { zurueck: string }) {
  return (
    <Card className="mt-8 overflow-hidden">
      <div className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:gap-6 sm:p-8">
        <Mascot pose="wave" decorative className="mx-auto h-24 w-24 shrink-0 sm:mx-0" />
        <div className="min-w-0 flex-1 text-center sm:text-left">
          <h2 className="font-display text-xl font-bold text-foreground">
            Willst du früher davon erfahren?
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Du liest gerade eine einzelne Seite aus dem Oldenburger Stadtrat. Mit
            einem kostenlosen Konto legst du eigene Themen an — Radverkehr, deine
            Schule, dein Stadtteil — und Ratslotse meldet sich, sobald sie auf
            einer Tagesordnung stehen oder entschieden sind. Höchstens zwei
            Nachrichten am Tag, zwischen 21 und 7 Uhr keine.
          </p>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button asChild variant="signal">
              <Link href={mitRuecksprung("/register", zurueck)}>Kostenlos registrieren</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href={mitRuecksprung("/login", zurueck)}>Ich habe schon ein Konto</Link>
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
