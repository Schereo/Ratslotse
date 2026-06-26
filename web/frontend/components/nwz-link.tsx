import { ExternalLink } from "lucide-react";

/** NWZonline search for a headline — the e-Paper feed carries no canonical article URL,
 *  so we link to the search (which surfaces the article). Trailing slash is required:
 *  /suche/?query=… works, /suche?query=… leaves the search box empty. */
export function nwzSearchUrl(title: string): string {
  return `https://www.nwzonline.de/suche/?query=${encodeURIComponent(title || "")}`;
}

/** A small, neutral "read at NWZonline" link — no mention of access tiers. */
export function NwzReadHint({ title }: { title: string }) {
  return (
    <a
      href={nwzSearchUrl(title)}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
    >
      <ExternalLink className="h-3.5 w-3.5" /> Bei NWZonline lesen
    </a>
  );
}
