"use client";

/* Das Schloss vor Notiz und Mitschrieb (Plan
   `docs/plan-notizen-verschluesselt.md`): ohne Konto, einrichten, entsperren.
   Erst wenn der Datenschlüssel offen ist, zeichnet es seinen Inhalt — mit
   Schlüssel und Schlüsselversion. Der Text verlässt das Gerät nur
   verschlüsselt (`lib/notizen.ts`). */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Fingerprint, Lock, LockOpen } from "lucide-react";
import { useAuth } from "@/lib/auth";
import * as krypto from "@/lib/notiz-krypto";
import {
  addPasskey, createKeys, createKeysMitPasskey, fetchKeys, lock, MIN_PASSPHRASE, onKeyChange, rememberedKey, rewrapKeys,
  sessionKey, setSessionKey, type NoteKeysState,
} from "@/lib/notizen";
import { mitPasskeyEntsperren, passkeyAnlegen, passkeyMoeglich, PasskeyFehler } from "@/lib/notiz-passkey";
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

/** Erst der Passkey (Tims Entscheidung 11.11.2026: nichts merken müssen),
 *  die Passphrase als Rückfall — wo der Browser kein PRF kann oder man lieber
 *  tippt. */
function Einrichten({ owner, karte, angebot, fuss, onFertig }: {
  owner: number; karte: { titel: string; id: string }; angebot: string; fuss?: string;
  onFertig: (k: NoteKeysState, dk: CryptoKey) => void;
}) {
  const { user } = useAuth();
  const [offen, setOffen] = useState(false);
  const [weg, setWeg] = useState<"passkey" | "passphrase" | null>(null);
  const [hinweis, setHinweis] = useState<string | null>(null);
  const [merken, setMerken] = useState(true);
  const [arbeit, setArbeit] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  useEffect(() => {
    if (offen && weg == null) void passkeyMoeglich().then((ja) => setWeg(ja ? "passkey" : "passphrase"));
  }, [offen, weg]);

  if (!offen) {
    return (
      <Karte {...karte}>
        <p className="text-sm text-muted-foreground">{angebot}</p>
        <button type="button" onClick={() => setOffen(true)} className={cn(KNOPF, "mt-3")}>Notizen einrichten</button>
        <Fuss text={fuss} />
      </Karte>
    );
  }
  if (weg == null) return <Karte {...karte}><p className="text-sm text-muted-foreground">Lädt …</p></Karte>;
  if (weg === "passphrase") {
    return <MitPassphrase owner={owner} karte={karte} fuss={fuss} hinweis={hinweis} onFertig={onFertig}
      onPasskey={hinweis ? undefined : () => setWeg("passkey")} />;
  }

  return (
    <Karte {...karte}>
      <div className="space-y-3">
        <p className="text-sm text-foreground">
          Deine Notizen schließt ein <strong className="font-semibold">Passkey</strong> auf — mit Face ID, Touch ID oder
          der Gerätesperre. Nichts zu merken, nichts abzutippen.
        </p>
        <label className="flex min-h-11 items-center gap-2 text-sm text-foreground">
          <input type="checkbox" checked={merken} onChange={(e) => setMerken(e.target.checked)} className="h-4 w-4" />
          Auf diesem Gerät offen lassen
        </label>
        {fehler && <p className="text-hinweis text-red-700 dark:text-red-300">{fehler}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" className={KNOPF} disabled={arbeit} onClick={async () => {
            setArbeit(true);
            setFehler(null);
            try {
              const { dk, basis } = await krypto.neuerSchluessel();
              const pk = await passkeyAnlegen(dk, owner, user?.email ?? `Konto ${owner}`);
              const k = await createKeysMitPasskey(basis, pk);
              const sitzung = await krypto.nurBenutzbar(dk);
              await setSessionKey(owner, sitzung, merken);
              onFertig(k, sitzung);
            } catch (e) {
              if (e instanceof PasskeyFehler && e.art === "nicht-unterstuetzt") {
                setHinweis("Dieser Browser kann keinen Passkey für Notizen anlegen. Dann mit einer Notiz-Passphrase:");
                setWeg("passphrase");
              } else {
                setFehler(e instanceof PasskeyFehler ? "Abgebrochen — noch einmal?" : e instanceof Error ? e.message : String(e));
              }
            } finally {
              setArbeit(false);
            }
          }}>
            <Fingerprint className="mr-1.5 h-4 w-4" aria-hidden /> {arbeit ? "Wartet auf den Passkey …" : "Mit Passkey einrichten"}
          </button>
          <button type="button" onClick={() => setWeg("passphrase")} className={LINK}>Lieber mit Passphrase</button>
        </div>
        <ul className="list-disc space-y-1 pl-5 text-hinweis text-muted-foreground">
          <li>Der Passkey liegt in deinem Schlüsselbund und kommt mit auf deine anderen Geräte desselben Anbieters.</li>
          <li>Die Suche und „Frag den Rat“ kennen deine Notizen nicht.</li>
          <li>Zu sehen ist nur, zu welchem Punkt es eine Notiz gibt, wann sie geändert wurde und wie lang sie ungefähr ist.</li>
        </ul>
      </div>
      <Fuss text={fuss} />
    </Karte>
  );
}

