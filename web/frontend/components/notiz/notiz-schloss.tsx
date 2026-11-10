"use client";

/* Das Schloss vor Notiz und Mitschrieb (Plan
   `docs/plan-notizen-verschluesselt.md`): ohne Konto, einrichten, entsperren.
   Erst wenn der Datenschlüssel offen ist, zeichnet es seinen Inhalt — mit
   Schlüssel und Schlüsselversion. Der Text verlässt das Gerät nur
   verschlüsselt (`lib/notizen.ts`). */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Lock, LockOpen } from "lucide-react";
import { useAuth } from "@/lib/auth";
import * as krypto from "@/lib/notiz-krypto";
import {
  createKeys, fetchKeys, lock, MIN_PASSPHRASE, onKeyChange, rememberedKey, rewrapKeys, sessionKey, setSessionKey,
  type NoteKeysState,
} from "@/lib/notizen";
import { cn } from "@/lib/utils";

export const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";
const FELD = "min-h-11 w-full rounded-xl border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const KNOPF = "inline-flex min-h-11 items-center justify-center rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60";
export const LINK = "inline-flex min-h-11 items-center text-sm font-medium text-primary hover:underline";
export const HINWEIS = "Wird auf deinem Gerät verschlüsselt, bevor sie gespeichert wird. Ratslotse sieht nur den verschlüsselten Text.";

export interface Offen { owner: number; dk: CryptoKey; keyVersion: number }

export function Karte({ titel, id, children, rechts }: { titel: string; id: string; children: React.ReactNode; rechts?: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id={id} className="font-display text-base font-semibold text-foreground">{titel}</h2>
        {rechts ?? <span className={KICKER}>Mit Konto</span>}
      </div>
      <div className="mt-2">{children}</div>
    </section>
  );
}

export function Fuss({ text = HINWEIS }: { text?: string }) {
  return (
    <p className="mt-2 flex items-start gap-1.5 text-hinweis text-muted-foreground">
      <Lock className="mt-0.5 h-3.5 w-3.5 flex-none" aria-hidden /> {text}
    </p>
  );
}

export function SperrenKnopf({ owner }: { owner: number }) {
  return (
    <button type="button" onClick={() => { void lock(owner); }} className="inline-flex min-h-11 items-center gap-1 text-meta text-muted-foreground hover:text-foreground">
      <Lock className="h-3.5 w-3.5" aria-hidden /> Sperren
    </button>
  );
}

/** ``titel``/``id``: die Karte; ``angebot``: der Satz vor dem Einrichten;
 *  ``fuss``: der Hinweis unter der Karte. */
export function NotizSchloss({ titel, id, angebot, fuss, children }: {
  titel: string; id: string; angebot: string; fuss?: string; children: (o: Offen) => React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const owner = user?.id ?? null;
  const [keys, setKeys] = useState<NoteKeysState | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [dk, setDk] = useState<CryptoKey | null>(null);

  useEffect(() => {
    if (owner == null) return;
    let weg = false;
    fetchKeys().then((k) => { if (!weg) setKeys(k); }).catch((e) => { if (!weg) setFehler(String(e?.message ?? e)); });
    void rememberedKey(owner).then((d) => { if (!weg && d) setDk(d); });
    setDk(sessionKey(owner));
    const ab = onKeyChange(() => setDk(sessionKey(owner)));
    return () => { weg = true; ab(); };
  }, [owner]);

  if (loading) return null;
  const k = { titel, id };
  if (owner == null) {
    return (
      <Karte {...k}>
        <p className="text-sm text-muted-foreground">{angebot}</p>
        <Link href="/login" className={LINK}>Anmelden</Link>
        <Fuss text={fuss} />
      </Karte>
    );
  }
  if (fehler) return <Karte {...k}><p className="text-sm text-muted-foreground">{fehler}</p></Karte>;
  if (!keys) return <Karte {...k}><p className="text-sm text-muted-foreground">Lädt …</p></Karte>;
  if (!keys.configured || !keys.keys) {
    return <Einrichten owner={owner} karte={k} angebot={angebot} fuss={fuss} onFertig={(neu, d) => { setKeys(neu); setDk(d); }} />;
  }
  if (!dk) return <Entsperren owner={owner} karte={k} fuss={fuss} keys={keys} onKeys={setKeys} onOffen={setDk} />;
  return <>{children({ owner, dk, keyVersion: keys.keys.key_version })}</>;
}

// ---- Einrichten -------------------------------------------------------------

function Einrichten({ owner, karte, angebot, fuss, onFertig }: {
  owner: number; karte: { titel: string; id: string }; angebot: string; fuss?: string;
  onFertig: (k: NoteKeysState, dk: CryptoKey) => void;
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
      <Karte {...karte}>
        <p className="text-sm text-muted-foreground">{angebot}</p>
        <button type="button" onClick={() => setOffen(true)} className={cn(KNOPF, "mt-3")}>Notizen einrichten</button>
        <Fuss text={fuss} />
      </Karte>
    );
  }

  if (!entwurf) {
    const kurz = p1.length > 0 && p1.length < MIN_PASSPHRASE;
    const ungleich = p2.length > 0 && p1 !== p2;
    return (
      <Karte {...karte}>
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
        <Fuss text={fuss} />
      </Karte>
    );
  }

  const passt = krypto.parseRecovery(abgetippt) !== null
    && krypto.parseRecovery(abgetippt)!.join() === krypto.parseRecovery(entwurf.recoveryCode)!.join();
  return (
    <Karte {...karte}>
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

function Entsperren({ owner, karte, fuss, keys, onKeys, onOffen }: {
  owner: number; karte: { titel: string; id: string }; fuss?: string; keys: NoteKeysState;
  onKeys: (k: NoteKeysState) => void; onOffen: (dk: CryptoKey) => void;
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
      <Karte {...karte} rechts={<span className={KICKER}>Gesperrt</span>}>
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
    <Karte {...karte} rechts={<span className={KICKER}>Gesperrt</span>}>
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
      <Fuss text={fuss} />
    </Karte>
  );
}

