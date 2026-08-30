/**
 * Antworttypen aus dem API-Vertrag — statt sie abzuschreiben.
 *
 * `lib/api-schema.ts` wird aus `api/openapi.json` generiert (siehe
 * `npm run api:typen`) und ist roh: verschachtelte `paths`-Objekte mit
 * `responses`/`content`/`application/json`. Dieses Modul macht daraus etwas,
 * das man an einer Aufrufstelle hinschreiben mag.
 *
 * **Warum überhaupt.** Es gibt zwei Frontends (dieses und die iOS-App), die
 * featuregleich bleiben sollen. Ein von Hand getippter Antworttyp ist eine
 * zweite Wahrheit neben dem Backend — er veraltet lautlos, und zwar in jedem
 * Frontend einzeln. Ein generierter Typ bricht den Build, sobald das Feld weg
 * ist.
 *
 * **Pfad-Schreibweise.** `api.get("/council/…")` hängt das `/api`-Präfix
 * selbst an; die Typen hier nehmen deshalb denselben Pfad OHNE `/api`, damit
 * Aufruf und Typ gleich aussehen.
 */
import { api } from "./api";
import type { paths } from "./api-schema";

/** Die 200/201/202-Nutzlast einer Operation, egal unter welchem Code sie steht. */
type Erfolg<O> =
  O extends { responses: { 200: { content: { "application/json": infer T } } } } ? T :
  O extends { responses: { 201: { content: { "application/json": infer T } } } } ? T :
  O extends { responses: { 202: { content: { "application/json": infer T } } } } ? T :
  never;

type MitApi<P extends string> = `/api${P}`;
type Methode = "get" | "post" | "put" | "delete";

/** Alle Pfade (ohne `/api`), die diese Methode kennen. */
export type Pfad<M extends Methode> = {
  [P in keyof paths]: paths[P] extends Record<M, object>
    ? P extends MitApi<infer Rest> ? Rest : never
    : never;
}[keyof paths];

/**
 * Der Antworttyp eines Endpunkts.
 *
 * Auch für Pfade mit Parametern verwendbar — dort steht die Vorlage aus dem
 * Vertrag, nicht der konkrete Pfad:
 *
 * ```ts
 * type Beschluss = ApiAntwort<"/council/decision/{decision_id}">;
 * const d = await api.get<Beschluss>(`/council/decision/${id}`);
 * ```
 */
export type ApiAntwort<P extends string, M extends Methode = "get"> =
  MitApi<P> extends keyof paths
    ? paths[MitApi<P>] extends Record<M, infer O> ? Erfolg<O> : never
    : never;

/**
 * Wie `api`, nur dass der Antworttyp aus dem Vertrag kommt statt aus dem
 * Kopf der Person, die den Aufruf schreibt.
 *
 * Funktioniert für Pfade ohne Parameter — nur die sind als Literal typisierbar.
 * Für `/council/decision/${id}` bleibt `api.get<ApiAntwort<…>>(…)` der Weg;
 * der Typ stammt auch dann aus dem Vertrag, nur die Zuordnung ist von Hand.
 */
export const vertrag = {
  get: <P extends Pfad<"get"> & string>(pfad: P) =>
    api.get<ApiAntwort<P, "get">>(pfad),
  post: <P extends Pfad<"post"> & string>(pfad: P, body?: unknown) =>
    api.post<ApiAntwort<P, "post">>(pfad, body),
  put: <P extends Pfad<"put"> & string>(pfad: P, body?: unknown) =>
    api.put<ApiAntwort<P, "put">>(pfad, body),
  del: <P extends Pfad<"delete"> & string>(pfad: P, body?: unknown) =>
    api.del<ApiAntwort<P, "delete">>(pfad, body),
};
