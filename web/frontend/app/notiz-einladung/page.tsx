"use client";

/* Einer gemeinsamen Notiz beitreten (Schalter `notizen-teilen`).

   Der Link sieht so aus: /notiz-einladung?i=<Kennung>#<Geheimnis>. Das
   Geheimnis im Anker öffnet den Notizschlüssel; kein Browser schickt den
   Anker an einen Server. Bevor diese Seite zur Anmeldung schickt, rettet sie
   ihn in den sessionStorage — die Rückleitung (`?weiter=`) trägt keinen
   Anker — und nimmt ihn aus der Adresszeile, damit er nicht im Verlauf steht.

   Beitreten heißt: Notizschlüssel mit dem Geheimnis auspacken, mit dem
   eigenen Datenschlüssel neu verpacken (dafür die eigenen Notizen
   entsperren), beim Server ablegen, zur Seite des Punkts springen.

   Eine Einladung per Adresse kommt als /notiz-einladung?a=<Kennung> (aus der
   Mail oder dem Push) und trägt kein Geheimnis: Annehmen, warten, bis ein
   Mitglied den Schlüssel übergibt, dann von selbst beitreten
   (`lib/shared-note-invite.ts`). */

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth-shell";
import { NotizSchloss, type Offen } from "@/components/notiz/notiz-schloss";
import { OFFEN_KEY } from "@/components/notiz/meine-notiz";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAppConfig, featureAktiv } from "@/lib/features";
import { mitRuecksprung } from "@/lib/public-routes";
import { decisionHref, punktHref } from "@/lib/routes";
import { inviteVerifier, openInvite, wrapForMe } from "@/lib/shared-note-crypto";
import { acceptInvitation, declineInvitation, joinInvitation } from "@/lib/shared-note-invite";
import type { ApiAntwort } from "@/lib/vertrag";

type Info = ApiAntwort<"/note-invites/{invite_id}">;

const zielHref = (i: Pick<Info, "target_kind" | "target_key">) => {
  if (i.target_kind === "decision") return decisionHref(Number(i.target_key));
  const [ksinr, nr] = i.target_key.split("|");
  return punktHref(Number(ksinr), nr);
};

function merken() {
  try { sessionStorage.setItem("ratslotse:punkt-reiter", "note"); } catch { /* privat */ }
}

type AdressInfo = ApiAntwort<"/note-invites/address/{invite_id}">;

const KNOPF_PRIMAER = "inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60";

function EinladungInner() {
  const sp = useSearchParams();
  const adresse = sp.get("a");
  if (adresse) return <AdressEinladung id={adresse} />;
  return <LinkEinladung id={sp.get("i") ?? ""} />;
}

