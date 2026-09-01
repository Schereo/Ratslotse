"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button, Input, Label, Select, Textarea } from "@/components/ui";

const KINDS = [
  { value: "konto", label: "Konto & Anmeldung" },
  { value: "bug", label: "Etwas funktioniert nicht" },
  { value: "feature", label: "Vorschlag" },
  { value: "other", label: "Sonstiges" },
];

/** Kontaktformular der Hilfe-Seite. Bewusst ohne Anmeldung — der
 *  Feedback-Dialog in der App hängt am Konto und hilft dem nicht, der
 *  gerade nicht reinkommt (und genau das verlangt Apples Richtlinie 1.5
 *  für die Support-URL).
 *
 *  Kein `toast` als einzige Rückmeldung: Wer ein Formular abschickt, will
 *  danach etwas Bleibendes sehen, keine Blase, die nach vier Sekunden weg
 *  ist — erst recht, wenn die Antwort auf sich warten lässt. */
export function SupportForm() {
  const [kind, setKind] = useState("konto");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  // Honigtopf-Zwilling zum Server-Feld: Menschen sehen ihn nie.
  const [website, setWebsite] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);
    setError(null);
    try {
      await api.post("/feedback/contact", { kind, email, message, website });
      setSent(true);
    } catch (err) {
      // 429 ist kein Fehler des Absenders — der Ton bleibt entsprechend ruhig.
      setError(
        err instanceof ApiError && err.status === 429
          ? "Gerade sind zu viele Anfragen angekommen. Bitte versuche es in einer Viertelstunde noch einmal."
          : "Die Nachricht ließ sich nicht abschicken. Schreib mir bitte direkt an ratslotse@timsigl.de.",
      );
    } finally {
      setSending(false);
    }
  }

  if (sent) {
    return (
      <div className="rounded-xl border border-primary/20 bg-primary/[0.04] p-5">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="space-y-1.5">
            <p className="font-semibold text-foreground">Nachricht ist da.</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Ich antworte an <span className="font-medium text-foreground">{email}</span>, in der Regel
              innerhalb von zwei Werktagen. Ratslotse betreibe ich alleine und nebenbei — an einem
              Wochenende kann es also etwas länger dauern.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <Label htmlFor="support-kind">Worum geht es?</Label>
        <Select id="support-kind" className="mt-1" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>{k.label}</option>
          ))}
        </Select>
      </div>

      <div>
        <Label htmlFor="support-email">Deine E-Mail-Adresse</Label>
        <Input
          id="support-email"
          type="email"
          className="mt-1"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          placeholder="damit ich antworten kann"
        />
      </div>

      <div>
        <Label htmlFor="support-message">Deine Nachricht</Label>
        <Textarea
          id="support-message"
          className="mt-1 min-h-[140px]"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          required
          minLength={3}
          maxLength={4000}
          placeholder="Was ist passiert? Wenn es um einen Fehler geht: Auf welchem Gerät, und was hast du davor gemacht?"
        />
      </div>

      {/* Honigtopf. Nicht `display:none` — manche Bots überspringen unsichtbare
          Felder gezielt; off-screen wirkt zuverlässiger. aria-hidden + tabIndex
          halten Screenreader und Tastatur draußen. */}
      <div className="absolute left-[-9999px] top-auto h-px w-px overflow-hidden" aria-hidden="true">
        <label htmlFor="support-website">Website (bitte frei lassen)</label>
        <input
          id="support-website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Button type="submit" disabled={sending || !email || message.trim().length < 3} className="h-11 w-full sm:w-auto">
        {sending ? "Wird gesendet…" : "Nachricht senden"}
      </Button>

      <p className="text-xs leading-relaxed text-muted-foreground">
        Deine Adresse und deine Nachricht landen per E-Mail bei mir und werden nur zur Beantwortung
        genutzt — nicht für Newsletter, nicht für Werbung. Mehr dazu in der{" "}
        <a href="/datenschutz" className="text-primary hover:underline">Datenschutzerklärung</a>.
      </p>
    </form>
  );
}
