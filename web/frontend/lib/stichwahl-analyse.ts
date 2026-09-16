import type { ApiAntwort } from "./vertrag";

export type StichwahlAnalyse = ApiAntwort<"/wahlabend/stichwahl/potenzial">;
export type Bezugsbasis = "alle" | "finalisten";

/** Beide Nenner sind Stimmen derselben Wahlart, keine Wahlberechtigten. */
export function stimmenanteil(stimmen: number, alle: number, finalisten: number, basis: Bezugsbasis): number | null {
  const nenner = basis === "alle" ? alle : finalisten;
  return nenner > 0 ? (100 * stimmen) / nenner : null;
}

export function analysePfad(token: string): string {
  return `/wahlabend/stichwahl/potenzial?${new URLSearchParams({ token })}`;
}
