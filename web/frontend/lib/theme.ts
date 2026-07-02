// Dark-mode helpers. Theme is stored in localStorage and applied to <html>.
// Called during Providers mount to avoid a flash of wrong theme.

type Theme = "light" | "dark" | "system";

export function getTheme(): Theme {
  if (typeof window === "undefined") return "system";
  return (localStorage.getItem("theme") as Theme) ?? "system";
}

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
}

/**
 * Zyklus hell → dunkel → System. Der alte Zweipunkt-Toggle war eine Sackgasse:
 * Einmal umgeschaltet, kam man nie zurück in den System-Modus.
 * Gibt den neuen Modus zurück, damit die UI Icon/Label aktualisieren kann.
 */
export function cycleTheme(): Theme {
  const order: Theme[] = ["light", "dark", "system"];
  const next = order[(order.indexOf(getTheme()) + 1) % order.length];
  applyTheme(next);
  return next;
}

export function initTheme() {
  applyTheme(getTheme());
  // Im System-Modus live auf Wechsel des OS-Farbschemas reagieren.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (getTheme() === "system") applyTheme("system");
  });
}

export type { Theme };
