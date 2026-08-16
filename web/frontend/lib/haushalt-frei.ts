// Umgebungs-Gate des Haushalts-Bereichs.
//
// Der Bereich ist nur auf dev.ratslotse.de freigeschaltet (Basic-Auth vorm
// vhost). Nur der Dev-Build setzt NEXT_PUBLIC_RATSLOTSE_ENV=dev
// (deploy-dev.yml); überall sonst ist die Konstante false, das Layout ruft
// notFound() und die Seiten rendern nicht — der Code darf deshalb gefahrlos
// mit Releases nach main fahren.
//
// Eine Einschränkung, gemessen statt vermutet: Der Bereich liegt unter
// app/(app)/, dessen Layout „use client" ist, und alle siebzehn Seiten sind
// selbst Client-Komponenten. Das notFound() im Haushalts-Layout wird zwar
// ausgeführt (nachgewiesen: HAUSHALT_FREI=false, der Aufruf greift), aber
// Next liefert die Antwort mit HTTP 200 statt 404 aus — ein „Soft 404".
// Inhaltlich ist das folgenlos, für Suchmaschinen unsauber; /haushalt steht
// deshalb ohnehin nicht in der Sitemap. Die Kommunalwahl hat das Problem
// nicht, weil ihre Seiten Server-Komponenten außerhalb von (app) sind.
// Eine Middleware wäre der übliche Weg zum echten 404 — sie wird in diesem
// Projekt aber nicht ausgeführt (auch nicht mit Matcher „/:path*"), das ist
// ungeklärt und wäre eigene Arbeit.
//
// Die Konstante steht hier statt im Layout, weil sie an drei Orten gebraucht
// wird: im Layout selbst (die siebzehn Seiten), in der Navigation (Sidebar +
// „Mehr"-Sheet) und auf den Beschluss-Seiten (Anschlussstelle H-21). Ein Gate
// ohne die Einstiegspunkte wäre nur die halbe Miete — die Links stünden auf
// Prod weiter da und führten ins Leere. Genau diese Falle gab es schon einmal
// bei der Kommunalwahl-Metadata.
//
// Nicht abgedeckt und auch nicht nötig: Auf Prod laufen weder die
// Ingest-Skripte noch der Cron `check_finanzdaten` — die Haushalts-Tabellen
// entstehen dort leer und bleiben es. Die API-Routen unter /council/haushalt/*
// antworten entsprechend leer statt falsch.
export const HAUSHALT_FREI = process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev";
