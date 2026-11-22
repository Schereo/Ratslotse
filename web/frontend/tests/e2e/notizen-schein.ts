/**
 * Ein kleiner Schein-Server für `/api/notes` (Browsertests `32-notizen`,
 * `33-mitschrieb`). Er hält wie der echte nur Blobs; Form und Version des
 * echten prüft `tests/test_notizen.py`. So laufen die Tests auch gegen das
 * Backend der CI, das den Schalter `notizen` nicht kennt.
 */
import type { Page, Route } from "@playwright/test";

export type Ablage = {
  keys: Record<string, unknown> | null;
  notes: Map<string, Record<string, unknown>>;
  passkeys?: Record<string, unknown>[];
};

/** Vor dem Passphrase-Weg: Wo der Browser Passkeys kann, steht erst das
 *  Passkey-Angebot da — dann „Lieber mit Passphrase“. */
export async function passphraseWeg(karte: import("@playwright/test").Locator) {
  const lieber = karte.getByRole("button", { name: "Lieber mit Passphrase" });
  await lieber.or(karte.locator("input[type=password]").first()).first().waitFor();
  if (await lieber.isVisible()) await lieber.click();
}

export async function notizenSchein(page: Page, ablage: Ablage) {
  await page.route("**/api/notes**", async (route: Route) => {
    const req = route.request();
    const pfad = new globalThis.URL(req.url()).pathname.replace(/^\/api\/notes/, "");
    const body = req.postData() ? JSON.parse(req.postData()!) : null;
    const jetzt = new Date().toISOString().slice(0, 19);
    const passkeys = () => (ablage.passkeys ??= []);
    const zustand = () => ({
      configured: !!ablage.keys,
      keys: ablage.keys ? { wrapped_passphrase: null, wrapped_recovery: null, ...ablage.keys } : null,
      passkeys: ablage.keys ? passkeys() : [],
    });
    if (pfad === "/keys") {
      if (req.method() === "GET") return route.fulfill({ json: zustand() });
      if (req.method() === "DELETE") {
        ablage.keys = null; ablage.notes.clear(); ablage.passkeys = [];
        return route.fulfill({ json: { deleted: 0 } });
      }
      const { passkey, ...rest } = body;
      if (rest.wrapped_recovery || passkey || !ablage.keys) {
        if (ablage.keys) return route.fulfill({ status: 409, json: { detail: "Notizen sind schon eingerichtet." } });
        ablage.keys = { ...rest, updated_at: jetzt };
        if (passkey) passkeys().push({ id: 1, ...passkey, created_at: jetzt });
      } else {
        ablage.keys = { ...ablage.keys, ...rest, updated_at: jetzt };
      }
      return route.fulfill({ json: zustand() });
    }
    if (pfad === "/keys/recovery") {
      ablage.keys = { ...ablage.keys, wrapped_recovery: body.wrapped_recovery, updated_at: jetzt };
      return route.fulfill({ json: zustand() });
    }
    if (pfad === "/passkeys" && req.method() === "POST") {
      const { key_version: _v, ...pk } = body;
      passkeys().push({ id: passkeys().length + 1, ...pk, created_at: jetzt });
      return route.fulfill({ json: zustand() });
    }
    if (pfad.startsWith("/passkeys/") && req.method() === "DELETE") {
      ablage.passkeys = passkeys().filter((p) => String(p.id) !== pfad.split("/")[2]);
      return route.fulfill({ json: zustand() });
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

