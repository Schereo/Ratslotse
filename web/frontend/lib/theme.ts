// Dark-mode helpers. Theme is stored in localStorage and applied to <html>.
// Called during Providers mount to avoid a flash of wrong theme.

type Theme = "light" | "dark" | "system";

export function getTheme(): Theme {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem("theme") as Theme) ?? "system";
}

/** Theme kann von mehreren Stellen wechseln (Lotti-Schalter, Konto-Karte,
 *  ⌘K-Palette) — dieses Event hält alle sichtbaren Regler synchron. */
export const THEME_EVENT = "ratslotse:theme";

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark = theme === "dark" || (theme === "system" && prefersDark);
  root.classList.toggle("dark", isDark);
  if (theme === "system") {
    localStorage.removeItem("theme");
  } else {
    localStorage.setItem("theme", theme);
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

/** Ist das Dokument gerade dunkel? Deckt auch den System-Modus ab —
 *  der Lotti-Schalter (RL-U09) zeigt und toggelt den Ist-Zustand. */
export function isDarkNow(): boolean {
  if (typeof document === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

export function initTheme() {
  applyTheme(getTheme());
  // Im System-Modus live auf Wechsel des OS-Farbschemas reagieren.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (getTheme() === "system") applyTheme("system");
  });
}

export type { Theme };
