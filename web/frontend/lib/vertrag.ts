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

/** Der Pfad ohne Query-String — viele Aufrufe hängen `?limit=2` an, der
 *  Vertrag kennt aber nur den nackten Pfad. */
type OhneQuery<S extends string> = S extends `${infer P}?${string}` ? P : S;

/** Erlaubt den Aufruf nur, wenn der (query-freie) Pfad im Vertrag steht. */
type Erlaubt<S extends string, M extends Methode> =
  OhneQuery<S> extends Pfad<M> ? S : never;

/**
 * Wie `api`, nur dass der Antworttyp aus dem Vertrag kommt statt aus dem
 * Kopf der Person, die den Aufruf schreibt. Ein Query-String darf dranhängen.
 *
 * Funktioniert für Pfade ohne PARAMETER — nur die sind als Literal typisierbar.
 * Für `/council/decision/${id}` bleibt `api.get<ApiAntwort<…>>(…)` der Weg;
 * der Typ stammt auch dann aus dem Vertrag, nur die Zuordnung ist von Hand.
 */
export const vertrag = {
  get: <S extends string>(pfad: Erlaubt<S, "get">) =>
    api.get<ApiAntwort<OhneQuery<S>, "get">>(pfad),
  post: <S extends string>(pfad: Erlaubt<S, "post">, body?: unknown) =>
    api.post<ApiAntwort<OhneQuery<S>, "post">>(pfad, body),
  put: <S extends string>(pfad: Erlaubt<S, "put">, body?: unknown) =>
    api.put<ApiAntwort<OhneQuery<S>, "put">>(pfad, body),
  del: <S extends string>(pfad: Erlaubt<S, "delete">, body?: unknown) =>
    api.del<ApiAntwort<OhneQuery<S>, "delete">>(pfad, body),
};
