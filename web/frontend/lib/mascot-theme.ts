/**
 * Was trägt Lotti heute? — Jahreszeiten- und Feiertags-Logik fürs Maskottchen.
 *
 * Rein und ohne React, damit es überall importierbar ist. Die Jahreszeit richtet
 * sich nach dem Monat (Nordhalbkugel); besondere Tage überschreiben die
 * Jahreszeit-Kleidung (z. B. Weihnachtsmütze statt Wintermütze).
 *
 * Wichtig: Bei statischem Export ist das Build-Datum ≠ Besuchsdatum. Deshalb wird
 * das Datum im `useMascotTheme`-Hook erst nach dem Mount clientseitig bestimmt —
 * serverseitig bleibt Lotti neutral (kein Hydration-Mismatch).
 */
export type Season = "spring" | "summer" | "autumn" | "winter";
export type Holiday = "pride" | "halloween" | "christmas" | "easter";

export interface MascotTheme {
  season: Season;
  /** Überschreibt die Jahreszeit-Kleidung, wenn gesetzt. */
  holiday: Holiday | null;
}

/** Meteorologische Jahreszeit nach Monat (0 = Januar … 11 = Dezember). */
export function seasonForMonth(month: number): Season {
  if (month <= 1 || month === 11) return "winter"; // Dez, Jan, Feb
  if (month <= 4) return "spring"; // Mär, Apr, Mai
  if (month <= 7) return "summer"; // Jun, Jul, Aug
  return "autumn"; // Sep, Okt, Nov
}

/**
 * Ostersonntag (gregorianisch) nach der „anonymen" Gauß-Formel.
 * Gibt Monat (1–12) und Tag zurück.
 */
export function easterSunday(year: number): { month: number; day: number } {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31); // 3 = März, 4 = April
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return { month, day };
}

const DAY = 24 * 60 * 60 * 1000;

/** Aktuelles Lotti-Thema für ein Datum (Default: jetzt). */
export function getMascotTheme(date: Date = new Date()): MascotTheme {
  const year = date.getFullYear();
  const month = date.getMonth(); // 0–11
  const day = date.getDate();
  const season = seasonForMonth(month);

  // Pride-Monat: ganzer Juni.
  if (month === 5) return { season, holiday: "pride" };

  // Halloween: 24.–31. Oktober.
  if (month === 9 && day >= 24) return { season, holiday: "halloween" };

  // Weihnachtszeit: 1.–26. Dezember.
  if (month === 11 && day <= 26) return { season, holiday: "christmas" };

  // Osterfenster: Karfreitag bis Ostermontag (Ostersonntag −2 … +1 Tag).
  const easter = easterSunday(year);
  const easterTs = new Date(year, easter.month - 1, easter.day).getTime();
  const ts = new Date(year, month, day).getTime();
  if (ts >= easterTs - 2 * DAY && ts <= easterTs + 1 * DAY) {
    return { season, holiday: "easter" };
  }

  return { season, holiday: null };
}

/** Kurzer, menschenlesbarer Name — z. B. für aria-label / Tooltip. */
export function mascotThemeLabel(theme: MascotTheme): string {
  const holidayName: Record<Holiday, string> = {
    pride: "im Pride-Outfit mit Regenbogenfahne",
    halloween: "im Halloween-Kostüm",
    christmas: "weihnachtlich",
    easter: "österlich",
  };
  if (theme.holiday) return holidayName[theme.holiday];
  const seasonName: Record<Season, string> = {
    spring: "im Frühling",
    summer: "im Sommer",
    autumn: "im Herbst",
    winter: "im Winter",
  };
  return seasonName[theme.season];
}
