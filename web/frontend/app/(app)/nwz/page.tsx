"use client";

import { useEffect, useState, useCallback } from "react";
import { api, qs } from "@/lib/api";
import { Article, SearchResult } from "@/lib/types";
import { Badge, Button, Card, EmptyState, Input, Spinner, formatDate } from "@/components/ui";

export default function NwzSearchPage() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [openArticle, setOpenArticle] = useState<Article | null>(null);

  useEffect(() => {
    api.get<{ categories: string[] }>("/nwz/categories").then((d) => setCategories(d.categories)).catch(() => {});
  }, []);

  const search = useCallback(async () => {
    setLoading(true);
    setSearched(true);
    try {
      const data = await api.get<{ results: SearchResult[] }>(
        `/nwz/search${qs({ q, category, date_from: dateFrom, date_to: dateTo, limit: 50 })}`,
      );
      setResults(data.results);
    } finally {
      setLoading(false);
    }
  }, [q, category, dateFrom, dateTo]);

  useEffect(() => {
    search();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDetail = async (r: SearchResult) => {
    const art = await api.get<Article>(`/nwz/article/${r.catalog}/${encodeURIComponent(r.refid)}`);
    setOpenArticle(art);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">NWZ-Suche</h1>
      <p className="mt-1 text-sm text-slate-500">Volltextsuche im Artikel-Archiv der Nordwest-Zeitung.</p>

      <Card className="mt-6 p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            search();
          }}
          className="space-y-3"
        >
          <Input placeholder="Suchbegriff (z. B. Radwege, Stadtpark)…" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">Alle Rubriken</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <Button type="submit">Suchen</Button>
        </form>
      </Card>

      <div className="mt-6">
        {loading ? (
          <Spinner />
        ) : results.length === 0 ? (
          searched && <EmptyState title="Keine Artikel gefunden" hint="Versuche andere Suchbegriffe oder Filter." />
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">{results.length} Treffer</p>
            {results.map((r) => (
              <Card key={`${r.catalog}-${r.refid}`} className="cursor-pointer p-4 transition-shadow hover:shadow-md" >
                <div onClick={() => openDetail(r)}>
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <span>{formatDate(r.pub_date)}</span>
                    {r.category_name && <Badge>{r.category_name}</Badge>}
                  </div>
                  <h3 className="mt-1 font-semibold text-slate-900">{r.title}</h3>
                  {r.subtitle && <p className="text-sm text-slate-500">{r.subtitle}</p>}
                  <p className="excerpt mt-1 text-sm text-slate-600" dangerouslySetInnerHTML={{ __html: r.excerpt }} />
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {openArticle && <ArticleModal article={openArticle} onClose={() => setOpenArticle(null)} />}
    </div>
  );
}

function ArticleModal({ article, onClose }: { article: Article; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4" onClick={onClose}>
      <Card className="my-8 w-full max-w-2xl p-6" >
        <div onClick={(e) => e.stopPropagation()}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>{formatDate(article.publication_date)}</span>
                {article.category_name && <Badge>{article.category_name}</Badge>}
                {article.page ? <Badge color="blue">Seite {article.page}</Badge> : null}
              </div>
              <h2 className="mt-2 text-xl font-bold text-slate-900">{article.title}</h2>
              {article.subtitle && <p className="mt-1 text-slate-500">{article.subtitle}</p>}
              {article.authors && <p className="mt-1 text-sm text-slate-400">{article.authors.replace(/\|/g, ", ")}</p>}
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}>
              ✕
            </Button>
          </div>
          <div className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{article.content_text}</div>
        </div>
      </Card>
    </div>
  );
}
