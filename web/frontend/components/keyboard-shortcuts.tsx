"use client";

import { useEffect } from "react";

/**
 * „/" springt ins wichtigste Suchfeld der aktuellen Seite.
 * Seiten markieren ihr Suchfeld mit `data-search`; das erste sichtbare gewinnt.
 * Tut nichts, während der Fokus bereits in einem Eingabefeld liegt.
 */
export function SlashSearchShortcut() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
      const el = Array.from(document.querySelectorAll<HTMLInputElement>("input[data-search]"))
        .find((i) => i.offsetParent !== null); // sichtbar (nicht in zugeklapptem Sheet/Tab)
      if (el) {
        e.preventDefault();
        el.focus();
        el.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return null;
}
