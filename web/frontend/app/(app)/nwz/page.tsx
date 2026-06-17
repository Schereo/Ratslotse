"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, ShieldCheck, ChevronRight, Newspaper } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDebounce } from "@/lib/use-debounce";
import { Article, SearchResult } from "@/lib/types";
import {
  Badge, Button, Card, CardListSkeleton, EmptyState, Input, Label, PageHeader, Select, formatDate,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, PasswordInput, toast,
} from "@/components/ui";

export default function NwzSearchPage() {
  const { user, refresh } = useAuth();

  if (!user?.nwz_verified) return <NwzCredentialsGate onVerified={refresh} />;
  return <NwzSearch />;
}

function NwzCredentialsGate({ onVerified }: { onVerified: () => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/account/nwz-credentials", { nwz_username: username, nwz_password: password });
      toast.success("NWZ-Zugang verifiziert.");
      await onVerified();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verifizierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Artikelsuche" description="Volltextsuche im Artikel-Archiv der Nordwest-Zeitung." />
      <Card className="mx-auto mt-6 max-w-md p-6">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-primary" />
          <h2 className="font-semibold text-foreground">Eigene NWZ-Zugangsdaten</h2>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Um NWZ-Inhalte zu durchsuchen, hinterlege bitte deine eigenen NWZ-Login-Daten. Wir prüfen sie
          einmalig bei der NWZ und speichern <b>nicht</b> dein Passwort.
        </p>
        <form onSubmit={submit} className="mt-4 space-y-3">
          <div>
            <Label htmlFor="nwz-user">NWZ-Benutzername / E-Mail</Label>
            <Input id="nwz-user" className="mt-1" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </div>
          <div>
            <Label htmlFor="nwz-pass">NWZ-Passwort</Label>
            <PasswordInput id="nwz-pass" className="mt-1" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Prüfe…" : "Verifizieren"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

function NwzSearch() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [openArticle, setOpenArticle] = useState<Article | null>(null);

  const debouncedQ = useDebounce(q, 350);

  useEffect(() => {
    api.get<{ categories: string[] }>("/nwz/categories").then((d) => setCategories(d.categories)).catch(() => {});
  }, []);

  const search = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ results: SearchResult[] }>(
        `/nwz/search${qs({ q, category, date_from: dateFrom, date_to: dateTo, limit: 50 })}`,
      );
      setResults(data.results);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Suche fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q, category, dateFrom, dateTo]);

  // Instant search: re-run whenever the debounced query or any filter changes
  // (also fires on mount, since debouncedQ initialises to "").
  useEffect(() => {
    search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, category, dateFrom, dateTo]);

  const openDetail = async (r: SearchResult) => {
    try {
      setOpenArticle(await api.get<Article>(`/nwz/article/${r.catalog}/${encodeURIComponent(r.refid)}`));
    } catch {
      toast.error("Artikel konnte nicht geladen werden.");
    }
  };

  return (
    <div>
      <PageHeader title="Artikelsuche" description="Volltextsuche im Artikel-Archiv der Nordwest-Zeitung." />

      <Card className="mt-6 p-4">
        <form onSubmit={(e) => { e.preventDefault(); search(); }} className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Suchbegriff (z. B. Radwege, Stadtpark)…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              autoFocus
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Alle Rubriken</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
        </form>
      </Card>

      <div className="mt-6">
        {loading ? (
          <CardListSkeleton rows={5} />
        ) : results.length === 0 ? (
          <EmptyState
            icon={Newspaper}
            title="Keine Artikel gefunden"
            hint="Versuche andere Suchbegriffe oder passe die Filter an."
          />
        ) : (
          <div className="space-y-3">
            <p className="text-sm font-medium text-muted-foreground">{results.length} Treffer</p>
            {results.map((r) => (
              <button
                key={`${r.catalog}-${r.refid}`}
                type="button"
                className="block w-full text-left"
                onClick={() => openDetail(r)}
              >
                <Card className="card-interactive group p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span>{formatDate(r.pub_date)}</span>
                        {r.category_name && <Badge>{r.category_name}</Badge>}
                      </div>
                      <h3 className="mt-1 font-semibold text-foreground">{r.title}</h3>
                      {r.subtitle && <p className="line-clamp-1 text-sm text-muted-foreground">{r.subtitle}</p>}
                      <p className="excerpt mt-1 line-clamp-2 text-sm text-foreground/80" dangerouslySetInnerHTML={{ __html: r.excerpt }} />
                    </div>
                    <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </Card>
              </button>
            ))}
          </div>
        )}
      </div>

      <Dialog open={!!openArticle} onOpenChange={(o) => !o && setOpenArticle(null)}>
        <DialogContent>
          {openArticle && (
            <>
              <DialogHeader>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{formatDate(openArticle.publication_date)}</span>
                  {openArticle.category_name && <Badge>{openArticle.category_name}</Badge>}
                  {openArticle.page ? <Badge color="blue">Seite {openArticle.page}</Badge> : null}
                </div>
                <DialogTitle>{openArticle.title}</DialogTitle>
                {openArticle.subtitle && <DialogDescription>{openArticle.subtitle}</DialogDescription>}
                {openArticle.authors && (
                  <p className="text-sm text-muted-foreground">{openArticle.authors.replace(/\|/g, ", ")}</p>
                )}
              </DialogHeader>
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                {openArticle.content_text}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
