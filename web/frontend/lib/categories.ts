// Human-readable labels for NWZ's raw section codes shown in the Rubrik filter
// and on result cards. Unknown codes fall back to the raw name (most NWZ
// Rubriken — "Oldenburg", "Sport", … — are already readable; only internal
// layout codes like "DS_Titel" need a nicer label).
const CATEGORY_LABELS: Record<string, string> = {
  Titelsei: "Titelseite",
  DS_Titel: "Titelseite",
  TitelSam: "Titelseite",
  TitelMo: "Titelseite",
  "Journal Titel": "Titelseite",
  DS_Lokal: "Lokales",
};

export function categoryLabel(raw: string): string {
  return CATEGORY_LABELS[raw] ?? raw;
}
