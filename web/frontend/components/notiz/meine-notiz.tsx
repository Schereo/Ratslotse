"use client";

/* „Meine Notiz" an einem Tagesordnungspunkt oder Beschluss (Schalter
   `notizen`, Plan `docs/plan-notizen-verschluesselt.md`, Bild
   `docs/entwurf-sitzungsseite/bilder/punkt-desktop-2.png` rechts unten).

   Vier Zustände: ohne Konto, nicht eingerichtet, gesperrt, offen. Der Text
   verlässt das Gerät nur verschlüsselt (`lib/notizen.ts`). */

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Lock, LockOpen } from "lucide-react";
import { useAuth } from "@/lib/auth";
import * as krypto from "@/lib/notiz-krypto";
import {
  createKeys, deleteNote, fetchKeys, loadNote, lock, MIN_PASSPHRASE, onKeyChange, rememberedKey, rewrapKeys,
  saveNote, sessionKey, setSessionKey, type LoadedNote, type NoteKeysState, type TargetKind,
} from "@/lib/notizen";
import { cn } from "@/lib/utils";

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";
const FELD = "min-h-11 w-full rounded-xl border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const KNOPF = "inline-flex min-h-11 items-center justify-center rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60";
const LINK = "inline-flex min-h-11 items-center text-sm font-medium text-primary hover:underline";
const HINWEIS = "Wird auf deinem Gerät verschlüsselt, bevor sie gespeichert wird. Ratslotse sieht nur den verschlüsselten Text.";

