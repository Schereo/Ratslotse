"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Search, ChevronRight, Newspaper } from "lucide-react";
import { api, qs, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDebounce } from "@/lib/use-debounce";
import { Article, SearchResult } from "@/lib/types";
import { categoryLabel } from "@/lib/categories";
import { NwzReadHint } from "@/components/nwz-link";
import {
  Badge, Card, CardListSkeleton, EmptyState, Input, PageHeader, Pagination, Select, DateField, formatDate,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, toast,
} from "@/components/ui";

export default function NwzSearchPage() {
  // Suspense boundary required because NwzSearch reads useSearchParams().
  return (
    <Suspense>
      <NwzSearch />
    </Suspense>
  );
}

const PAGE_SIZE = 50;

function NwzSearch() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [categories, setCategories] = useState<string[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [openArticle, setOpenArticle] = useState<Article | null>(null);
  const { user } = useAuth();
  const fulltextAllowed = user?.role === "admin" || !!user?.nwz_fulltext_allowed;

  const debouncedQ = useDebounce(q, 350);
  const searchParams = useSearchParams();

  useEffect(() => {
    api.get<{ categories: string[] }>("/nwz/categories").then((d) => setCategories(d.categories)).catch(() => {});
  }, []);

  // Deep link from email/Telegram (e.g. session follow-up): open a specific
  // article on load when ?catalog=…&refid=… is present.
  useEffect(() => {
    const catalog = searchParams.get("catalog");
    const refid = searchParams.get("refid");
    if (!catalog || !refid) return;
    api.get<Article>(`/nwz/article/${catalog}?refid=${encodeURIComponent(refid)}`)
      .then(setOpenArticle)
      .catch(() => toast.error("Artikel konnte nicht geladen werden."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const search = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ results: SearchResult[]; total: number }>(
        `/nwz/search${qs({ q, category, date_from: dateFrom, date_to: dateTo, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE })}`,
      );
      setResults(data.results);
      setTotal(data.total);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Suche fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  }, [q, category, dateFrom, dateTo, page]);

  // Instant search on debounced query / filter / page change (also on mount).
  useEffect(() => {
    search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ, category, dateFrom, dateTo, page]);

  const openDetail = async (r: SearchResult) => {
    try {
      setOpenArticle(await api.get<Article>(`/nwz/article/${r.catalog}?refid=${encodeURIComponent(r.refid)}`));
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
              onChange={(e) => { setQ(e.target.value); setPage(1); }}
              autoFocus
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Rubrik</span>
              <Select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
                <option value="">Alle Rubriken</option>
                {categories.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
              </Select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Von</span>
              <DateField value={dateFrom} onChange={(v) => { setDateFrom(v); setPage(1); }} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Bis</span>
              <DateField value={dateTo} onChange={(v) => { setDateTo(v); setPage(1); }} />
            </label>
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
            <p className="text-sm font-medium text-muted-foreground">{total} Treffer</p>
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
                        {r.category_name && <Badge>{categoryLabel(r.category_name)}</Badge>}
                      </div>
                      <h3 className="mt-1 font-semibold text-foreground">{r.title}</h3>
                      {r.subtitle && <p className="line-clamp-1 text-sm text-muted-foreground">{r.subtitle}</p>}
                      {fulltextAllowed && r.excerpt && (
                        <p className="excerpt mt-1 line-clamp-2 text-sm text-foreground/80" dangerouslySetInnerHTML={{ __html: r.excerpt }} />
                      )}
                    </div>
                    <ChevronRight className="mt-1 h-5 w-5 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </div>
                </Card>
              </button>
            ))}
            <Pagination
              page={page}
              totalPages={Math.ceil(total / PAGE_SIZE)}
              onChange={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); }}
              className="pt-2"
            />
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
              {fulltextAllowed ? (
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
                  {openArticle.content_text}
                </div>
              ) : (
                <div className="pt-1">
                  <NwzReadHint title={openArticle.title || ""} />
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
