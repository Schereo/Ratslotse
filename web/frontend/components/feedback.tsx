"use client";

import { useState } from "react";
import { MessageSquarePlus } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Dialog, DialogContent, DialogHeader, DialogTitle, Select, Textarea, toast } from "@/components/ui";

const KINDS = [
  { value: "feature", label: "Feature-Vorschlag" },
  { value: "bug", label: "Fehler / Bug" },
  { value: "other", label: "Sonstiges" },
];

export function FeedbackButton({ onNavigate }: { onNavigate?: () => void }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("feature");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

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
    <>
      <button
        type="button"
        onClick={() => { setOpen(true); onNavigate?.(); }}
        className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <MessageSquarePlus className="h-4 w-4" /> Feedback
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
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
    </>
  );
}
