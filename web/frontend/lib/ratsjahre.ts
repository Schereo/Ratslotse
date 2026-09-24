/**
 * Wahlperioden im Rat als Jahresspannen — „seit 2001", „2011–2016, seit 2021".
 *
 * Eine Wahlperiode dauert fünf Jahre und heißt nach ihrem Anfangsjahr (2016
 * für 2016–2021). Aufeinanderfolgende Perioden werden zu einer Spanne; die
 * zuletzt abgelaufene (`letzte`) läuft bis heute und heißt deshalb „seit".
 */
export function ratsjahre(terms: readonly number[], letzte: number): string {
  const sortiert = [...new Set(terms)].sort((a, b) => a - b);
  const spannen: [number, number][] = [];
  for (const t of sortiert) {
    const vorige = spannen[spannen.length - 1];
    if (vorige && vorige[1] === t) vorige[1] = t + 5;
    else spannen.push([t, t + 5]);
  }
  return spannen
    .map(([von, bis]) => (bis > letzte ? `seit ${von}` : `${von}–${bis}`))
    .join(", ");
}
