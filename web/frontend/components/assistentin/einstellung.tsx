"use client";

import { useEffect, useState } from "react";
import { MessageCircleQuestion } from "lucide-react";

import { Card, Switch } from "@/components/ui";
import { useFeature } from "@/lib/features";
import {
  knopfVersteckt, LOTTI_SICHT_EVENT, setzeKnopfVersteckt,
} from "@/lib/lotti-sichtbar";

/**
 * Konto-Karte „Lotti": der Knopf lässt sich ausblenden — auf diesem Gerät.
 *
 * **Warum das eine Karte wert ist.** Ein Element, das dauerhaft über dem
 * Inhalt schwebt, braucht einen sichtbaren Weg, es loszuwerden; sonst ist es
 * kein Angebot, sondern ein Möbelstück. Und weil der Weg zurück derselbe
 * bleiben muss, nennt die Karte ihn ausdrücklich: ⌘K.
 */
export function LottiCard() {
  const an = useFeature("lotti-assistentin");
  const [aus, setAus] = useState(false);
  const [bereit, setBereit] = useState(false);

  useEffect(() => {
    const sync = () => setAus(knopfVersteckt());
    sync();
    setBereit(true);
    window.addEventListener(LOTTI_SICHT_EVENT, sync);
    return () => window.removeEventListener(LOTTI_SICHT_EVENT, sync);
  }, []);

  if (!an) return null;

  return (
    <Card className="p-6">
      <h2 className="flex items-center gap-2 font-semibold text-foreground">
        <MessageCircleQuestion className="h-4 w-4 text-primary" aria-hidden />
        Lotti
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Lotti sitzt als Knopf unten rechts und erklärt, was gerade auf der
        Seite steht.
      </p>

      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-foreground">Knopf ausblenden</span>
        {bereit && (
          <Switch
            checked={aus}
            onCheckedChange={(v) => { setAus(v); setzeKnopfVersteckt(v); }}
            aria-label="Lotti-Knopf ausblenden"
          />
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground/80">
        Gilt nur auf diesem Gerät. Fragen kannst du sie trotzdem: ⌘K öffnen und
        „Lotti fragen" wählen.
      </p>
    </Card>
  );
}
