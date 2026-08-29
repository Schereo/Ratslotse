import "server-only";

/** Preview fixtures are allowed in Vercel previews and explicit local development only. */
export function buergerportalVorschauAktiv(): boolean {
  return process.env.VERCEL_ENV === "preview"
    || (process.env.NODE_ENV !== "production"
      && process.env.NEXT_PUBLIC_BUERGERPORTAL_VORSCHAU === "1");
}
