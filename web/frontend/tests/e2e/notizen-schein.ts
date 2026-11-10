/**
 * Ein kleiner Schein-Server für `/api/notes` (Browsertests `32-notizen`,
 * `33-mitschrieb`). Er hält wie der echte nur Blobs; Form und Version des
 * echten prüft `tests/test_notizen.py`. So laufen die Tests auch gegen das
 * Backend der CI, das den Schalter `notizen` nicht kennt.
 */
import type { Page, Route } from "@playwright/test";

export type Ablage = { keys: Record<string, unknown> | null; notes: Map<string, Record<string, unknown>> };

export async function notizenSchein(page: Page, ablage: Ablage) {
  await page.route("**/api/notes**", async (route: Route) => {
    const req = route.request();
    const pfad = new globalThis.URL(req.url()).pathname.replace(/^\/api\/notes/, "");
    const body = req.postData() ? JSON.parse(req.postData()!) : null;
    const jetzt = new Date().toISOString().slice(0, 19);
    if (pfad === "/keys") {
      if (req.method() === "GET") return route.fulfill({ json: { configured: !!ablage.keys, keys: ablage.keys } });
      if (req.method() === "DELETE") { ablage.keys = null; ablage.notes.clear(); return route.fulfill({ json: { deleted: 0 } }); }
      if (body.wrapped_recovery) {
        if (ablage.keys) return route.fulfill({ status: 409, json: { detail: "Notizen sind schon eingerichtet." } });
        ablage.keys = { ...body, updated_at: jetzt };
      } else {
        ablage.keys = { ...ablage.keys, ...body, updated_at: jetzt };
      }
      return route.fulfill({ json: { configured: true, keys: ablage.keys } });
    }
    if (pfad === "" || pfad === "/") {
      const q = new globalThis.URL(req.url()).searchParams;
      const notes = [...ablage.notes.values()].filter((n) =>
        (!q.get("target_kind") || n.target_kind === q.get("target_kind"))
        && (!q.get("target_key") || n.target_key === q.get("target_key")));
      return route.fulfill({ json: { notes } });
    }
    const [, kind, key, art] = pfad.split("/").map(decodeURIComponent);
    const id = `${kind}|${key}|${art}`;
    const alt = ablage.notes.get(id);
    if (req.method() === "DELETE") { ablage.notes.delete(id); return route.fulfill({ status: 204, body: "" }); }
    if ((alt?.version ?? 0) !== body.version) {
      return route.fulfill({ status: 409, json: { detail: { message: "geändert", current: alt ?? null } } });
    }
    const neu = { target_kind: kind, target_key: key, kind: art, iv: body.iv, ciphertext: body.ciphertext,
                  key_version: body.key_version, version: (alt?.version as number ?? 0) + 1, updated_at: jetzt };
    ablage.notes.set(id, neu);
    return route.fulfill({ json: neu });
  });
}

