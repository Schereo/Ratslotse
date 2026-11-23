"use client";

/* The bridge between a note and „Frag den Rat" on the same page (Tims Wunsch
   23.11.2026: Verweise auf Unterlagen in der Notiz, über die man mit dem Chat
   sprechen kann).

   Note and chat live in different columns and know nothing of each other.
   The chat registers here when it can answer; a reference chip in the note
   then offers „Im Chat fragen" and hands over the reference — document id
   and page, never the note's text: that goes to no model. Without a chat on
   the page (or without an account) there is no handler, and the chip offers
   only to open the document. */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { DocRefAttrs } from "@/lib/doc-ref";

type Ask = (ref: DocRefAttrs) => void;

interface Bridge {
  /** `null`: no chat on this page can take a reference. */
  ask: Ask | null;
  register: (fn: Ask) => () => void;
}

const Ctx = createContext<Bridge | null>(null);

export function ChatBridgeProvider({ children }: { children: React.ReactNode }) {
  const [ask, setAsk] = useState<Ask | null>(null);
  const register = useCallback((fn: Ask) => {
    setAsk(() => fn);
    return () => setAsk((cur: Ask | null) => (cur === fn ? null : cur));
  }, []);
  const value = useMemo(() => ({ ask, register }), [ask, register]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useChatBridge(): Bridge | null {
  return useContext(Ctx);
}
