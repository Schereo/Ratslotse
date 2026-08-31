// <BelegChip> — der Pflicht-Slot jeder Grafik (GB-00, Regel 7 des Bereichs:
// jede Zahl trägt ihren Beleg).
//
// Bewusst KEINE eigene Implementierung: Der Chip existiert seit der ersten
// Haushalts-Runde als `Beleg` in `components/haushalt/source.tsx`, samt
// Quellenkontext (seitenweise Nummerierung), Popover mit Fundstelle und
// Ratsvorgang sowie Verzeichnis am Seitenfuß. Das hier ist nur die Tür des
// Baukastens zu genau diesem System — eine zweite Chip-Sorte wäre die
// Verwechslung, die niemand mehr auflöst.
//
// VERWENDUNG IN GRAFIKEN: Eine Grafik-Komponente nimmt den Chip als Slot
// entgegen (`beleg?: ReactNode`) und rendert ihn an ihrer Quellenzeile —
// welche Quelle gemeint ist, weiß die SEITE (sie kennt ihren
// `Quellenkontext`), nicht die Grafik:
//
//   <Zeitreihe … beleg={<BelegChip q="plan" />} />
//
// Mobil-Regel (H4-A): je Karte EIN Chip sichtbar, weitere hinter
// „Quellen (n)" im Karten-Fuß — „Bewusst nicht"-Chips und Lücken-Sätze
// werden NIE eingeklappt.

export {
  Beleg,
  Beleg as BelegChip,
  Quellenkontext,
  Quellenverzeichnis,
  Apparat,
} from "@/components/haushalt/source";
