"use client";

import { useEffect, useState } from "react";
import { MessageSquarePlus } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Dialog, DialogContent, DialogHeader, DialogTitle, Select, Textarea, toast } from "@/components/ui";

const KINDS = [
  { value: "feature", label: "Feature-Vorschlag" },
  { value: "bug", label: "Fehler / Bug" },
  { value: "other", label: "Sonstiges" },
];

// Der Dialog-State lebt in <FeedbackDialog /> (einmal global im Layout), nicht
// im Button: der Button steckt auf Mobile IM Menü-Sheet, das beim Klick zugeht —
// läge der Dialog im Button, risse der Sheet-Unmount ihn sofort wieder mit.
// Gleiches Muster wie openCommandPalette().
const OPEN_EVENT = "ratslotse:open-feedback";

export function openFeedback() {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

/** Reiner Auslöser — schließt zuerst das Menü (onNavigate), dann öffnet der
 *  globale Dialog. */
export function FeedbackButton({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <button
      type="button"
      onClick={() => { onNavigate?.(); openFeedback(); }}
      className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
    >
      <MessageSquarePlus className="h-4 w-4" /> Feedback
    </button>
  );
}

/** Der eigentliche Feedback-Dialog. Einmal im App-Layout gerendert, öffnet auf
 *  das openFeedback()-Event — unabhängig davon, welcher Button ihn ausgelöst hat. */
export function FeedbackDialog() {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("feature");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOpen);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim().length < 3) return;
    setSending(true);
    try {
      await api.post("/feedback", { kind, message: message.trim() });
      toast.success("Danke für dein Feedback!");
      setOpen(false);
      setMessage("");
      setKind("feature");
    } catch {
      toast.error("Konnte nicht gesendet werden — bitte später nochmal.");
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        // Radix fokussiert beim Öffnen das erste fokussierbare Element — hier
        // die Art-Auswahl. Auf iOS reißt ein fokussiertes <select> sofort das
        // Rad-Menü auf, noch bevor man den Dialog gelesen hat. Stattdessen den
        // Dialog selbst fokussieren: Screenreader sagen ihn weiterhin an und
        // die Fokusfalle greift, aber es klappt nichts von allein auf.
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          (event.currentTarget as HTMLElement | null)?.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle>Feedback geben</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Art</label>
            <Select value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Dein Feedback</label>
            <Textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={5}
              required
              placeholder="Was fehlt, was nervt, was wäre cool? Feature-Wünsche oder Fehler — alles willkommen."
            />
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Abbrechen</Button>
            <Button type="submit" disabled={sending || message.trim().length < 3}>
              {sending ? "Senden…" : "Senden"}
            </Button>
          </div>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">
          Geht direkt per E-Mail an uns; Antwort ggf. an deine Konto-Adresse.
        </p>
      </DialogContent>
    </Dialog>
  );
}