/** Einladung an dieses Konto (per Adresse). */
function AdressEinladung({ id }: { id: string }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const config = useAppConfig();
  const an = featureAktiv(config.data, "notizen") && featureAktiv(config.data, "notizen-teilen");
  const [info, setInfo] = useState<AdressInfo | null | undefined>(undefined);
  const [fehler, setFehler] = useState<string | null>(null);
  const [abgelehnt, setAbgelehnt] = useState(false);

  useEffect(() => {
    if (loading || user) return;
    router.replace(mitRuecksprung("/login", `/notiz-einladung?a=${encodeURIComponent(id)}`));
  }, [loading, user, id, router]);

  const holen = useRef<() => void>(() => {});
  useEffect(() => {
    if (!user || !an) return;
    let gone = false;
    holen.current = () => {
      api.get<AdressInfo>(`/note-invites/address/${encodeURIComponent(id)}`)
        .then((r) => { if (!gone) setInfo(r); })
        .catch((e) => { if (!gone) { setInfo(null); setFehler(e instanceof ApiError && e.status === 404 ? null : String(e?.message ?? e)); } });
    };
    holen.current();
    return () => { gone = true; };
  }, [user, an, id]);

  // Angenommen, aber noch kein Schlüssel: alle paar Sekunden nachsehen.
  const wartet = Boolean(info?.accepted && !info.grant);
  useEffect(() => {
    if (!wartet) return;
    const t = window.setInterval(() => { if (document.visibilityState === "visible") holen.current(); }, 4000);
    const ende = window.setTimeout(() => window.clearInterval(t), 15 * 60 * 1000);
    return () => { window.clearInterval(t); window.clearTimeout(ende); };
  }, [wartet]);

  if (config.isLoading || loading || !user) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-muted-foreground">Lädt …</p></AuthShell>;
  if (!an) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-foreground">Diese Seite gibt es hier nicht.</p></AuthShell>;
  if (abgelehnt) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-foreground">Abgelehnt. Die Einladung ist weg.</p></AuthShell>;
  if (info === undefined) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-muted-foreground">Lädt …</p></AuthShell>;
  if (info === null) {
    return (
      <AuthShell title="Gemeinsame Notiz">
        <p className="text-sm text-foreground">{fehler ?? "Diese Einladung gilt nicht mehr."}</p>
      </AuthShell>
    );
  }
  const worum = info.target_title ? `„${info.target_title}“` : "einem Tagesordnungspunkt";
  const oeffnen = (noteId: string) => {
    try { sessionStorage.setItem(OFFEN_KEY, noteId); } catch { /* privat */ }
    merken();
    router.push(zielHref(info));
  };
  return (
    <AuthShell title="Gemeinsame Notiz" breit>
      <p className="text-lese text-foreground">
        <strong>{info.inviter_name}</strong> lädt dich ein, gemeinsam eine Notiz zu {worum} zu schreiben.
      </p>
      {info.already_member ? (
        <p className="mt-4">
          <button type="button" onClick={() => oeffnen(info.note_id)} className={KNOPF_PRIMAER}>Du bist schon dabei — zur Notiz</button>
        </p>
      ) : (
        <div className="mt-4">
          <NotizSchloss titel="Deine Notizen" id="einladung-notizen" angebot="Dafür brauchst du deine Notizen.">
            {(o) => (
              <AdressSchritt info={info} o={o} onInfo={setInfo} onJoined={oeffnen} onFehler={setFehler}
                onAblehnen={() => { declineInvitation(info).then(() => setAbgelehnt(true)).catch((e) => setFehler(String(e?.message ?? e))); }} />
            )}
          </NotizSchloss>
        </div>
      )}
      {fehler && <p className="mt-3 text-sm text-destructive" role="alert">{fehler}</p>}
    </AuthShell>
  );
}

function AdressSchritt({ info, o, onInfo, onJoined, onFehler, onAblehnen }: {
  info: AdressInfo; o: Offen; onInfo: (i: AdressInfo) => void; onJoined: (noteId: string) => void;
  onFehler: (f: string | null) => void; onAblehnen: () => void;
}) {
  const [laeuft, setLaeuft] = useState(false);
  const beigetreten = useRef(false);
  useEffect(() => {
    if (!info.grant || beigetreten.current) return;
    beigetreten.current = true;
    joinInvitation(info, o.dk, o.keyVersion, o.owner)
      .then((n) => (n ? onJoined(n.id) : onFehler("Der Schlüssel ließ sich nicht öffnen. Lass dich noch einmal einladen.")))
      .catch((e) => onFehler(e instanceof Error ? e.message : "Das hat nicht geklappt."));
  }, [info, o, onJoined, onFehler]);
  const annehmen = async () => {
    setLaeuft(true);
    onFehler(null);
    try {
      onInfo(await acceptInvitation(info, o.dk, o.keyVersion));
    } catch (e) {
      onFehler(e instanceof Error ? e.message : "Das hat nicht geklappt.");
    } finally {
      setLaeuft(false);
    }
  };
  if (!info.accepted) {
    return (
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={laeuft} onClick={() => void annehmen()} className={KNOPF_PRIMAER}>
          {laeuft ? "Nimmt an …" : "Annehmen"}
        </button>
        <button type="button" onClick={onAblehnen}
          className="inline-flex h-11 items-center rounded-lg px-3 text-sm font-medium text-foreground hover:bg-accent">
          Ablehnen
        </button>
      </div>
    );
  }
  return (
    <div role="status">
      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden />
        {info.grant ? "Tritt bei …" : "Angenommen. Gleich geht es weiter."}
      </p>
      {!info.grant && (
        <p className="mt-1 text-meta text-muted-foreground">Sobald jemand aus der Notiz online ist. Du kannst die Seite auch schließen.</p>
      )}
    </div>
  );
}

