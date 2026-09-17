"use client";

import { useState } from "react";
import { ArrowLeft, ChevronDown } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminUserDetail } from "@/lib/types";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { Button, Card, ErrorState, Spinner, formatDate, toast } from "@/components/ui";
import { cn } from "@/lib/utils";
import { clientFarbe, clientKurz, clientLabel, hauptClient } from "@/lib/clients";
import { AdminVerlauf } from "@/components/grafik/admin-verlauf";
import { UserMailHistory } from "./mail";

type RolleInfo = ApiAntwort<"/admin/roles">[number];

/** Aktivitäts-Ampel aus dem letzten Aktivitätstag (Design 20a). */
function activitySignal(lastSeen: string | null): { dot: string; label: string } {
  if (!lastSeen) return { dot: "bg-muted-foreground/40", label: "nie aktiv" };
  const days = Math.round((Date.now() - new Date(lastSeen + "T12:00:00").getTime()) / 86400000);
  if (days <= 0) return { dot: "bg-green-500", label: "heute aktiv" };
  if (days < 7) return { dot: "bg-amber-500", label: `vor ${days} ${days === 1 ? "Tag" : "Tagen"}` };
  const w = Math.round(days / 7);
  return { dot: "bg-muted-foreground/50", label: w <= 1 ? "vor 1 Woche" : `vor ${w} Wochen` };
}

const USER_FEATURE_LABEL: [keyof AdminUserDetail["features"], string][] = [
  ["ki_frage", "KI-Frage"], ["research", "Gründliche Recherche"], ["suche", "Beschluss-Suche"],
  ["quiz", "Quiz"], ["analyse", "Analyse"], ["karte", "Stadtkarte"],
];

