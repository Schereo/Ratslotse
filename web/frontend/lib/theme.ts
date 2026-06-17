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

export function toggleTheme() {
  const current = getTheme();
  const root = document.documentElement;
  const isDarkNow = root.classList.contains("dark");
  applyTheme(isDarkNow ? "light" : "dark");
}

export function initTheme() {
  applyTheme(getTheme());
}
