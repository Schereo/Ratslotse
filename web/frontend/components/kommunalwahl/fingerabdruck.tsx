// Themen-Fingerabdruck: Prägnanz (0–3) über die 12 Themenfelder als kleiner
// Equalizer — wo legt dieses Programm sein Gewicht? Misst Aufmerksamkeit,
// nie Richtung: Bauplan E7 (keine Ampel-Summen) bleibt unberührt.
// Serverseitig, kein Client-JS.

type Feld = { key: string; kurz: string; praegnanz: number };

function abk(kurz: string): string {
  return kurz.length > 7 ? `${kurz.slice(0, 6)}.` : kurz;
}

export function Fingerabdruck({ felder, mini = false }: { felder: Feld[]; mini?: boolean }) {
  const label = `Themen-Fingerabdruck: ${felder
    .map((f) => `${f.kurz} ${f.praegnanz} von 3`)
    .join(", ")}`;
  return (
    <div
      role="img"
      aria-label={label}
      className={mini ? "flex items-end gap-[5px]" : "flex flex-wrap items-end gap-x-2.5 gap-y-2 sm:gap-x-3"}
    >
      {felder.map((f) => (
        <div
          key={f.key}
          title={`${f.kurz}: Prägnanz ${f.praegnanz} von 3`}
          className="flex flex-col items-center gap-1"
        >
          <div className="flex flex-col-reverse gap-[2px]">
            {[1, 2, 3].map((i) => (
              <span
                key={i}
                className={`rounded-[2px] ${i <= f.praegnanz ? "bg-primary" : "bg-foreground/10"}`}
                style={mini ? { width: 7, height: 4 } : { width: 13, height: 6 }}
              />
            ))}
          </div>
          {!mini && (
            <span className="text-[8.5px] font-medium leading-none text-muted-foreground">{abk(f.kurz)}</span>
          )}
        </div>
      ))}
    </div>
  );
}