/** Der bisherige Weg: eigene Passphrase plus Wiederherstellungscode. */
function MitPassphrase({ owner, karte, fuss, hinweis, onFertig, onPasskey }: {
  owner: number; karte: { titel: string; id: string }; fuss?: string; hinweis: string | null;
  onFertig: (k: NoteKeysState, dk: CryptoKey) => void; onPasskey?: () => void;
}) {
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [merken, setMerken] = useState(false);
  const [entwurf, setEntwurf] = useState<Awaited<ReturnType<typeof krypto.setup>> | null>(null);
  const [abgetippt, setAbgetippt] = useState("");
  const [arbeit, setArbeit] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

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
          {hinweis && <p className="text-sm text-muted-foreground">{hinweis}</p>}
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
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className={KNOPF} disabled={arbeit || p1.length < MIN_PASSPHRASE || p1 !== p2}>
              {arbeit ? "Rechnet …" : "Weiter"}
            </button>
            {onPasskey && <button type="button" onClick={onPasskey} className={LINK}>Doch mit Passkey</button>}
          </div>
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
  const { user } = useAuth();
  const k = keys.keys!;
  const hatPasskey = keys.passkeys.length > 0;
  const [modus, setModus] = useState<"passkey" | "passphrase" | "code">(hatPasskey ? "passkey" : k.wrapped_passphrase ? "passphrase" : "code");
  const [pass, setPass] = useState("");
  const [merken, setMerken] = useState(hatPasskey);
  const [code, setCode] = useState("");
  const [neu, setNeu] = useState("");
  const [arbeit, setArbeit] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [kannPasskey, setKannPasskey] = useState(false);
  useEffect(() => { void passkeyMoeglich().then(setKannPasskey); }, []);

  const offen = async (dk: CryptoKey) => {
    await setSessionKey(owner, dk, merken);
    onOffen(dk);
  };
  const nebenwege = (
    <div className="flex flex-wrap items-center gap-x-4">
      {modus !== "passkey" && hatPasskey && <button type="button" onClick={() => { setModus("passkey"); setFehler(null); }} className={LINK}>Mit Passkey</button>}
      {modus !== "passphrase" && k.wrapped_passphrase && <button type="button" onClick={() => { setModus("passphrase"); setFehler(null); }} className={LINK}>Mit Passphrase</button>}
      {modus !== "code" && k.wrapped_recovery && (
        <button type="button" onClick={() => { setModus("code"); setFehler(null); }} className={LINK}>
          {k.wrapped_passphrase ? "Passphrase vergessen?" : "Mit Notfall-Code"}
        </button>
      )}
    </div>
  );
  const merkenFeld = (
    <label className="flex min-h-11 items-center gap-2 text-sm text-foreground">
      <input type="checkbox" checked={merken} onChange={(e) => setMerken(e.target.checked)} className="h-4 w-4" />
      Auf diesem Gerät offen lassen
    </label>
  );

  if (modus === "code") {
    return (
      <Karte {...karte} rechts={<span className={KICKER}>Gesperrt</span>}>
        <form className="space-y-3" onSubmit={async (e) => {
          e.preventDefault();
          if (k.wrapped_passphrase && neu && neu.length < MIN_PASSPHRASE) return;
          setArbeit(true);
          setFehler(null);
          try {
            const exportierbar = await krypto.unlockWithRecovery(k, code);
            if (!exportierbar) { setFehler("Dieser Code passt nicht."); return; }
            if (neu) {
              // Passphrase vergessen: neu verpacken, Notizen und Code bleiben.
              const verpackt = await krypto.rewrap(exportierbar, neu, k.salt, k.iterations);
              onKeys(await rewrapKeys(k.key_version, verpackt));
            } else if (kannPasskey) {
              // Ohne Passphrase: gleich einen Passkey für dieses Gerät — dann
              // braucht es den Code beim nächsten Mal nicht mehr.
              try {
                onKeys(await addPasskey(k.key_version, await passkeyAnlegen(exportierbar, owner, user?.email ?? `Konto ${owner}`)));
              } catch { /* abgebrochen: entsperrt ist trotzdem */ }
            }
            await offen(await krypto.nurBenutzbar(exportierbar));
          } catch (e2) {
            setFehler(e2 instanceof Error ? e2.message : String(e2));
          } finally {
            setArbeit(false);
          }
        }}>
          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">{k.wrapped_passphrase ? "Wiederherstellungscode" : "Notfall-Code"}</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" spellCheck={false} className={cn(FELD, "font-mono")} />
          </label>
          {k.wrapped_passphrase && (
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">Neue Notiz-Passphrase (mindestens {MIN_PASSPHRASE} Zeichen)</span>
              <input type="password" autoComplete="new-password" value={neu} onChange={(e) => setNeu(e.target.value)} className={FELD} />
            </label>
          )}
          {merkenFeld}
          {fehler && <p className="text-hinweis text-red-700 dark:text-red-300">{fehler}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className={KNOPF} disabled={arbeit || !code || (!!k.wrapped_passphrase && neu.length < MIN_PASSPHRASE)}>
              {arbeit ? "Rechnet …" : k.wrapped_passphrase ? "Neue Passphrase setzen" : "Entsperren"}
            </button>
            {nebenwege}
          </div>
        </form>
      </Karte>
    );
  }

  if (modus === "passkey") {
    return (
      <Karte {...karte} rechts={<span className={KICKER}>Gesperrt</span>}>
        <div className="space-y-2">
          {merkenFeld}
          {fehler && <p className="text-hinweis text-red-700 dark:text-red-300">{fehler}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className={KNOPF} disabled={arbeit} onClick={async () => {
              setArbeit(true);
              setFehler(null);
              try {
                await offen(await mitPasskeyEntsperren(keys.passkeys));
              } catch (e) {
                setFehler(e instanceof PasskeyFehler
                  ? (e.art === "abgebrochen" ? "Abgebrochen — noch einmal?" : e.message)
                  : e instanceof Error ? e.message : String(e));
              } finally {
                setArbeit(false);
              }
            }}>
              <Fingerprint className="mr-1.5 h-4 w-4" aria-hidden /> {arbeit ? "Wartet auf den Passkey …" : "Mit Passkey entsperren"}
            </button>
            {nebenwege}
          </div>
        </div>
        <Fuss text={fuss} />
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
        await offen(dk);
      }}>
        <label className="block text-sm">
          <span className="mb-1 block text-muted-foreground">Notiz-Passphrase</span>
          <input type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} className={FELD} />
        </label>
        {fehler && <p className="text-hinweis text-red-700 dark:text-red-300">{fehler}</p>}
        {merkenFeld}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className={KNOPF} disabled={arbeit || !pass}>
            <LockOpen className="mr-1.5 h-4 w-4" aria-hidden /> {arbeit ? "Rechnet …" : "Entsperren"}
          </button>
          {nebenwege}
        </div>
      </form>
      <Fuss text={fuss} />
    </Karte>
  );
}