export function UsersTab({ currentUserId, route }: { currentUserId: number; route: string }) {
  const [q, setQ] = useState("");
  const params = new URLSearchParams(route);
  const id = Number(params.get("user"));
  const selected = Number.isSafeInteger(id) && id > 0 ? id : null;
  const section = params.get("detail") === "emails" ? "emails" : params.get("detail") === "verwaltung" ? "verwaltung" : "aktivitaet";
  const { data: users = [], isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => vertrag.get("/admin/users"),
  });
  // Der Rollen-Katalog kommt vom Server (Namen, Beschriftung, Rechte). Er
  // steht hier und nicht als Liste im Code, damit eine neue Rolle in
  // `kern/roles.py` im Panel erscheint, ohne dass jemand das Frontend anfasst.
  const { data: rollenKatalog = [] } = useQuery({
    queryKey: ["admin", "roles"],
    queryFn: () => vertrag.get("/admin/roles"),
    staleTime: 60 * 60 * 1000,  // ändert sich nur mit einem Deploy
  });

  if (isPending) return <Spinner />;
  if (isError) return <ErrorState title="Die Nutzer*innen konnten nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;

  const needle = q.trim().toLowerCase();
  // Nach dem Namen zu suchen ist der Normalfall: Man erinnert sich an „Anne",
  // nicht an ihre Adresse. Beides durchsuchen, damit keins der beiden fehlt.
  const filtered = needle
    ? users.filter((u) => `${u.display_name ?? ""} ${u.email}`.toLowerCase().includes(needle))
    : users;

  return (
    <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
      <Card className={cn("min-w-0 overflow-hidden p-0", selected != null && "hidden lg:block")}>
        <div className="flex flex-wrap items-center gap-3 border-b border-border bg-muted/30 px-4 py-3">
          <div className="relative flex-1">
            <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name oder E-Mail suchen…" aria-label="Konten durchsuchen"
              className="h-9 w-full rounded-[9px] border border-input bg-card pl-9 pr-3 text-base text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </div>
          <span className="shrink-0 text-xs text-muted-foreground">{users.length} Nutzer*innen</span>
        </div>
        <div className="divide-y divide-border">
          {filtered.map((u) => {
            const sig = activitySignal(u.last_seen);
            const chips = [
              u.n_topics > 0 && `${u.n_topics} ${u.n_topics === 1 ? "Thema" : "Themen"}`,
              u.n_ki > 0 && `${u.n_ki} KI-Fragen`,
              u.n_subscriptions > 0 && `${u.n_subscriptions} Abos`,
              u.n_quiz > 0 && "Quiz",
            ].filter(Boolean) as string[];
            // Womit gearbeitet wird — steht getrennt von den Inhalts-Chips, weil
            // es eine andere Art Auskunft ist (Kanal, nicht Menge).
            const womit = clientKurz(u.clients);
            return (
              <a key={u.id} href={`#users?user=${u.id}&detail=${section}`} aria-current={selected === u.id ? "true" : undefined}
                className={cn("block w-full px-4 py-3 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary",
                  selected === u.id && "bg-accent")}>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {/* Der Name steht vorn, die Adresse blass daneben: Konten
                        tragen seit 09/2026 einen Namen (Pflicht bei der
                        Registrierung), und ein Konto ist damit eine Person und
                        nicht mehr nur eine Adresse. Wer noch keinen hat —
                        Alt-Bestand —, erscheint weiter unter seiner Adresse. */}
                    <span className="flex w-full min-w-0 flex-col gap-0.5">
                      <span className="truncate text-sm font-semibold text-foreground">{u.display_name || u.email}</span>
                      {u.display_name && <span className="text-xs text-muted-foreground">{u.email}</span>}
                    </span>
                    {/* Ein Abzeichen JE Rolle: Seit ein Konto mehrere tragen
                        kann, verschwiege ein einzelnes „admin" das Ratsmandat
                        daneben. Die Beschriftung kommt aus dem Katalog, damit
                        eine neue Rolle hier ohne Codeänderung auftaucht. */}
                    {(u.roles ?? []).map((r) => (
                      <span key={r} className="shrink-0 rounded bg-primary/10 px-1.5 text-xs font-semibold text-primary">
                        {rollenKatalog.find((k) => k.key === r)?.label ?? r}
                      </span>
                    ))}
                    {u.status !== "active" && <span className="shrink-0 rounded bg-amber-500/15 px-1.5 text-xs font-semibold text-amber-700 dark:text-amber-500">{u.status === "disabled" ? "gesperrt" : "wartet"}</span>}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {womit && (
                      <span className="rounded bg-primary/10 px-1.5 py-px text-xs font-medium text-primary">{womit}</span>
                    )}
                    {chips.length ? chips.map((c) => (
                      <span key={c} className="rounded bg-muted px-1.5 py-px text-xs text-muted-foreground">{c}</span>
                    )) : <span className="rounded bg-muted px-1.5 py-px text-xs text-muted-foreground">noch nichts angelegt</span>}
                  </div>
                </div>
                <span className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground"><span className={cn("h-[7px] w-[7px] rounded-full", sig.dot)} />{sig.label}</span>
              </a>
            );
          })}
          {!filtered.length && <p className="px-4 py-6 text-center text-sm text-muted-foreground">Keine Nutzer*in passt zu „{q}".</p>}
        </div>
      </Card>

      {selected != null
        ? <UserDetailPanel key={selected} userId={selected} isSelf={selected === currentUserId}
                           rollenKatalog={rollenKatalog} section={section} />
        : <Card className="hidden p-8 text-center text-sm text-muted-foreground lg:block">Nutzer*in wählen, um Details zu sehen.</Card>}
    </div>
  );
}

