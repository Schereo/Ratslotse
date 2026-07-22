import { cn } from "@/lib/utils";
import { shortCommittee } from "@/lib/committees";

/** Gremienname für Karten & Zeilen (Design 19a): Kurzname als Titel, der volle
 *  amtliche Name als 2-zeilige Unterzeile darunter — nur wenn er abweicht.
 *  Der volle Name steht immer im `title` (Tooltip + Screenreader). Für enge
 *  Slots (Chips, Dropdown-Trigger) stattdessen direkt `shortCommittee()` nutzen. */
export function CommitteeName({
  name,
  className,
  subClassName,
}: {
  name: string;
  className?: string;
  subClassName?: string;
}) {
  const short = shortCommittee(name);
  const differs = short !== name.trim();
  return (
    <span className="block min-w-0" title={name}>
      <span className={cn("block truncate", className)}>{short}</span>
      {differs && (
        <span className={cn("mt-0.5 block text-[11px] leading-snug text-muted-foreground line-clamp-2", subClassName)}>
          {name}
        </span>
      )}
    </span>
  );
}