function LinkEinladung({ id }: { id: string }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const config = useAppConfig();
  const an = featureAktiv(config.data, "notizen") && featureAktiv(config.data, "notizen-teilen");
  const [geheimnis, setGeheimnis] = useState<string | null | undefined>(undefined);
  const [info, setInfo] = useState<Info | null | undefined>(undefined);
  const [fehler, setFehler] = useState<string | null>(null);
  const [laeuft, setLaeuft] = useState(false);

  useEffect(() => {
    const key = `ratslotse:einladung:${id}`;
    const anker = window.location.hash.slice(1);
    if (anker) {
      try { sessionStorage.setItem(key, anker); } catch { /* privat: dann eben nur jetzt */ }
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      setGeheimnis(anker);
      return;
    }
    let gemerkt: string | null = null;
    try { gemerkt = sessionStorage.getItem(key); } catch { /* privat */ }
    setGeheimnis(gemerkt);
  }, [id]);

  useEffect(() => {
    if (loading || user || geheimnis === undefined) return;
    router.replace(mitRuecksprung("/login", `/notiz-einladung?i=${encodeURIComponent(id)}`));
  }, [loading, user, geheimnis, id, router]);

  useEffect(() => {
    if (!user || !an || !id) return;
    let gone = false;
    api.get<Info>(`/note-invites/${encodeURIComponent(id)}`)
      .then((r) => { if (!gone) setInfo(r); })
      .catch((e) => { if (!gone) { setInfo(null); setFehler(e instanceof ApiError && e.status === 404 ? null : String(e?.message ?? e)); } });
    return () => { gone = true; };
  }, [user, an, id]);

  const beitreten = async (o: Offen) => {
    if (!info || !geheimnis) return;
    setLaeuft(true);
    setFehler(null);
    try {
      const nk = await openInvite(geheimnis, { iv: info.iv, ct: info.ciphertext });
      const verifier = await inviteVerifier(geheimnis);
      if (!nk || !verifier) {
        setFehler("Der Link ist unvollständig oder gehört zu einer anderen Einladung. Lass ihn dir noch einmal schicken.");
        return;
      }
      const w = await wrapForMe(o.dk, nk);
      await api.post(`/note-invites/${encodeURIComponent(info.invite_id)}/accept`,
        { key_iv: w.iv, key_ct: w.ct, key_version: o.keyVersion, verifier });
      try {
        sessionStorage.removeItem(`ratslotse:einladung:${id}`);
        sessionStorage.setItem(OFFEN_KEY, info.note_id);
      } catch { /* privat */ }
      merken();
      router.push(zielHref(info));
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Das hat nicht geklappt.");
    } finally {
      setLaeuft(false);
    }
  };

  if (config.isLoading || loading || !user) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-muted-foreground">Lädt …</p></AuthShell>;
  if (!an) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-foreground">Diese Seite gibt es hier nicht.</p></AuthShell>;
  if (!id || geheimnis === null) {
    return (
      <AuthShell title="Gemeinsame Notiz">
        <p className="text-sm text-foreground">Der Link ist unvollständig. Lass ihn dir noch einmal schicken.</p>
      </AuthShell>
    );
  }
  if (info === undefined) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-muted-foreground">Lädt …</p></AuthShell>;
  if (info === null) {
    return (
      <AuthShell title="Gemeinsame Notiz">
        <p className="text-sm text-foreground">{fehler ?? "Diese Einladung gilt nicht mehr."}</p>
      </AuthShell>
    );
  }
  const worum = info.target_title ? `„${info.target_title}“` : "einem Tagesordnungspunkt";
  return (
    <AuthShell title="Gemeinsame Notiz" breit>
      <p className="text-lese text-foreground">
        <strong>{info.inviter_name}</strong> lädt dich ein, gemeinsam eine Notiz zu {worum} zu schreiben.
      </p>
      {info.already_member ? (
        <p className="mt-4">
          <Link href={zielHref(info)} onClick={() => { try { sessionStorage.setItem(OFFEN_KEY, info.note_id); } catch { /* privat */ } merken(); }}
            className="inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            Du bist schon dabei — zur Notiz
          </Link>
        </p>
      ) : (
        <div className="mt-4">
          <NotizSchloss titel="Deine Notizen" id="einladung-notizen" angebot="Dafür brauchst du deine Notizen.">
            {(o) => (
              <button type="button" disabled={laeuft} onClick={() => void beitreten(o)} className={KNOPF_PRIMAER}>
                {laeuft ? "Tritt bei …" : "Beitreten"}
              </button>
            )}
          </NotizSchloss>
        </div>
      )}
      {fehler && <p className="mt-3 text-sm text-destructive" role="alert">{fehler}</p>}
    </AuthShell>
  );
}

export default function EinladungPage() {
  return (
    <Suspense fallback={null}>
      <EinladungInner />
    </Suspense>
  );
}
