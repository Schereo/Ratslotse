import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { toast } from "@/components/ui";

/** GET `path` on mount (and whenever it changes). Returns `{ data, loading }`.
 *  Toasts on non-404 errors; a 404 just leaves `data` null. Pass `null` to skip. */
export function useFetch<T>(path: string | null): { data: T | null; loading: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(path !== null);

  useEffect(() => {
    if (path === null) return;
    let active = true;
    setLoading(true);
    api.get<T>(path)
      .then((d) => { if (active) setData(d); })
      .catch((e) => { if (active && e instanceof ApiError && e.status !== 404) toast.error(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path]);

  return { data, loading };
}