function Karte({ children, rechts }: { children: React.ReactNode; rechts?: React.ReactNode }) {
  return (
    <section aria-labelledby="meine-notiz" className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="meine-notiz" className="font-display text-base font-semibold text-foreground">Meine Notiz</h2>
        {rechts ?? <span className={KICKER}>Mit Konto</span>}
      </div>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Fuss({ text = HINWEIS }: { text?: string }) {
  return (
    <p className="mt-2 flex items-start gap-1.5 text-hinweis text-muted-foreground">
      <Lock className="mt-0.5 h-3.5 w-3.5 flex-none" aria-hidden /> {text}
    </p>
  );
}

export function MeineNotiz({ targetKind, targetKey, wofuer = "Punkt" }: {
  targetKind: TargetKind; targetKey: string; wofuer?: "Punkt" | "Beschluss";
}) {
  const { user, loading } = useAuth();
  const owner = user?.id ?? null;
  const [keys, setKeys] = useState<NoteKeysState | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [dk, setDk] = useState<CryptoKey | null>(null);

  useEffect(() => {
    if (owner == null) return;
    let weg = false;
    fetchKeys().then((k) => { if (!weg) setKeys(k); }).catch((e) => { if (!weg) setFehler(String(e.message ?? e)); });
    void rememberedKey(owner).then((d) => { if (!weg && d) setDk(d); });
    const ab = onKeyChange(() => setDk(sessionKey(owner)));
    return () => { weg = true; ab(); };
  }, [owner]);

  if (loading) return null;
  if (owner == null) {
    return (
      <Karte>
        <p className="text-sm text-muted-foreground">Mit einem Konto kannst du dir zu diesem {wofuer} etwas notieren — nur für dich lesbar.</p>
        <Link href="/login" className={LINK}>Anmelden</Link>
        <Fuss />
      </Karte>
    );
  }
  if (fehler) return <Karte><p className="text-sm text-muted-foreground">{fehler}</p></Karte>;
  if (!keys) return <Karte><p className="text-sm text-muted-foreground">Lädt …</p></Karte>;
  if (!keys.configured || !keys.keys) {
    return <Einrichten owner={owner} onFertig={(k, d) => { setKeys(k); setDk(d); }} wofuer={wofuer} />;
  }
  if (!dk) return <Entsperren owner={owner} keys={keys} onKeys={setKeys} onOffen={setDk} />;
  return <Offen owner={owner} dk={dk} keyVersion={keys.keys.key_version} targetKind={targetKind} targetKey={targetKey} wofuer={wofuer} />;
}

// ---- Einrichten -------------------------------------------------------------

function Einrichten({ owner, onFertig, wofuer }: {
  owner: number; wofuer: string; onFertig: (k: NoteKeysState, dk: CryptoKey) => void;
}) {
  const [offen, setOffen] = useState(false);
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [merken, setMerken] = useState(false);
  const [entwurf, setEntwurf] = useState<Awaited<ReturnType<typeof krypto.setup>> | null>(null);
  const [abgetippt, setAbgetippt] = useState("");
  const [arbeit, setArbeit] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  if (!offen) {
    return (
      <Karte>
        <p className="text-sm text-muted-foreground">Notiere dir, was du zu diesem {wofuer} wissen oder nachfragen willst. Nur du kannst es lesen.</p>
        <button type="button" onClick={() => setOffen(true)} className={cn(KNOPF, "mt-3")}>Notizen einrichten</button>
        <Fuss />
      </Karte>
    );
  }

  if (!entwurf) {
    const kurz = p1.length > 0 && p1.length < MIN_PASSPHRASE;
    const ungleich = p2.length > 0 && p1 !== p2;
    return (
      <Karte>
        <form className="space-y-3" onSubmit={async (e) => {
          e.preventDefault();
          if (p1.length < MIN_PASSPHRASE || p1 !== p2) return;
          setArbeit(true);
          setEntwurf(await krypto.setup(p1));
          setArbeit(false);
        }}>
          <p className="text-sm text-foreground">
            Deine Notizen schließt eine eigene <strong className="font-semibold">Notiz-Passphrase</strong> auf — nicht dein Anmeldepasswort.
          </p>
          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">Notiz-Passphrase (mindestens {MIN_PASSPHRASE} Zeichen)</span>
            <input type="password" autoComplete="new-password" value={p1} onChange={(e) => setP1(e.target.value)} className={FELD} />
          </label>
          {kurz && <p className="text-hinweis text-amber-700 dark:text-amber-300">Noch etwas länger, bitte.</p>}
          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">Noch einmal</span>
            <input type="password" autoComplete="new-password" value={p2} onChange={(e) => setP2(e.target.value)} className={FELD} />
          </label>
          {ungleich && <p className="text-hinweis text-amber-700 dark:text-amber-300">Die beiden stimmen nicht überein.</p>}
          <label className="flex min-h-11 items-center gap-2 text-sm text-foreground">
            <input type="checkbox" checked={merken} onChange={(e) => setMerken(e.target.checked)} className="h-4 w-4" />
            Auf diesem Gerät merken
          </label>
          <button type="submit" className={KNOPF} disabled={arbeit || p1.length < MIN_PASSPHRASE || p1 !== p2}>
            {arbeit ? "Rechnet …" : "Weiter"}
          </button>
        </form>
        <Fuss />
      </Karte>
    );
  }

  const passt = krypto.parseRecovery(abgetippt) !== null
    && krypto.parseRecovery(abgetippt)!.join() === krypto.parseRecovery(entwurf.recoveryCode)!.join();
  return (
    <Karte>
      <div className="space-y-3">
        <p className="text-sm text-foreground">
          <strong className="font-semibold">Dein Wiederherstellungscode.</strong> Schreib ihn auf oder druck ihn aus. Wer Passphrase
          und Code verliert, verliert die Notizen — niemand kann sie zurückholen.
        </p>
        <p className="select-all rounded-xl border border-dashed border-border bg-muted px-3 py-2 text-center font-mono text-sm tracking-wider text-foreground [overflow-wrap:anywhere]"
          aria-label="Wiederherstellungscode">{entwurf.recoveryCode}</p>
        <label className="block text-sm">
          <span className="mb-1 block text-muted-foreground">Zur Sicherheit einmal abtippen</span>
          <input value={abgetippt} onChange={(e) => setAbgetippt(e.target.value)} autoComplete="off" spellCheck={false} className={cn(FELD, "font-mono")} />
        </label>
        <ul className="list-disc space-y-1 pl-5 text-hinweis text-muted-foreground">
          <li>Die Suche und „Frag den Rat“ kennen deine Notizen nicht.</li>
          <li>Zu sehen ist nur, zu welchem Punkt es eine Notiz gibt, wann sie geändert wurde und wie lang sie ungefähr ist.</li>
          <li>Im Browser kommt der Code, der verschlüsselt, vom selben Server, der die Notizen speichert. Die App bringt ihn aus dem Store mit.</li>
        </ul>
        {fehler && <p className="text-hinweis text-red-700 dark:text-red-300">{fehler}</p>}
        <button type="button" className={KNOPF} disabled={!passt || arbeit} onClick={async () => {
          setArbeit(true);
          setFehler(null);
          try {
            const k = await createKeys(entwurf.keys);
            await setSessionKey(owner, entwurf.dk, merken);
            onFertig(k, entwurf.dk);
          } catch (e) {
            setFehler(e instanceof Error ? e.message : String(e));
          } finally {
            setArbeit(false);
          }
        }}>Notizen einrichten</button>
      </div>
    </Karte>
  );
}

// ---- Entsperren ---------------------------------------------------------------

function Entsperren({ owner, keys, onKeys, onOffen }: {
  owner: number; keys: NoteKeysState; onKeys: (k: NoteKeysState) => void; onOffen: (dk: CryptoKey) => void;
}) {
  const k = keys.keys!;
  const [pass, setPass] = useState("");
  const [merken, setMerken] = useState(false);
  const [code, setCode] = useState("");
  const [neu, setNeu] = useState("");
  const [vergessen, setVergessen] = useState(false);
  const [arbeit, setArbeit] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  if (vergessen) {
    return (
      <Karte rechts={<span className={KICKER}>Gesperrt</span>}>
        <form className="space-y-3" onSubmit={async (e) => {
          e.preventDefault();
          if (neu.length < MIN_PASSPHRASE) return;
          setArbeit(true);
          setFehler(null);
          try {
            const exportierbar = await krypto.unlockWithRecovery(k, code);
            if (!exportierbar) { setFehler("Dieser Code passt nicht."); return; }
            const verpackt = await krypto.rewrap(exportierbar, neu, k.salt, k.iterations);
            onKeys(await rewrapKeys(k.key_version, verpackt));
            const dk = await krypto.unlockWithPassphrase({ ...k, ...verpackt }, neu);
            await setSessionKey(owner, dk!, merken);
            onOffen(dk!);
          } catch (e2) {
            setFehler(e2 instanceof Error ? e2.message : String(e2));
          } finally {
            setArbeit(false);
          }
        }}>
          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">Wiederherstellungscode</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" spellCheck={false} className={cn(FELD, "font-mono")} />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">Neue Notiz-Passphrase (mindestens {MIN_PASSPHRASE} Zeichen)</span>
            <input type="password" autoComplete="new-password" value={neu} onChange={(e) => setNeu(e.target.value)} className={FELD} />
          </label>
          {fehler && <p className="text-hinweis text-red-700 dark:text-red-300">{fehler}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className={KNOPF} disabled={arbeit || neu.length < MIN_PASSPHRASE}>{arbeit ? "Rechnet …" : "Neue Passphrase setzen"}</button>
            <button type="button" onClick={() => setVergessen(false)} className={LINK}>Zurück</button>
          </div>
        </form>
      </Karte>
    );
  }

  return (
    <Karte rechts={<span className={KICKER}>Gesperrt</span>}>
      <form className="space-y-2" onSubmit={async (e) => {
        e.preventDefault();
        setArbeit(true);
        setFehler(null);
        const dk = await krypto.unlockWithPassphrase(k, pass);
        setArbeit(false);
        if (!dk) { setFehler("Diese Passphrase passt nicht."); return; }
        setPass("");
        await setSessionKey(owner, dk, merken);
        onOffen(dk);
      }}>
        <label className="block text-sm">
          <span className="mb-1 block text-muted-foreground">Notiz-Passphrase</span>
          <input type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} className={FELD} />
        </label>
        {fehler && <p className="text-hinweis text-red-700 dark:text-red-300">{fehler}</p>}
        <label className="flex min-h-11 items-center gap-2 text-sm text-foreground">
          <input type="checkbox" checked={merken} onChange={(e) => setMerken(e.target.checked)} className="h-4 w-4" />
          Auf diesem Gerät merken
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className={KNOPF} disabled={arbeit || !pass}>
            <LockOpen className="mr-1.5 h-4 w-4" aria-hidden /> {arbeit ? "Rechnet …" : "Entsperren"}
          </button>
          <button type="button" onClick={() => setVergessen(true)} className={LINK}>Passphrase vergessen?</button>
        </div>
      </form>
      <Fuss />
    </Karte>
  );
}

// ---- Offen ------------------------------------------------------------------

type Stand = "lädt" | "bereit" | "speichert" | "gespeichert" | "konflikt" | "fehler";

function Offen({ owner, dk, keyVersion, targetKind, targetKey, wofuer }: {
  owner: number; dk: CryptoKey; keyVersion: number; targetKind: TargetKind; targetKey: string; wofuer: string;
}) {
  const [text, setText] = useState("");
  const [stand, setStand] = useState<Stand>("lädt");
  const [version, setVersion] = useState(0);
  const [um, setUm] = useState<string | null>(null);
  const [konflikt, setKonflikt] = useState<LoadedNote | null>(null);
  const [unlesbar, setUnlesbar] = useState(false);
  const zuletzt = useRef("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let weg = false;
    loadNote(dk, targetKind, targetKey).then((n) => {
      if (weg) return;
      setText(n?.text ?? "");
      zuletzt.current = n?.text ?? "";
      setVersion(n?.version ?? 0);
      setUm(n?.updatedAt ?? null);
      setUnlesbar(n != null && !n.lesbar);
      setStand("bereit");
    }).catch(() => { if (!weg) setStand("fehler"); });
    return () => { weg = true; };
  }, [dk, targetKind, targetKey]);

  const speichern = useCallback(async (wert: string, basis: number) => {
    if (wert === zuletzt.current) return;
    setStand("speichert");
    try {
      if (!wert.trim() && basis > 0) {
        await deleteNote(targetKind, targetKey);
        zuletzt.current = "";
        setVersion(0);
        setUm(null);
        setStand("gespeichert");
        return;
      }
      const r = await saveNote(dk, keyVersion, targetKind, targetKey, wert, basis);
      if (r.ok) {
        zuletzt.current = wert;
        setVersion(r.version);
        setUm(r.updatedAt);
        setStand("gespeichert");
      } else {
        setKonflikt(r.conflict);
        setStand("konflikt");
      }
    } catch {
      setStand("fehler");
    }
  }, [dk, keyVersion, targetKind, targetKey]);

  // Zwischenspeichern beim Tippen: 1,5 s Ruhe, dann verschlüsselt hinaus.
  useEffect(() => {
    if (stand === "lädt" || stand === "konflikt") return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void speichern(text, version); }, 1500);
    return () => { if (timer.current) clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  const uhr = um ? new Date(um.endsWith("Z") ? um : `${um}Z`).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : null;
  const statusText = stand === "speichert" ? "Speichert …"
    : stand === "gespeichert" ? (version ? `Gespeichert${uhr ? ` um ${uhr}` : ""}` : "Gelöscht")
    : stand === "fehler" ? "Nicht gespeichert — Verbindung prüfen." : null;

  return (
    <Karte rechts={
      <button type="button" onClick={() => { void lock(owner); }} className="inline-flex min-h-11 items-center gap-1 text-meta text-muted-foreground hover:text-foreground">
        <Lock className="h-3.5 w-3.5" aria-hidden /> Sperren
      </button>
    }>
      {unlesbar && (
        <p className="mb-2 text-hinweis text-amber-700 dark:text-amber-300">
          Diese Notiz lässt sich mit dem jetzigen Schlüssel nicht lesen. Was du schreibst, ersetzt sie.
        </p>
      )}
      <label htmlFor="notiz-text" className="sr-only">Meine Notiz zu diesem {wofuer}</label>
      <textarea id="notiz-text" value={text} disabled={stand === "lädt"} rows={5} maxLength={8000}
        onChange={(e) => setText(e.target.value)} onBlur={() => { void speichern(text, version); }}
        placeholder={`Was willst du dir zu diesem ${wofuer} merken?`}
        className="w-full resize-y rounded-xl border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
      {stand === "konflikt" && (
        <div className="mt-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          <p>Auf einem anderen Gerät wurde diese Notiz inzwischen geändert.</p>
          {konflikt && <p className="mt-1 whitespace-pre-wrap italic">{konflikt.text || "(leer)"}</p>}
          <div className="mt-2 flex flex-wrap gap-3">
            <button type="button" className={LINK} onClick={() => {
              setText(konflikt?.text ?? "");
              zuletzt.current = konflikt?.text ?? "";
              setVersion(konflikt?.version ?? 0);
              setKonflikt(null);
              setStand("bereit");
            }}>Diese Fassung übernehmen</button>
            <button type="button" className={LINK} onClick={() => {
              const basis = konflikt?.version ?? 0;
              setKonflikt(null);
              setStand("bereit");
              zuletzt.current = "\u0000";   // erzwingt das Speichern
              void speichern(text, basis);
            }}>Meine behalten</button>
          </div>
        </div>
      )}
      <p className="mt-1 min-h-5 text-meta text-muted-foreground" aria-live="polite">{statusText}</p>
      <Fuss />
    </Karte>
  );
}