function UserDetailPanel({ userId, isSelf, rollenKatalog, section }: {
  userId: number; isSelf: boolean; rollenKatalog: RolleInfo[]; section: "aktivitaet" | "emails" | "verwaltung";
}) {
  const qc = useQueryClient();
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${userId}`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "user", userId] });
    qc.invalidateQueries({ queryKey: ["admin", "users"] });
  };
  // Die VOLLSTÄNDIGE Liste geht raus, nicht ein Delta: Ein PUT mit dem
  // gewünschten Endzustand ist idempotent und kann sich nicht mit dem Klick
  // eines zweiten Admins überkreuzen.
  const rollenMutation = useMutation({
    mutationFn: (roles: string[]) => api.put(`/admin/users/${userId}/roles`, { roles }),
    onSuccess: () => { toast.success("Rollen aktualisiert."); invalidate(); },
    onError: () => toast.error("Rollen konnten nicht geändert werden."),
  });
  const statusMutation = useMutation({
    mutationFn: (status: "active" | "disabled") => api.put(`/admin/users/${userId}/status`, { status }),
    onSuccess: (_, status) => { toast.success(status === "active" ? "Freigeschaltet." : "Gesperrt."); invalidate(); },
    onError: () => toast.error("Status konnte nicht geändert werden."),
  });
  const limitsMutation = useMutation({
    mutationFn: (limits: { deep_limit: number | null; limits_unlocked: boolean }) =>
      api.put(`/admin/users/${userId}/limits`, limits),
    onSuccess: () => { toast.success("Limits aktualisiert."); invalidate(); },
    onError: () => toast.error("Limits konnten nicht gespeichert werden."),
  });

  if (isPending) return <Card className="p-6"><Spinner /></Card>;
  if (isError || !data) return <ErrorState title="Das Konto konnte nicht geladen werden" onRetry={() => void refetch()} busy={isFetching} />;

  const sig = activitySignal(data.last_seen);
  const login = data.apple_linked ? "Apple-Login" : data.has_password ? "Passwort" : "Apple-Login";
  // „Wie angemeldet" heißt hier zweierlei: mit welchem Verfahren (Apple oder
  // Passwort) und von welchem Client aus. Beides gehört in die Kopfzeile.
  const woher = data.signup_client ? clientLabel(data.signup_client) : null;
  // Nur Gemessenes zeigen. `unknown` sind Zeilen von vor der Messung — sie als
  // eigenen Balken zu führen behauptete eine Plattform, die niemand kennt.
  const nutzung = Object.entries((data.clients ?? {}) as Record<string, number>)
    .filter(([id, n]) => id !== "unknown" && n > 0)
    .sort((a, b) => b[1] - a[1]);
  const nutzungGesamt = nutzung.reduce((s, [, n]) => s + n, 0);
  const fuehrend = hauptClient((data.clients ?? {}) as Record<string, number>);
  return (
    <Card className="min-w-0 p-4 sm:p-5 [overflow-wrap:anywhere]">
      <a href="#users" className="mb-4 inline-flex min-h-11 items-center gap-2 text-sm text-primary lg:hidden"><ArrowLeft className="h-4 w-4" aria-hidden />Zur Kontenliste</a>
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/10 font-display text-base font-bold text-primary">{(data.display_name || data.email)[0].toUpperCase()}</span>
        <div className="min-w-0 flex-1">
          <p className="font-display text-xl font-bold text-foreground">{data.display_name || data.email}</p>
          {data.display_name && <p className="text-sm text-muted-foreground">{data.email}</p>}
          <p className="text-xs text-muted-foreground">
            seit {formatDate(data.created_at.slice(0, 10))} · {sig.label} · {login}
            {woher && <> · über {woher} registriert</>}
          </p>
        </div>
      </div>
      <nav aria-label="Kontodetails" className="mt-5 flex flex-wrap gap-x-4 border-b border-border">
        {([["aktivitaet", "Aktivität"], ["emails", "E-Mails"], ["verwaltung", "Verwaltung"]] as const).map(([key, label]) => (
          <a key={key} href={`#users?user=${userId}&detail=${key}`} aria-current={section === key ? "page" : undefined}
            className={cn("flex min-h-11 items-center border-b-2 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", section === key ? "border-primary font-semibold text-primary" : "border-transparent text-muted-foreground")}>{label}</a>
        ))}
      </nav>
      {section === "emails" && <UserMailHistory userId={userId} channel={data.delivery_channel} />}
      {section === "aktivitaet" && <>
      {/* Womit gearbeitet wird (Zugriffe je Client). Anteile statt roher
          Zahlen: Die Frage ist „App oder Web?", nicht „wie viele Requests". */}
      <StatKickerSpaced>Womit genutzt</StatKickerSpaced>
      {nutzung.length ? (
        <div className="mt-2 flex flex-col gap-1.5">
          <div className="flex h-2 overflow-hidden rounded-full bg-muted">
            {nutzung.map(([id, n]) => (
              <span key={id} title={`${clientLabel(id)}: ${n}`}
                className={cn("h-full", clientFarbe(id))}
                style={{ width: `${(n / nutzungGesamt) * 100}%` }} />
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {nutzung.map(([id, n]) => (
              <span key={id} className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                <span className={cn("h-2 w-2 rounded-full", clientFarbe(id))} />
                {clientLabel(id)}
                <span className="font-semibold tabular-nums text-foreground">
                  {Math.round((n / nutzungGesamt) * 100)} %
                </span>
              </span>
            ))}
            {nutzung.length > 1 && fuehrend && (
              <span className="inline-flex items-center rounded-full border border-dashed border-border px-2.5 py-1 text-xs text-muted-foreground">
                überwiegend {clientLabel(fuehrend)}
              </span>
            )}
          </div>
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          Noch nichts gemessen — die Zuordnung läuft erst seit 09/2026 mit.
        </p>
      )}

      <StatKickerSpaced>Genutzte Features</StatKickerSpaced>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {USER_FEATURE_LABEL.map(([key, label]) => {
          const n = data.features[key];
          const suffix = key === "quiz" ? (n === 1 ? "1 Runde" : `${n} Runden`) : `${n}×`;
          return n > 0
            ? <span key={key} className="rounded-full bg-primary/[0.08] px-2.5 py-1 text-xs font-medium text-primary">{label} · {suffix}</span>
            : <span key={key} className="rounded-full border border-dashed border-border px-2.5 py-1 text-xs text-muted-foreground">{label} · nie</span>;
        })}
      </div>

      <StatKickerSpaced>Angelegt</StatKickerSpaced>
      <div className="mt-2 flex flex-col gap-1.5">
        <DetailList
          label={`${data.topics.length} ${data.topics.length === 1 ? "Thema" : "Themen"}`}
          entries={data.topics}
          empty="Noch keins angelegt"
        />
        <DetailList
          label={`${data.subscriptions.length} Ausschuss-${data.subscriptions.length === 1 ? "Abo" : "Abos"}`}
          entries={data.subscriptions}
          empty="Keiner abonniert"
        />
        <DetailRow label="Zustellung" value={data.delivery_channel === "both" ? "Push + E-Mail" : data.delivery_channel === "push" ? "Push" : data.delivery_channel === "off" ? "Aus" : "E-Mail"} />
        <DetailRow label="Gespräche speichern" value={data.saves_conversations === 1 ? "An" : data.saves_conversations === 0 ? "Bewusst aus" : "Nie gefragt"} />
      </div>

      <StatKickerSpaced>Aktivität (30 Tage)</StatKickerSpaced>
      <AdminVerlauf values={data.history} days={data.history_days} label="Aktivitäten" />
      </>}
      {section === "verwaltung" && <>

      {/* Rollen. Bis 09/2026 stand hier ein Umschalt-Knopf „Zu Admin" — der
          ging nur, solange es zwei Rollen gab. Jetzt trägt ein Konto mehrere,
          und jede ist ein eigener Schalter. */}
      <StatKickerSpaced>Rollen</StatKickerSpaced>
      <div className="mt-2 flex flex-col gap-1.5">
        {rollenKatalog.filter((r) => r.assignable).map((r) => {
          const an = (data.roles ?? []).includes(r.key);
          // Sich selbst die Adminrechte zu nehmen ist der eine Fehler ohne
          // Undo: Danach kommt niemand mehr ins Panel. Der Server weist es
          // ohnehin ab (400) — hier steht der Schalter gar nicht erst zur
          // Verfügung, statt einen Klick anzubieten, der scheitert.
          const gesperrt = isSelf && r.key === "admin" && an;
          return (
            <button
              key={r.key}
              type="button"
              disabled={gesperrt || rollenMutation.isPending}
              aria-pressed={an}
              onClick={() => rollenMutation.mutate(
                an ? (data.roles ?? []).filter((x) => x !== r.key) : [...(data.roles ?? []), r.key])}
              className={cn(
                "flex items-start gap-3 rounded-[10px] border px-3 py-2.5 text-left transition-colors",
                an ? "border-primary/40 bg-primary/[0.06]" : "border-border bg-card hover:bg-accent",
                gesperrt && "cursor-not-allowed opacity-60",
              )}
            >
              <span className={cn(
                "mt-px flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] border",
                an ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background",
              )} aria-hidden>
                {an && (
                  <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor"
                       strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><path d="m5 13 4 4L19 7" /></svg>
                )}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-foreground">{r.label}</span>
                <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
                  {gesperrt ? "Du kannst dir die Adminrechte nicht selbst entziehen." : r.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {!isSelf && (
        <div className="mt-4 flex gap-2 border-t border-border pt-4">
          <Button variant="secondary" size="sm"
            onClick={() => statusMutation.mutate(data.status === "active" ? "disabled" : "active")}>
            {data.status === "active" ? "Sperren" : "Freischalten"}
          </Button>
        </div>
      )}

      {/* Frage-Limits je Konto: Recherche-Tageskontingent (leer = Standard 5,
          0 = unbegrenzt) + Befreiung von den Rate-Limitern der Frage-Endpoints. */}
      <StatKickerSpaced>Frage-Limits</StatKickerSpaced>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm">
          Recherchen/Tag
          <input
            type="number" min={0} max={999}
            defaultValue={data.deep_limit ?? ""}
            placeholder="Standard (5)"
            key={`dl-${data.id}-${data.deep_limit ?? "std"}`}
            id={`deep-limit-${data.id}`}
            className="w-24 rounded-md border border-border bg-background px-2 py-1 text-sm"
          />
        </label>
        <Button variant="secondary" size="sm"
          onClick={() => {
            const el = document.getElementById(`deep-limit-${data.id}`) as HTMLInputElement | null;
            const roh = (el?.value ?? "").trim();
            const value = roh === "" ? null : Math.max(0, Math.min(999, Number(roh)));
            if (value !== null && Number.isNaN(value)) return;
            limitsMutation.mutate({ deep_limit: value, limits_unlocked: data.limits_unlocked });
          }}>
          Speichern
        </Button>
        <Button variant="secondary" size="sm"
          onClick={() => limitsMutation.mutate({ deep_limit: data.deep_limit, limits_unlocked: !data.limits_unlocked })}>
          {data.limits_unlocked ? "Rate-Limits wieder an" : "Rate-Limits aus"}
        </Button>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground/70">
        {data.deep_limit === 0 ? "Recherche: unbegrenzt." : data.deep_limit != null
          ? `Recherche: ${data.deep_limit}/Tag.` : "Recherche: Standard (5/Tag)."}
        {" "}0 = unbegrenzt, leer = Standard.
        {data.limits_unlocked && " · Rate-Limits (schnelle Frage, Parteien, Teilen) sind für dieses Konto AUS."}
      </p>
      </>}
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Alles server-aggregiert & nur für Admins; nur eigene App-Aktivität, keine Dritt-Analytics.
      </p>
    </Card>
  );
}

function StatKickerSpaced({ children }: { children: React.ReactNode }) {
  return <p className="mt-4 text-xs font-bold uppercase tracking-[0.06em] text-muted-foreground">{children}</p>;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2">
      <span className="shrink-0 text-sm text-foreground">{label}</span>
      <span className="text-xs text-muted-foreground">{value}</span>
    </div>
  );
}

/** Ab so vielen Einträgen startet die Liste zugeklappt. Darunter passt sie in
 *  ein, zwei Zeilen und kostet offen nichts; ein Konto mit fünfzehn Abos
 *  schöbe offen alles darunter — Zustellung, Verlauf, Rollen, Limits — aus dem
 *  Blick, und das sind die Dinge, wegen derer man das Detail aufmacht. */
const DETAIL_LISTE_ZU_AB = 8;

/** Angelegtes als VOLLSTÄNDIGE Liste — Themen und Ausschuss-Abos.
 *
 *  Bis 09/2026 stand hier eine `DetailRow`: die ersten vier Namen,
 *  kommagetrennt, in einer Zeile mit `truncate` — je nach Breite waren also
 *  zwei zu sehen, und nichts deutete darauf hin, dass mehr da sind. Wer wissen
 *  wollte, WELCHE Themen ein Konto angelegt hat, musste in die Datenbank
 *  (gemessen an Konto 37: 10 Themen, 15 Abos, im Panel sichtbar 2 bzw. 1).
 *  Die Zahl im Label bleibt, die Namen stehen vollständig darunter.
 *
 *  Natives `<details>` wie bei den Cron-Schritten weiter oben: Tastatur und
 *  Screenreader können das ohne Zutun, und der Zustand gehört dem Element, es
 *  braucht keinen React-State. `open` steht nur für den ERSTEN Aufbau — danach
 *  führt das DOM den Zustand, React fasst ihn nicht wieder an, solange der Wert
 *  derselbe bleibt. Der Wechsel auf ein anderes Konto baut die Karte neu auf
 *  (eigener Query-Key), die Vorgabe greift also je Konto frisch. */
function DetailList({ label, entries, empty }: { label: string; entries: string[]; empty: string }) {
  // Nichts da, nichts zum Aufklappen: ein Satz, kein Pfeil, der ins Leere führt.
  if (!entries.length) {
    return (
      <div className="rounded-lg border border-border bg-card px-3 py-2">
        <p className="text-sm text-foreground">{label}</p>
        <p className="mt-1 text-xs text-muted-foreground">{empty}</p>
      </div>
    );
  }
  return (
    <details className="group rounded-lg border border-border bg-card px-3 py-2"
      open={entries.length < DETAIL_LISTE_ZU_AB}>
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-foreground [&::-webkit-details-marker]:hidden">
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-fluss ease-out-strong group-open:rotate-180" />
        {label}
      </summary>
      {/* Themen dürfen doppelt heißen (zwei Konten, ein Wort — und auch
          innerhalb eines Kontos verbietet es niemand), der Index gehört
          deshalb in den Key. */}
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {entries.map((eintrag, i) => (
          <span key={`${i}-${eintrag}`}
            className="rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs text-muted-foreground">
            {eintrag}
          </span>
        ))}
      </div>
    </details>
  );
}

