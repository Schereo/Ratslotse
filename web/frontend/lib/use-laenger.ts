import { useEffect, useState } from "react";

/** Wird wahr, wenn `aktiv` länger als `ms` am Stück wahr ist.
 *
 *  Für Wartezustände, die etwas sagen sollen, sobald es ungewöhnlich lange
 *  dauert („dauert länger als üblich — du kannst abbrechen"). Ohne das stand
 *  bei einem hängenden Modell dieselbe Zeile minutenlang da, und man konnte
 *  nicht unterscheiden, ob noch etwas passiert. */
export function useLaengerAls(aktiv: boolean, ms: number): boolean {
  const [laenger, setLaenger] = useState(false);
  useEffect(() => {
    setLaenger(false);
    if (!aktiv) return;
    const t = setTimeout(() => setLaenger(true), ms);
    return () => clearTimeout(t);
  }, [aktiv, ms]);
  return laenger;
}
