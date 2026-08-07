// Themen-Fingerabdruck: Forderungen je Themenfeld als Skyline — Säulenhöhe
// relativ zum stärksten Feld der Liste. So bekommt jedes Programm eine
// unterscheidbare Silhouette (die Prägnanz-Punkte davor waren bei großen
// Programmen überall voll und sagten nichts). Misst Aufmerksamkeit, nie
// Richtung: Bauplan E7 (keine Ampel-Summen) bleibt unberührt.
// Serverseitig, kein Client-JS.

type Feld = { key: string; kurz: string; anzahl: number; anteil: number };

function abk(kurz: string): string {
  return kurz.length > 7 ? `${kurz.slice(0, 6)}.` : kurz;
}

export function Fingerabdruck({ felder, mini = false }: { felder: Feld[]; mini?: boolean }) {
  const label = `Forderungen je Themenfeld: ${felder
    .map((f) => `${f.kurz} ${f.anzahl}`)
    .join(", ")}`;
  const hoehe = mini ? 22 : 38;

  return (
    <div role="img" aria-label={label} className={mini ? undefined : "inline-block"}>
      <div className={`flex items-end ${mini ? "gap-[4px]" : "gap-[6px]"}`} style={{ height: hoehe }}>
        {felder.map((f) => (
          <div
            key={f.key}
            title={`${f.kurz}: ${f.anzahl} Forderung${f.anzahl === 1 ? "" : "en"}`}
            className="flex flex-col items-center justify-end self-stretch"
          >
            <span
              className={`rounded-t-[2px] ${f.anzahl === 0 ? "bg-foreground/15" : "bg-primary"}`}
              style={{
                width: mini ? 9 : 15,
                height: f.anzahl === 0 ? 2 : Math.max(3, Math.round(f.anteil * hoehe)),
              }}
            />
          </div>
        ))}
      </div>
      {mini ? (
        <p className="mt-1 text-[9.5px] leading-none text-muted-foreground">Forderungen je Themenfeld</p>
      ) : (
        <div className="mt-1 flex gap-[6px]">
          {felder.map((f) => (
            <span
              key={f.key}
              title={`${f.kurz}: ${f.anzahl} Forderung${f.anzahl === 1 ? "" : "en"}`}
              className="w-[15px] overflow-visible text-center text-[8px] font-medium leading-tight text-muted-foreground [writing-mode:vertical-rl]"
              style={{ height: 52 }}
            >
              {abk(f.kurz)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
