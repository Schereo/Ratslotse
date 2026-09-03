import type { ApiAntwort } from "@/lib/vertrag";

export type ProblemList = ApiAntwort<"/probleme">;
export type PublicProblem = ProblemList["problems"][number];
export type ProblemFrequency = PublicProblem["frequency"];
export type ProblemStatus = PublicProblem["status"];

export const PROBLEM_ANGEBOT = {
  name: "Probleme in Oldenburg",
  navigation: "Probleme",
} as const;

export const PROBLEM_KATEGORIEN: Record<PublicProblem["category"], string> = {
  mobility: "Mobilität & Verkehr",
  public_space: "Öffentlicher Raum",
  education: "Schule & Bildung",
  childcare: "Kinderbetreuung",
  housing: "Wohnen",
  environment: "Umwelt & Grün",
  accessibility: "Barrierefreiheit",
  administration: "Verwaltung",
  other: "Sonstiges kommunales Thema",
};

export const PROBLEM_STATUS: Record<ProblemStatus, string> = {
  new: "Neu",
  multiple_reports: "Mehrfach gemeldet",
  verified: "Geprüft",
  persists: "Weiterhin vorhanden",
  apparently_resolved: "Offenbar behoben",
};

export const PROBLEM_SCOPE: Record<PublicProblem["scope_kind"], string> = {
  point: "Punkt",
  facility: "Einrichtung",
  route: "Route",
  area: "Gebiet",
  citywide: "Stadtweit",
};

export const MELDE_HAEUFIGKEIT: Record<ProblemFrequency, string> = {
  once: "einmal gemeldet",
  several: "mehrfach gemeldet",
  many: "häufig gemeldet",
  very_many: "sehr häufig gemeldet",
};

function isPosition(value: unknown): value is number[] {
  return (
    Array.isArray(value)
    && value.length >= 2
    && value.every((coordinate) => typeof coordinate === "number" && Number.isFinite(coordinate))
    && value[0] >= -180
    && value[0] <= 180
    && value[1] >= -90
    && value[1] <= 90
  );
}

function isRing(value: unknown): value is number[][] {
  return (
    Array.isArray(value)
    && value.length >= 4
    && value.every(isPosition)
    && value[0][0] === value.at(-1)![0]
    && value[0][1] === value.at(-1)![1]
  );
}

function isPolygon(value: unknown): value is number[][][] {
  return Array.isArray(value) && value.length > 0 && value.every(isRing);
}

/** Nur Probleme mit einem ehrlichen räumlichen Bezug gehören auf die Karte. */
export function isProblemMappable(problem: PublicProblem): boolean {
  if (problem.scope_kind === "point" || problem.scope_kind === "facility") {
    return (
      typeof problem.latitude === "number"
      && Number.isFinite(problem.latitude)
      && problem.latitude >= -90
      && problem.latitude <= 90
      && typeof problem.longitude === "number"
      && Number.isFinite(problem.longitude)
      && problem.longitude >= -180
      && problem.longitude <= 180
    );
  }
  const geometry = problem.geometry;
  if (problem.scope_kind === "route") {
    return (
      geometry?.type === "LineString"
      && Array.isArray(geometry.coordinates)
      && geometry.coordinates.length >= 2
      && geometry.coordinates.every(isPosition)
    );
  }
  if (problem.scope_kind !== "area") return false;
  if (geometry?.type === "Polygon") return isPolygon(geometry.coordinates);
  return (
    geometry?.type === "MultiPolygon"
    && Array.isArray(geometry.coordinates)
    && geometry.coordinates.length > 0
    && geometry.coordinates.every(isPolygon)
  );
}
