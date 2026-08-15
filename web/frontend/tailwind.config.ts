import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "1rem",
    },
    extend: {
      screens: {
        /* Zwei verschiedene Fragen — bitte nicht wieder zu einer machen:
           „Wie BREIT ist der Platz?" (wie viele Lesespalten passen nebeneinander)
           und „Womit wird GEZEIGT?" (Maus oder Daumen — Seitenleiste oder
           Tab-Leiste). Ein iPad quer beantwortet sie unterschiedlich: breit
           genug für zwei Spalten, aber immer noch ein Touch-Gerät.

           breit  — reine Breite. Alles, was nur mit dem Platz zu tun hat:
                    Lesespalte + Belege-Spalte, Raster, Innenabstände. Gilt
                    auf dem iPad quer GENAUSO wie am Desktop (Tims Befund
                    15.08.: „hier würden die quellen auch als spalte daneben
                    passen").
           desk   — echter Desktop, nicht bloß ein breiter Screen. Die
                    Seitenleiste ist Maus-Navigation: schmale Ziele,
                    Hover-Zustände, kein Daumen in Reichweite. Ein iPad ist
                    auch quer 1366 px breit und bekäme sie nach reiner Breite
                    — genau das sah auf dem 13"-iPad hochkant falsch aus
                    (Tims Befund 14.08.: „der Screen ist absolut kacke
                    aufgeteilt"). `pointer: fine` fragt das primäre
                    Eingabegerät ab: Maus/Trackpad → Leiste links, Finger →
                    Tab-Leiste unten. Ein angestecktes Magic Keyboard ändert
                    daran nichts, Touch bleibt auf dem iPad das primäre Gerät.
           tab    — der Rest von `breit`: breites Touch-Gerät. Dort gehören
                    Tab-Leiste und fixierter Composer der Unterkante des
                    Bildschirms; was sich daran ausrichten muss, hängt hier
                    dran statt an `desk`.

           `desk` und `tab` schließen einander aus — deshalb ist es egal, in
           welcher Reihenfolge Tailwind ihre Regeln ausgibt. `breit` steht
           bewusst VOR beiden: Wo eine Regel doppelt gesetzt wird, gewinnt die
           gerätespezifische. */
        breit: { raw: "(min-width: 1024px)" },
        desk: { raw: "(pointer: fine) and (min-width: 1024px)" },
        tab: { raw: "(pointer: coarse) and (min-width: 1024px)" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "var(--font-inter)", "system-ui", "sans-serif"],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        signal: {
          DEFAULT: "hsl(var(--signal))",
          foreground: "hsl(var(--signal-foreground))",
        },
      },
      boxShadow: {
        // Weicher Ambient-Schatten für angehobene Karten (statt hartem shadow-md).
        lifted: "0 6px 24px -8px hsl(var(--primary) / 0.18), 0 2px 8px -4px hsl(var(--foreground) / 0.08)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        // Sanftes Auf-und-ab-Schweben fürs Maskottchen (wie ein Boot in der Dünung).
        bob: {
          "0%, 100%": { transform: "translateY(0) rotate(-1.5deg)" },
          "50%": { transform: "translateY(-6px) rotate(1.5deg)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        bob: "bob 4s ease-in-out infinite",
      },
      // Starke Kurven als Utilities (ease-out-strong, ease-drawer …) —
      // die Werte stehen als CSS-Variablen in globals.css.
      transitionTimingFunction: {
        "out-strong": "var(--ease-out-strong)",
        "in-out-strong": "var(--ease-in-out-strong)",
        drawer: "var(--ease-drawer)",
        "back-out": "var(--ease-back-out)",
      },
    },
  },
  // Container-Queries (offizielles Tailwind-Plugin; in Tailwind 4 eingebaut):
  // Karten liegen in unterschiedlich breiten Rasterspalten — eine Karte muss
  // auf IHRE Breite reagieren, nicht auf die des Fensters. Mit
  // Fenster-Breakpoints allein blieb in der schmalen Spalte vom Gremiennamen
  // nur „K…" übrig (Tims Befund 12.08.).
  plugins: [require("tailwindcss-animate"), require("@tailwindcss/container-queries")],
};

export default config;
