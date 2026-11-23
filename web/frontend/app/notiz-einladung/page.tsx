"use client";

/* Einer gemeinsamen Notiz beitreten (Schalter `notizen-teilen`).

   Der Link sieht so aus: /notiz-einladung?i=<Kennung>#<Geheimnis>. Das
   Geheimnis im Anker öffnet den Notizschlüssel; kein Browser schickt den
   Anker an einen Server. Bevor diese Seite zur Anmeldung schickt, rettet sie
   ihn in den sessionStorage — die Rückleitung (`?weiter=`) trägt keinen
   Anker — und nimmt ihn aus der Adresszeile, damit er nicht im Verlauf steht.

   Beitreten heißt: Notizschlüssel mit dem Geheimnis auspacken, mit dem
   eigenen Datenschlüssel neu verpacken (dafür die eigenen Notizen
   entsperren), beim Server ablegen, zur Seite des Punkts springen. */

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/auth-shell";
import { NotizSchloss, type Offen } from "@/components/notiz/notiz-schloss";
import { OFFEN_KEY } from "@/components/notiz/meine-notiz";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAppConfig, featureAktiv } from "@/lib/features";
import { mitRuecksprung } from "@/lib/public-routes";
import { decisionHref, punktHref } from "@/lib/routes";
import { openInvite, wrapForMe } from "@/lib/shared-note-crypto";
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

function EinladungInner() {
  const sp = useSearchParams();
  const id = sp.get("i") ?? "";
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
      if (!nk) {
        setFehler("Der Link ist unvollständig oder gehört zu einer anderen Einladung. Lass ihn dir noch einmal schicken.");
        return;
      }
      const w = await wrapForMe(o.dk, nk);
      await api.post(`/note-invites/${encodeURIComponent(info.invite_id)}/accept`,
        { key_iv: w.iv, key_ct: w.ct, key_version: o.keyVersion });
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
        <p className="text-sm text-foreground">Der Link ist unvollständig. Lass ihn dir noch einmal schicken, am besten zum Kopieren statt abgetippt.</p>
      </AuthShell>
    );
  }
  if (info === undefined) return <AuthShell title="Gemeinsame Notiz"><p className="text-sm text-muted-foreground">Lädt …</p></AuthShell>;
  if (info === null) {
    return (
      <AuthShell title="Gemeinsame Notiz">
        <p className="text-sm text-foreground">{fehler ?? "Diese Einladung gilt nicht mehr — sie ist abgelaufen oder wurde zurückgezogen."}</p>
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
          <NotizSchloss titel="Deine Notizen" id="einladung-notizen"
            angebot="Um beizutreten, richte deine Notizen ein. Nur die Mitglieder können die gemeinsame Notiz lesen.">
            {(o) => (
              <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
                <button type="button" disabled={laeuft} onClick={() => void beitreten(o)}
                  className="inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60">
                  {laeuft ? "Tritt bei …" : "Beitreten"}
                </button>
              </div>
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
