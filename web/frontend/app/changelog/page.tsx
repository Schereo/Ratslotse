import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { BackLink } from "@/components/back-link";

export const metadata: Metadata = {
  title: "Changelog – Ratslotse",
  description: "Alle nennenswerten Änderungen an Ratslotse, nach Version.",
};

type Section = { title: string; items: string[] };
type Version = { version: string; date: string; sections: Section[] };

// CHANGELOG.md lives at the repo root (two levels up from web/frontend). Read at build
// time so it ships baked into this static page; it refreshes with every deploy.
const REPO_ROOT = path.join(process.cwd(), "..", "..");

function readChangelog(): string {
  try {
    return fs.readFileSync(path.join(REPO_ROOT, "CHANGELOG.md"), "utf8");
  } catch {
    return "";
  }
}

// Noch nicht geschnittene Einträge liegen als einzelne Dateien in changelog.d/
// (siehe scripts/changelog_schnitt.py) — ein Fragment je Änderung, damit
// parallele Zweige nicht in denselben Changelog-Zeilen kollidieren. Für
// Leser*innen ist das unsichtbar: Sie stehen hier unter „Unreleased", genau
// wie die von Hand eingetragenen. Beim Versionsschnitt wandern sie in
// CHANGELOG.md und verschwinden hier — dieselbe Anzeige, andere Quelle.
const KATEGORIEN: Record<string, string> = {
  hinzugefuegt: "Hinzugefügt",
  "hinzugefügt": "Hinzugefügt",
  geaendert: "Geändert",
  "geändert": "Geändert",
  behoben: "Behoben",
};
const FRAGMENT_REIHENFOLGE = ["Hinzugefügt", "Geändert", "Behoben"];

type Fragment = { section: string; text: string };

function readFragments(): Fragment[] {
  let namen: string[];
  try {
    namen = fs
      .readdirSync(path.join(REPO_ROOT, "changelog.d"))
      .filter((n) => n.endsWith(".md") && !n.startsWith("_") && n.toLowerCase() !== "readme.md")
      .sort(); // nach Dateiname — auf jedem Rechner dieselbe Reihenfolge
  } catch {
    return []; // kein Verzeichnis (z. B. frisch nach einem Schnitt) → nichts zu zeigen
  }
  const out: Fragment[] = [];
  for (const name of namen) {
    let roh = "";
    try {
      roh = fs.readFileSync(path.join(REPO_ROOT, "changelog.d", name), "utf8");
    } catch {
      continue;
    }
    const m = roh.match(/^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*\r?\n([\s\S]*)$/);
    if (!m) continue;
    const kat = m[1].match(/^[ \t]*category[ \t]*:[ \t]*(.+?)[ \t]*$/m);
    const section = kat ? KATEGORIEN[kat[1].trim().toLowerCase()] : undefined;
    const text = m[2].replace(/\s+/g, " ").trim();
    // Ein kaputtes Fragment überspringen statt den Build zu kippen — angemeckert
    // wird es von tests/test_changelog_fragmente.py, nicht von der Seite.
    if (section && text) out.push({ section, text });
  }
  return out;
}

function mergeFragments(versions: Version[], fragmente: Fragment[]): Version[] {
  if (fragmente.length === 0) return versions;
  let unreleased = versions.find((v) => v.version === "Unreleased");
  if (!unreleased) {
    unreleased = { version: "Unreleased", date: "", sections: [] };
    versions = [unreleased, ...versions];
  }
  for (const titel of FRAGMENT_REIHENFOLGE) {
    const passend = fragmente.filter((f) => f.section === titel);
    if (passend.length === 0) continue;
    let sec = unreleased.sections.find((s) => s.title === titel);
    if (!sec) {
      sec = { title: titel, items: [] };
      unreleased.sections.push(sec);
    }
    sec.items.push(...passend.map((f) => f.text));
  }
  return versions;
}

function parse(md: string): Version[] {
  const out: Version[] = [];
  let cur: Version | null = null;
  let sec: Section | null = null;
  for (const line of md.split("\n")) {
    if (line.startsWith("## ")) {
      const head = line.slice(3).trim();
      const m = head.match(/\[([^\]]+)\]\s*[–-]\s*(.+)/);
      cur = { version: m ? m[1] : head.replace(/[[\]]/g, ""), date: m ? m[2].trim() : "", sections: [] };
      sec = null;
      out.push(cur);
    } else if (line.startsWith("### ") && cur) {
      sec = { title: line.slice(4).trim(), items: [] };
      cur.sections.push(sec);
    } else if (line.startsWith("- ") && cur && sec) {
      sec.items.push(line.slice(2).trim());
    } else if (/^\s{2,}\S/.test(line) && cur && sec && sec.items.length > 0) {
      // Umbruch-Folgezeile eines Eintrags (Markdown auf ~80 Zeichen umbrochen)
      // — an den letzten Punkt anhängen statt sie zu verlieren.
      sec.items[sec.items.length - 1] += " " + line.trim();
    }
  }
  return out;
}

// Minimal inline markdown → React: **bold**, `code`, [text](url). Safe (no innerHTML).
function inline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1] !== undefined) parts.push(<strong key={i++} className="font-semibold text-foreground">{m[1]}</strong>);
    else if (m[2] !== undefined) parts.push(<code key={i++} className="rounded bg-muted px-1 py-0.5 text-[0.85em] text-foreground">{m[2]}</code>);
    else parts.push(<a key={i++} href={m[4]} target="_blank" rel="noreferrer" className="text-primary hover:underline">{m[3]}</a>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function ChangelogPage() {
  // Fragmente erst dazumischen, dann leere Blöcke wegwerfen — sonst fiele ein
  // „Unreleased" ohne eigene Einträge weg, das nur aus Fragmenten besteht.
  const versions = mergeFragments(parse(readChangelog()), readFragments())
    .filter((v) => v.sections.length > 0);
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            <BackLink />
            <Link href="/" className="flex items-center gap-2"><BrandMark /><span className="hidden font-semibold text-foreground sm:inline">Ratslotse</span></Link>
          </div>
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">Anmelden →</Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Changelog</h1>
        <p className="mt-3 leading-relaxed text-muted-foreground">Alle nennenswerten Änderungen an Ratslotse, nach Version.</p>

        {versions.length === 0 ? (
          <p className="mt-8 text-sm text-muted-foreground">Changelog konnte nicht geladen werden.</p>
        ) : (
          <div className="mt-8 space-y-8">
            {versions.map((v) => (
              <section key={v.version} className="border-t border-border pt-6">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h2 className="text-lg font-semibold text-foreground">{v.version === "Unreleased" ? "Unreleased" : `v${v.version}`}</h2>
                  {v.date && <span className="text-xs text-muted-foreground">{v.date}</span>}
                </div>
                {v.sections.map((s) => (
                  <div key={s.title} className="mt-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">{s.title}</p>
                    <ul className="mt-1.5 space-y-1.5">
                      {s.items.map((it, idx) => (
                        <li key={idx} className="flex gap-2 text-sm leading-relaxed text-muted-foreground">
                          <span className="select-none text-muted-foreground/40">•</span>
                          <span>{inline(it)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </section>
            ))}
          </div>
        )}

        <footer className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          <Link href="/impressum" className="hover:text-foreground">Impressum</Link>
          {" · "}
          <Link href="/datenschutz" className="hover:text-foreground">Datenschutz</Link>
          {" · "}
          <Link href="/" className="hover:text-foreground">Startseite</Link>
        </footer>
      </main>
    </div>
  );
}
