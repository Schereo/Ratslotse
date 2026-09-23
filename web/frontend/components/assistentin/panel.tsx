"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ExternalLink, RotateCcw, Sparkles, X } from "lucide-react";

import { Mascot } from "@/components/mascot";
import { AntwortText } from "@/components/qa-bausteine";
import { GlossarAufklappBereich } from "@/components/glossary-text";
import { FeedbackDaumen } from "@/components/feedback-daumen";
import { api, apiUrl, authHeaders, qs } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import {
  ankerKennung, ankerListe, ankerTreffer, anschlussfragen, belegName,
  chipTitel, daumenZeigen, erklaerAktion,
  ernteElement, gedaechtnis, kuerze, ortsfrage, refsAus, routeAus, seitenName,
  seitenTitel, seitenUeberschrift, trenneWeiter, ueberschriftenPfad, zaesur,
  type Anker, type Bildschirm, type NaechsteSeite,
} from "@/lib/assistentin";
import { useAuth } from "@/lib/auth";
import { GespraecheEinwilligung } from "@/components/gespraeche-einwilligung";
import { decisionHref, fragenHref } from "@/lib/routes";
import type { ElementFrage } from "./index";
import type { MarkierFrage } from "./markier-knopf";
import { auswahlText, frageMitZitat } from "@/lib/markieren";
import { leseSseStrom } from "@/lib/sse";
import { lottiSchrittText } from "@/lib/qa-schritte";
import { tastaturHoehe } from "@/lib/tastatur";
import { cn } from "@/lib/utils";

/**
 * Lottis Chat-Fenster — das Gegenstück zum schwebenden Knopf.
 *
 * **Kein Sheet und kein Dialog.** Am Schreibtisch ist es ein Fenster über dem
 * Knopf, 384 px breit und **nicht modal**: Die Seite bleibt bedienbar, man
 * kann weiterlesen und weiterscrollen, während Lotti antwortet. Ein Dialog mit
 * Abdunkler wäre das Gegenteil dessen, wofür die Assistentin da ist — sie
 * erklärt, was auf der Seite steht, also darf sie die Seite nicht verdecken.
 * Auf dem Handy füllt es die Fläche zwischen Kopfleiste und Knopf; dort ist
 * ein halbes Fenster keins.
 *
 * **Der Verlauf überlebt den Seitenwechsel.** Das Fenster lebt in der
 * App-Hülle, nicht in einer Seite. Wer navigiert, behält seine Runden — nur
 * die Kontext-Pille wechselt. Innerhalb des Tabs übersteht der Verlauf auch
 * ein Neuladen (`sessionStorage`); über den Tab hinaus nicht: Gespeichert
 * wird erst mit Einwilligung, und die ist ein eigener Schritt.
 */

const SPEICHER = "ratslotse:lotti-verlauf";
/** Die Kennung des laufenden Gesprächs. Ohne sie riss nach einem Neuladen
 *  des Tabs der Faden: Der Verlauf stand noch da, die nächste Frage eröffnete
 *  serverseitig aber ein zweites Gespräch zu derselben Sache. */
const SPEICHER_ID = "ratslotse:lotti-gespraech";
const MAX_TURNS_SPEICHER = 10;
const MAX_TURNS_KONTEXT = 3;

/** Eine Quelle unter einer Ratsantwort — nur, was die schlanke Liste braucht. */
export type LottiQuelle = {
  id: number;
  title: string | null;
  committee?: string | null;
  session_date?: string | null;
};

/** Ein Papier, das Lotti beim Antworten vorlag — aus dem `done`-Rahmen
 *  (`evidence`) und aus dem gespeicherten Gespräch.
 *
 *  **Belege des KONTEXTS, nicht der einzelnen Zahl.** Welchen Satz das Modell
 *  auf welche Zeile stützt, weiß niemand; was im Prompt stand, schon. Die
 *  Zeile heißt deshalb „Grundlage:" und nicht „Quelle dieser Zahl". */
export type LottiBeleg = {
  label: string;
  year?: number | null;
  url?: string | null;
};

export type LottiTurn = {
  key: number;
  question: string;
  answer: string;
  /** Kam die Antwort aus dem Archiv? Dann trägt sie Belege. */
  ratsfrage?: boolean;
  quellen?: LottiQuelle[];
  /** Die Papiere hinter den Haushaltszahlen im Prompt (höchstens fünf). */
  evidence?: LottiBeleg[];
  cited?: number[];
  next: "ratsfrage" | null;
  /** Die Haushalts-Seite, auf der die Sache ausführlich steht — aus dem
   *  `done`-Rahmen (`next_page`). Sie trägt den Chip „Weiter zu: …"; das
   *  Fenster bleibt dabei offen, der Verlauf überlebt den Seitenwechsel und
   *  bekommt die Zäsur „Jetzt auf: …". */
  nextPage?: NaechsteSeite | null;
  /** Kam die Antwort ohne Modell? Nur fürs Protokoll, nicht sichtbar. */
  mode: string | null;
  fehler?: boolean;
  /** Was auf dem Bildschirm stand, als die Frage gestellt wurde. */
  kontext: string;
  /** Auf welcher Seite gefragt wurde — die normalisierte Route. Sie trägt die
   *  Zäsur im Verlauf UND die Auswahl des Gedächtnisses (`gedaechtnis`).
   *  Runden aus einem älteren Tab-Speicher haben sie nicht; sie gelten dann
   *  als fremd. Eine Migration braucht das nicht: Der Verlauf lebt einen Tab
   *  lang, und die schlimmste Folge ist eine Zäsur zu viel. */
  route?: string;
  /** Wie die Seite damals hieß — für die Zäsur. */
  seite?: string;
  /** Die Bausteine, zu denen diese Runde hinführt („Zeig mir: …"). Gesetzt
   *  nur in der Lotsen-Runde (`mode === "local"`). */
  zeigen?: Anker[];
  /** Die Markierung, zu der diese Runde gefragt wurde („Lotti fragen" an der
   *  Auswahl). Sie steht als Zitat vor der Frage — im Verlauf wie im
   *  Gedächtnis (`frageMitZitat`), denn „Was bedeutet das?" allein hätte
   *  in der nächsten Runde kein „das" mehr. */
  zitat?: string;
  /** Der Baustein, den diese Runde ERKLÄRT — aus einem „… erklären"-Chip. Er ist das Gedächtnis der Anschlussfragen:
   *  Was einmal erklärt wurde, wird nicht noch einmal vorgeschlagen. Der
   *  Schlüssel allein reichte dafür nicht (zwei Bausteine dürfen sich einen
   *  teilen), deshalb steht hier der ganze Anker. */
  baustein?: Anker;
  /** Woran der Strom gerade arbeitet — aus dem SSE-Rahmen `step`. Steht nur
   *  neben der Tipp-Anzeige, also solange noch kein Wort da ist; danach ist
   *  der Text selbst die Auskunft. */
  schritt?: string | null;
  /** Diese Runde ist der ZWEITE Schritt derselben Frage (Erklärung, dann
   *  Archiv): Die Frage-Blase steht schon darüber. Die Frage selbst bleibt
   *  gesetzt — der Daumen und das gespeicherte Gespräch brauchen sie. */
  frageVerborgen?: boolean;
};

/** Der Breakpoint `desk` aus `tailwind.config.ts`, als Medienabfrage.
 *
 *  **Warum der Client ihn kennen muss.** Am Schreibtisch steht das Fenster
 *  NEBEN der Seite — nach einem „Zeig mir" bleibt es offen, man sieht beides.
 *  Auf dem Handy füllt es die Fläche zwischen Kopfleiste und Knopf und deckt
 *  damit genau das ab, wohin gescrollt wird; dort schließt es sich. Die
 *  Zeichenkette ist dieselbe wie in
 *  `tailwind.config.ts` — laufen die beiden auseinander, schließt sich das
 *  Fenster genau auf den Breiten falsch, auf denen niemand nachsieht. */
const DESK = "(pointer: fine) and (min-width: 1024px)";

/** Wie lange der Ring am gezeigten Baustein stehen bleibt — **ab dem
 *  Ankommen**, nicht ab dem Klick. Zwei Sekunden: lang genug, um ihn nach dem
 *  Scrollen zu finden, kurz genug, um nicht als dauerhafte Auswahl gelesen zu
 *  werden (Designsprache, „Bewegungs-Grammatik": Hinweise verblassen, sie
 *  bleiben nicht stehen). */
const ZEIG_MS = 2000;

/** Bis hierhin wird auf `scrollend` gewartet, dann läuft die Zeit trotzdem.
 *
 *  **Warum überhaupt gewartet wird:** Ein sanfter Sprung über eine
 *  Haushaltsseite dauert. Gemessen am 22.09.2026 auf `/haushalt/schulden`:
 *  2.500 px brauchten rund 1,3 s — von zwei Sekunden Ring wäre eine halbe
 *  übrig gewesen, und zwar genau beim weitesten Sprung, bei dem man den
 *  Hinweis am nötigsten hat. Der Notausgang ist dieser Deckel: `scrollend`
 *  kennt nicht jeder Browser, und wo gar nicht gescrollt wird (der Baustein
 *  steht schon im Bild), kommt es nie. */
const SCROLL_MAX_MS = 1500;

/**
 * Zum Baustein scrollen und ihn kurz hervorheben.
 *
 * **Nur über den Anker-Schlüssel**, nie über eine freie DOM-Suche: Der Chip
 * verspricht genau den Baustein, den Lotti genannt hat. Ist er inzwischen
 * weg (eine Seite lädt nach, ein Reiter wurde gewechselt), passiert nichts —
 * eine Fehlermeldung über einen verschwundenen Kasten hülfe niemandem.
 */
function ankerKnoten(anker: Anker): HTMLElement | undefined {
  // Schlüssel UND Titel, nicht nur der Schlüssel: Auf `/haushalt/schulden`
  // tragen zwei Zeitreihen denselben (`…zeitreihe`). Ein Selektor auf den
  // Schlüssel allein sprang immer die erste an — also im halben Fall auf den
  // falschen Kasten (gemessen im Browser am 22.09.2026).
  return [...document.querySelectorAll<HTMLElement>(
    `[data-erklaer="${CSS.escape(anker.key)}"]`)]
    .find((k) => k.getAttribute("data-erklaer-titel") === anker.titel);
}

function zeigeBaustein(anker: Anker): void {
  const el = ankerKnoten(anker);
  if (!el) return;
  // Sanft nur, wer das will: Ein geschmeidiger Sprung über eine halbe
  // Haushaltsseite ist genau die Bewegung, die `prefers-reduced-motion`
  // meint. Der Ring selbst steht in beiden Fällen (globals.css).
  const ruhig = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ block: "center", behavior: ruhig ? "auto" : "smooth" });
  el.classList.add("lotti-zeigt");
  let gestartet = false;
  const abnehmen = () => {
    if (gestartet) return;
    gestartet = true;
    window.setTimeout(() => el.classList.remove("lotti-zeigt"), ZEIG_MS);
  };
  window.addEventListener("scrollend", abnehmen, { once: true });
  window.setTimeout(abnehmen, SCROLL_MAX_MS);
}

/** **`glossary` ist hier bewusst weg** (B7 der zweiten Durchsicht): Der
 *  `done`-Rahmen schickt die Fachwörter weiterhin, das Fenster speicherte sie
 *  je Runde und zeigte sie nirgends. Leisten tun das die Unterstreichungen in
 *  `AntwortText` — sie stehen im Antworttext selbst, also an der Stelle, an
 *  der man das Wort liest. Ein zweiter Ort für dieselben Wörter wäre
 *  Doppelung; der Rahmen bleibt, falls jemand sie später als Chips will. */

function leseVerlauf(): LottiTurn[] {
  try {
    const roh = sessionStorage.getItem(SPEICHER);
    if (!roh) return [];
    const p = JSON.parse(roh);
    return Array.isArray(p) ? (p as LottiTurn[]).slice(-MAX_TURNS_SPEICHER) : [];
  } catch {
    return [];
  }
}

function merkeVerlauf(turns: LottiTurn[]): void {
  try {
    sessionStorage.setItem(SPEICHER, JSON.stringify(turns.slice(-MAX_TURNS_SPEICHER)));
  } catch { /* privates Fenster, gesperrter Speicher — dann eben nicht */ }
}

export function LottiPanel({
  offen, onSchliessen, markierung, markiert, onMarkiertVerbraucht,
  ladeGespraech, onGespraechGeladen,
}: {
  offen: boolean;
  onSchliessen: () => void;
  /** Der gerade markierte Text der Seite — er wandert in die Kontext-Pille. */
  markierung: string;
  /** Eine Markierung, an der „Lotti fragen" gedrückt wurde. Gesetzt heißt:
   *  sofort fragen. */
  markiert: MarkierFrage | null;
  onMarkiertVerbraucht: () => void;
  /** Ein gespeichertes Lotti-Gespräch, das geladen werden soll. */
  ladeGespraech?: number | null;
  onGespraechGeladen?: () => void;
}) {
  const pathname = usePathname();
  const sp = useSearchParams();
  const router = useRouter();
  const [turns, setTurns] = useState<LottiTurn[]>([]);
  // Dieselbe Einwilligung wie „Frag den Rat" — ein Schalter am Konto, eine
  // Tabelle. `null` heißt „noch nie gefragt" und ist der einzige Zustand, in
  // dem die Karte erscheint; eine getroffene Wahl gilt auf beiden Flächen.
  const { user, refresh } = useAuth();
  const [merken, setMerken] = useState<number | null | undefined>(
    () => (user ? user.saves_conversations ?? null : undefined));
  // **Und sie folgt ihm weiter.** Der Anfangswert allein reichte nicht: Wer
  // die Frage auf `/fragen` beantwortet und danach Lotti öffnet, sah die
  // Karte ein zweites Mal und konnte bis zur zweiten Antwort nicht fragen.
  // Eine hier getroffene Wahl gilt trotzdem sofort, auch bevor `user` neu
  // geladen ist — deshalb nur nachziehen, was wirklich neu ist.
  const kontoWahl = user ? user.saves_conversations ?? null : undefined;
  // Der Anzeigename geht NIE mit — er wird aus der Überschrift gestrichen.
  const anzeigename = user?.display_name ?? null;
  useEffect(() => { setMerken(kontoWahl); }, [kontoWahl]);
  const [gespraechId, _setGespraechId] = useState<number | null>(null);
  const setGespraechId = useCallback((id: number | null) => {
    _setGespraechId(id);
    try {
      if (id) sessionStorage.setItem(SPEICHER_ID, String(id));
      else sessionStorage.removeItem(SPEICHER_ID);
    } catch { /* privates Fenster — dann eben nicht */ }
  }, []);
  const [frage, setFrage] = useState("");
  const [laden, setLaden] = useState(false);
  const abbruch = useRef<AbortController | null>(null);
  const eingabeRef = useRef<HTMLInputElement>(null);
  const endeRef = useRef<HTMLDivElement>(null);
  const fensterRef = useRef<HTMLDivElement>(null);
  const tastatur = useTastatur();
  const naechsterKey = useRef(1);
  /** Der zuletzt angetippte Baustein — die Ratsfrage schickt ihn mit, damit
   *  „und wer hat das beantragt?" ein „das" hat. */
  const letzterBaustein = useRef<ElementFrage | null>(null);

  const route = routeAus(pathname, sp.toString());
  // Die Route MUSS mit: `?id=` ist auf der Ort-Seite ein Kürzel, sonst eine
  // Nummer (lib/assistentin.ts).
  const refs = useMemo(() => refsAus(sp.toString(), route), [sp, route]);

  /** Die zwei Startfragen dieser Route (PR 25) — React Query statt eines
   *  eigenen Caches: derselbe Baustein wie `ThemenBruecke` in
   *  `council-qa.tsx`, und die Fragen ändern sich nur mit einem Deploy, nie
   *  während einer Sitzung — `staleTime` darf deshalb großzügig sein. Geholt
   *  wird nur, solange das Fenster offen UND leer ist: Nach der ersten Runde
   *  braucht niemand sie mehr, und geschlossen sieht sie ohnehin niemand.
   *  Kein Modellaufruf auf dem Server, kostet also nichts außer der Anfrage
   *  selbst. */
  const startfragenAntwort = useQuery({
    queryKey: ["lotti-starters", route],
    queryFn: () => api.get<ApiAntwort<"/council/assistant/starters">>(
      `/council/assistant/starters${qs({ route })}`),
    enabled: offen && turns.length === 0,
    staleTime: 60 * 60_000,
  });
  const startfragen = startfragenAntwort.data?.starters ?? [];

  // Der Verlauf des Tabs — einmal beim Aufbauen, danach bei jeder Änderung.
  useEffect(() => {
    const alt = leseVerlauf();
    if (alt.length) {
      setTurns(alt);
      naechsterKey.current = Math.max(...alt.map((t) => t.key)) + 1;
    }
    try {
      const id = Number(sessionStorage.getItem(SPEICHER_ID));
      if (id > 0) _setGespraechId(id);
    } catch { /* egal */ }
  }, []);
  useEffect(() => { if (turns.length) merkeVerlauf(turns); }, [turns]);

  // Beim Öffnen: Fokus ins Eingabefeld. Beim Schließen: zurück auf den Knopf —
  // sonst steht der Fokus im Nichts, und die nächste Tabulatortaste beginnt
  // wieder ganz oben auf der Seite (BITV).
  useEffect(() => {
    if (offen) {
      const id = window.setTimeout(() => eingabeRef.current?.focus(), 60);
      return () => window.clearTimeout(id);
    }
    document.querySelector<HTMLElement>("[data-lotti-knopf]")?.focus();
  }, [offen]);

  // Esc schließt — auch wenn der Fokus gerade woanders auf der Seite steht.
  useEffect(() => {
    if (!offen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onSchliessen(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [offen, onSchliessen]);

  // Ein Seitenwechsel bricht eine laufende Antwort ab: Eine Erklärung zur
  // ALTEN Seite, die auf der neuen fertig geschrieben wird, ist schlimmer als
  // keine — sie sieht aus, als gehörte sie hierher.
  useEffect(() => {
    abbruch.current?.abort();
    abbruch.current = null;
    setLaden(false);
  }, [pathname]);

  useEffect(() => {
    if (offen) endeRef.current?.scrollIntoView({ block: "end" });
  }, [offen, turns.length]);

  /** Dieselbe Frage, aber ans Archiv — mit dem Bildschirm als Kontext.
   *
   *  **Warum nicht einfach nach `/fragen` schicken.** Das war PR 2, und es
   *  kostete den Zusammenhang: Wer auf der Schulden-Seite fragt „wer hat das
   *  beantragt?", landete auf einer leeren Fragen-Seite, und das „das" war
   *  weg. Jetzt reist der Bildschirm mit, und die Antwort erscheint dort, wo
   *  gefragt wurde. Der Weg ins volle Ratsgespräch bleibt darunter stehen.
   *
   *  **Seit 22.09.2026 ruft das meist niemand mehr von Hand auf.** Gehört die
   *  Frage ins Archiv, sagt das der Server (`mode: "handoff"`), und diese
   *  Funktion läuft von selbst — `inTurn` ist dann die Runde, die schon
   *  dasteht: Die Frage bleibt oben stehen, darunter kommt die Archivantwort.
   *  EINE Runde, ein Weg. Ohne `inTurn` entsteht eine neue Runde — so, wenn
   *  das Modell erst erklärt und dann `WEITER: ratsfrage` setzt (die
   *  Erklärung bleibt stehen), und so beim Textlink „Im Ratsarchiv
   *  nachsehen".
   */
  const ratsfrageStellen = useCallback(async (frageText: string, opts: {
    /** Die bestehende Runde, in die geantwortet wird (statt einer neuen). */
    inTurn?: number;
    /** Die Erklärung, die gerade darüber entstanden ist — sie gehört ins
     *  Gedächtnis der Ratsfrage („und wer hat das beantragt?"). Der Zustand
     *  `turns` trägt sie zu diesem Zeitpunkt noch nicht: React hat den
     *  Setzer erst eingereiht, und dieser `useCallback` hält den Stand vom
     *  letzten Zeichnen. Gesetzt heißt außerdem: Diese Runde ist der ZWEITE
     *  Schritt derselben Frage — die Frage-Blase steht schon darüber und
     *  wird nicht wiederholt. */
    dazu?: { question: string; answer: string };
    /** Die Markierung der Runde, aus der dieser Weg kommt. Der Zustand
     *  `markierung` taugt dafür nicht: Auf dem Handy ist die Auswahl nach dem
     *  Tipp auf „Lotti fragen" schon aufgehoben. */
    auswahl?: string;
  } = {}) => {
    abbruch.current?.abort();
    const ctrl = new AbortController();
    abbruch.current = ctrl;
    setLaden(true);
    const key = opts.inTurn ?? naechsterKey.current++;
    const rahmen = {
      question: frageText, answer: "", next: null, mode: null,
      kontext: "im Ratsarchiv gesucht", ratsfrage: true, quellen: [], cited: [],
      route, seite: seitenName(document, anzeigename),
      // Die Frage steht schon über der Erklärung — ein zweites Mal wäre sie
      // eine neue Runde, und es ist dieselbe.
      frageVerborgen: opts.dazu != null,
    } satisfies Partial<LottiTurn>;
    setTurns((ts) => (opts.inTurn != null
      // Die Runde steht schon da (die Frage, die Tipp-Anzeige) — sie wird
      // zur Archiv-Runde, statt eine zweite daneben zu stellen.
      ? ts.map((t) => (t.key === key ? { ...t, ...rahmen, schritt: t.schritt } : t))
      : [...ts, { key, ...rahmen }]));
    const patch = (fn: (t: LottiTurn) => Partial<LottiTurn>) =>
      setTurns((ts) => ts.map((t) => (t.key === key ? { ...t, ...fn(t) } : t)));
    try {
      const res = await fetch(apiUrl("/council/ask"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          question: frageText,
          // **Dasselbe Gespräch wie die Erklärungen.** Der Plan sagt, der
          // Ratsweg aus dem Fenster hängt seinen Turn dort an; ohne diese
          // beiden Felder blieb er ungespeichert, und der Verlauf hatte ein
          // Loch genau an der interessantesten Stelle.
          conversation_id: gespraechId,
          // Wie bei `/explain`: nur Runden dieser Seite — plus die Erklärung,
          // die gerade darüber entstanden ist und noch nicht im Zustand steht.
          history: [
            ...gedaechtnis(turns, route, MAX_TURNS_KONTEXT).map((t) => ({
              question: frageMitZitat(t), answer: t.answer })),
            ...(opts.dazu ? [opts.dazu] : []),
          ].slice(-MAX_TURNS_KONTEXT)
            .map((t) => ({ question: t.question.slice(0, 200), answer: t.answer.slice(0, 300) })),
          screen: {
            route,
            heading: seitenUeberschrift(document, anzeigename).slice(0, 200),
            element_title: letzterBaustein.current?.title ?? "",
            element_text: (letzterBaustein.current?.text ?? "").slice(0, 600),
            // 600: `qa.SCREEN_SELECTION_MAX` — die Ratsfrage nimmt weniger
            // mit als die Erklärung.
            selection: (opts.auswahl ?? markierung).slice(0, 600),
            // **Die Kennung, nicht nur der Text.** Ohne sie suchte das Archiv
            // nach Ähnlichkeit: Auf der Seite des Beschlusses „Weitenmesser im
            // Marschwegstadion" (2020) beantwortete „Wer hat dagegen gestimmt?"
            // eine Frage zu den Stadion-Richtlinien von 2025. Dieselben `refs`
            // wie bei `/assistant/explain` — der Client kennt sie ohnehin.
            refs,
          },
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        patch(() => ({
          answer: res.status === 429
            ? "Du hast gerade viele Fragen gestellt — probier es in ein paar Minuten noch mal."
            : "Das hat gerade nicht geklappt.",
          fehler: true,
        }));
        return;
      }
      await leseSseStrom(res.body, (msg) => {
        // Die Ratsfrage meldet drei Schritte (`expand`, `search`, `answer`) —
        // dieselbe Abbildung wie auf der Fragen-Seite, aus `lib/qa-schritte.ts`.
        if (msg.type === "step") patch(() => ({ schritt: msg.step as string }));
        else if (msg.type === "token") patch((t) => ({ answer: t.answer + (msg.text as string) }));
        else if (msg.type === "replace") patch(() => ({ answer: (msg.text as string) ?? "" }));
        else if (msg.type === "sources") {
          patch(() => ({ quellen: (msg.sources as LottiQuelle[]) ?? [] }));
        } else if (msg.type === "done") {
          patch(() => ({ cited: (msg.cited as number[]) ?? [] }));
          // **Auch das erste Gespräch entsteht hier.** Bis 22.09.2026 stand
          // hier ein `&& gespraechId != null`: Ohne laufendes Gespräch legte
          // `/ask` eines der Art `ask` an, und die Liste hätte ein
          // Mischwesen gezeigt. Das Backend kennt Lottis Fenster inzwischen
          // am mitgeschickten `screen` und legt dann ein `lotti`-Gespräch an
          // — die Sperre schützte also vor etwas, das es nicht mehr gibt,
          // und kostete den Faden: Ist die erste Frage im Fenster eine
          // Archivfrage (seit PR 23 der Normalfall), lief die nächste
          // Erklärung in ein zweites Gespräch zur selben Sache.
          if (msg.conversation_id != null) {
            setGespraechId(msg.conversation_id as number);
          }
        } else if (msg.type === "error") {
          patch(() => ({ answer: (msg.message as string) ?? "Frage fehlgeschlagen.", fehler: true }));
        }
      });
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      patch(() => ({ answer: "Das hat gerade nicht geklappt.", fehler: true }));
    } finally {
      if (abbruch.current === ctrl) {
        setLaden(false);
        abbruch.current = null;
      }
    }
  }, [markierung, refs, route, gespraechId, turns, setGespraechId, anzeigename]);

  const fragen = useCallback(async (
    text: string, mitMarkierung: boolean, baustein: ElementFrage | null = null,
    opts: {
      /** Welchen Baustein dieser Aufruf ERKLÄRT — aus einem „… erklären"-
       *  Chip. Gemerkt wird er nur, damit derselbe Chip nicht zweimal
       *  erscheint. */
      anker?: Anker;
      /** Eine Markierung, an der „Lotti fragen" gedrückt wurde. Sie ersetzt
       *  die laufende Auswahl: Die kann schon weg sein (Handy) oder eine
       *  andere (man hat weitermarkiert, während das Fenster aufging). */
      markiert?: MarkierFrage;
    } = {},
  ) => {
    const sauber = text.trim();
    const markiert = opts.markiert ?? null;
    const auswahl = markiert ? markiert.auswahl : (mitMarkierung ? markierung : "");
    if (!sauber && !auswahl && !baustein) return;
    // Ohne beantwortete Einwilligung wird nicht gefragt: Der Satz über die
    // externe Verarbeitung steht in der Karte, und sie ist die einzige Stelle,
    // an der er VOR der ersten Frage steht.
    if (merken === null || merken === undefined) return;

    // **Die Lotsin, bevor das Modell dran ist.** „Wo finde ich …?" ist keine
    // Ermessensfrage: Die Anker der Seite sind eine Landkarte, die der Client
    // schon hat. Trifft ein Titel, entsteht die Antwort hier — in unter einer
    // Millisekunde, ohne Netz, ohne Kosten.
    //
    // **Kein Aufruf heißt auch kein Turn im Konto.** Die Runde steht im
    // Verlauf des Tabs und verschwindet mit ihm; gespeichert wird nur, was
    // über `/council/explain` läuft (dort hängt die Einwilligung). Das ist
    // vertretbar: Gespeichert würde „Wo finde ich X?" → „unter X" — ein
    // Gesprächsverlauf, den niemand nachliest, zum Preis eines Schreibwegs
    // durchs ganze Backend.
    const anker = ankerListe(document);
    if (!baustein && !auswahl && ortsfrage(sauber)) {
      const treffer = ankerTreffer(sauber, anker);
      if (treffer.length) {
        abbruch.current?.abort();
        setFrage("");
        setTurns((ts) => [...ts, {
          key: naechsterKey.current++, question: sauber, next: null, mode: "local",
          kontext: "auf dieser Seite gefunden", route,
          seite: seitenName(document, anzeigename), zeigen: treffer,
          answer: treffer.length === 1
            ? `Das steht auf dieser Seite unter „${treffer[0].titel}“.`
            : "Das steht auf dieser Seite — ich vermute hier:",
        }]);
        return;
      }
    }

    abbruch.current?.abort();
    const ctrl = new AbortController();
    abbruch.current = ctrl;
    setFrage("");
    setLaden(true);

    // Unter der Frage: woher sie kommt. Bei einer Markierung steht das Zitat
    // schon IN der Blase — dann nur der Baustein, in dem sie lag, und ob sie
    // gekürzt wurde (sonst glaubte man, Lotti habe alles gelesen).
    const kontext = markiert
      ? [markiert.element?.title, markiert.gekuerzt ? "Markierung gekürzt" : null]
        .filter(Boolean).join(" · ")
      : baustein
        ? (baustein.title || "Baustein auf der Seite")
        : (auswahl ? `Markiert: „${kuerze(auswahl, 40)}“` : "");
    if (baustein) letzterBaustein.current = baustein;
    const key = naechsterKey.current++;
    setTurns((ts) => [...ts, {
      key, question: sauber, answer: "", next: null, mode: null, kontext,
      route, seite: seitenName(document, anzeigename),
      baustein: opts.anker,
      zitat: markiert?.text,
    }]);

    const bildschirm: Bildschirm = {
      route,
      page_title: seitenTitel(document),
      // Der PFAD, nicht nur die `h1`: „Schulden › Rate-Treppe" sagt Lotti,
      // wo auf der Seite sie steht, ohne den Seitentext mitzuschicken. Er
      // wird beim Antippen berechnet — nur dort liegt der Knoten noch vor.
      heading: baustein?.pfad || markiert?.pfad
        || ueberschriftenPfad(null, document, anzeigename),
      element: baustein,
      selection: auswahl,
      refs,
    };

    const patch = (fn: (t: LottiTurn) => Partial<LottiTurn>) =>
      setTurns((ts) => ts.map((t) => (t.key === key ? { ...t, ...fn(t) } : t)));

    /** Der Weg ins Archiv, sobald dieser Strom durch ist.
     *
     *  `"statt"`: Der Server hat gar nicht erst erklärt (`mode: "handoff"`) —
     *  die Runde, die schon dasteht, wird zur Archiv-Runde.
     *  `"danach"`: Die Erklärung steht, und das Modell hat weitergereicht —
     *  die Archivantwort kommt als zweiter Schritt darunter. */
    let archivWeg: "statt" | "danach" | null = null;
    /** Der Antworttext, wie er hier entsteht — der Zustand `turns` trägt ihn
     *  erst nach dem nächsten Zeichnen, die Ratsfrage braucht ihn aber sofort
     *  als Gedächtnis. */
    let antwort = "";

    try {
      const res = await fetch(apiUrl("/council/explain"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          route: bildschirm.route,
          page_title: bildschirm.page_title,
          heading: bildschirm.heading,
          element: bildschirm.element,
          selection: bildschirm.selection,
          question: sauber,
          refs: bildschirm.refs,
          // **Die Landkarte der Seite — nur die Titel.** Trifft der Abgleich
          // oben nichts, soll die Antwort wenigstens sagen können „das steht
          // unter „Rate-Treppe", weiter unten". Ohne diese Liste kennt das
          // Modell die Bausteine nicht und beschreibt die Seite im Ungefähren.
          // Kein Seiteninhalt: ein Titel ist unser eigener Komponententext.
          anchors: anker.map((a) => a.titel),
          // **Nur Runden DIESER Seite** — der Verlauf überlebt den
          // Seitenwechsel, das Gedächtnis nicht (lib/assistentin.ts).
          history: gedaechtnis(turns, route, MAX_TURNS_KONTEXT)
            .map((t) => ({ question: frageMitZitat(t).slice(0, 200), answer: t.answer.slice(0, 300) })),
          // Das laufende Gespräch. Das Feld MUSS mit, auch als `null`: Der
          // Server speichert nur, wenn der Client es überhaupt geschickt hat
          // (`model_fields_set`) — so bleibt ein alter Client stumm, statt
          // ungefragt Gespräche anzulegen.
          conversation_id: gespraechId,
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        // 400 heißt: Zu dieser Seite gibt es nichts zu sagen — der Grund steht
        // in der Antwort und ist für Menschen geschrieben.
        let msg = "Dazu kann ich gerade nichts sagen.";
        try {
          const b = await res.json();
          if (typeof b?.detail === "string") msg = b.detail;
        } catch { /* kein JSON — dann bleibt der allgemeine Satz */ }
        patch(() => ({ answer: msg, fehler: true }));
        return;
      }
      await leseSseStrom(res.body, (msg) => {
        // **Der Schritt, den das Fenster bis 22.09.2026 wegwarf.** Der Server
        // meldet `context` und `answer`, seit es den Endpunkt gibt; angezeigt
        // wurden drei blasse Punkte, an denen man nicht sah, dass etwas läuft.
        if (msg.type === "step") patch(() => ({ schritt: msg.step as string }));
        else if (msg.type === "token") {
          antwort += msg.text as string;
          patch((t) => ({ answer: t.answer + (msg.text as string) }));
        } else if (msg.type === "replace") {
          const { text: rein, next } = trenneWeiter((msg.text as string) ?? "");
          antwort = rein;
          if (next === "ratsfrage") archivWeg = "danach";
          patch(() => ({ answer: rein, next }));
        } else if (msg.type === "done") {
          // **Der Weg ins Archiv ist unsere Entscheidung, nicht ihre.** Bis
          // 22.09.2026 stand hier ein Knopf „Den Rat fragen" — Tim: „Ich weiß
          // als User gar nicht, was heißt denn ‚den Rat fragen‘? Ich dachte,
          // ich frage gerade die Informationen aus dem Rat."
          if (msg.mode === "handoff") archivWeg = "statt";
          else if ((msg.next as string | null) === "ratsfrage") archivWeg = "danach";
          patch((t) => ({
            next: (msg.next as "ratsfrage" | null) ?? t.next,
            // Geprüft hat der Server: in `kern/knowledge.py`, im
            // Haushalts-Bereich, für dieses Konto erreichbar. Der Client
            // navigiert nur — er prüft die Route nicht ein zweites Mal und
            // baut sie auch nicht selbst.
            nextPage: (msg.next_page as NaechsteSeite | null) ?? null,
            mode: (msg.mode as string) ?? null,
            // Die Papiere, die im Prompt standen. `?? []` und nicht
            // `?? t.evidence`: Der `done`-Rahmen ist die vollständige
            // Auskunft dieser Runde — käme er ohne Belege, wäre ein
            // stehengebliebener Chip aus einem früheren Zustand eine
            // Quellenangabe, die zu nichts mehr gehört.
            evidence: (msg.evidence as LottiBeleg[]) ?? [],
          }));
          // `null` heißt: Der Server konnte oder durfte nicht (mehr) in dieses
          // Gespräch speichern — die tote Kennung nicht weiter mitschicken,
          // die nächste Frage eröffnet frisch.
          if (msg.conversation_id != null) setGespraechId(msg.conversation_id as number);
          else if ("conversation_id" in msg) setGespraechId(null);
        } else if (msg.type === "error") {
          archivWeg = null;
          patch(() => ({ answer: (msg.message as string) ?? "Erklärung fehlgeschlagen.", fehler: true }));
        }
      });
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      // Die Frage ist nicht verloren — sie steht wieder im Eingabefeld
      // (Designsprache § 6: „Fehler/Limits: immer mit Ausweg").
      patch(() => ({ answer: "Das hat gerade nicht geklappt.", fehler: true }));
      setFrage(sauber);
      return;
    } finally {
      if (abbruch.current === ctrl) {
        setLaden(false);
        abbruch.current = null;
      }
    }

    // **Erst NACH dem Strom**, nicht im `done`-Rahmen: Dort liefe der
    // Abbruch-Wächter von `ratsfrageStellen` in den noch offenen
    // Erklär-Strom und risse ihn mitten im Satz ab.
    // Die Ratsfrage nimmt nur 600 Zeichen (`qa.SCREEN_SELECTION_MAX`). Passt
    // die Zeile samt Marken nicht, geht nur der markierte Teil — ein bei 600
    // abgeschnittenes „»" ohne „«" wäre schlechter als keine Zeile.
    const auswahlRat = [...auswahl].length <= 600 ? auswahl : (markiert?.text ?? auswahl);
    if (archivWeg === "statt") await ratsfrageStellen(sauber, { inTurn: key, auswahl: auswahlRat });
    else if (archivWeg === "danach") {
      await ratsfrageStellen(sauber, {
        dazu: { question: frageMitZitat({ question: sauber, zitat: markiert?.text }), answer: antwort },
        auswahl: auswahlRat,
      });
    }
  }, [markierung, refs, route, turns, gespraechId, merken, setGespraechId,
      anzeigename, ratsfrageStellen]);

  // „Lotti fragen" an einer Markierung fragt von selbst — der Tipp auf den
  // Knopf IST die Frage, ein zweiter Klick im Fenster wäre einer zu viel.
  // Danach wird sie verbraucht, sonst feuerte jedes Neuzeichnen erneut.
  //
  // **Und sie wartet auf die Einwilligung.** Wer zum ersten Mal fragt, sieht
  // zuerst die Karte; ohne Antwort darauf fragt `fragen` nichts. Bis
  // 23.09.2026 wurde der angetippte Baustein trotzdem verbraucht — die Frage
  // war dann einfach weg. Jetzt steht sie, bis die Karte beantwortet ist.
  useEffect(() => {
    if (!markiert || !offen || merken == null) return;
    // Der Baustein um die Markierung geht als Kontext mit, gilt aber NICHT
    // als erklärt: Gefragt wurde nach einem Stück davon, nicht nach ihm —
    // der Anschluss-Chip „… erklären" darf ihn weiter anbieten.
    void fragen("Was bedeutet das?", false,
      markiert.element ? { ...markiert.element, pfad: markiert.pfad } : null,
      { markiert });
    onMarkiertVerbraucht();
    // `fragen` hängt am Verlauf und wechselt mit jeder Runde — in der
    // Abhängigkeitsliste stünde es für „bei jeder Antwort noch einmal fragen".
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markiert, offen, merken]);

  // Ein gespeichertes Lotti-Gespräch aus der Liste „Gespräche".
  useEffect(() => {
    if (!ladeGespraech || !offen) return;
    let abgebrochen = false;
    (async () => {
      try {
        const r = await fetch(apiUrl(`/council/conversations/${ladeGespraech}`),
                              { credentials: "include", headers: authHeaders() });
        if (!r.ok) throw new Error();
        const g = await r.json();
        if (abgebrochen) return;
        type Gespeichert = { question: string; answer: string; sources: {
          route?: string; element_title?: string; selection?: string;
          mode?: string; next?: string | null; evidence?: LottiBeleg[] } | null };
        setTurns((g.turns as Gespeichert[]).map((tn) => ({
          key: naechsterKey.current++,
          question: tn.question,
          answer: tn.answer,
          next: (tn.sources?.next as "ratsfrage" | null) ?? null,
          mode: tn.sources?.mode ?? null,
          // Die Grundlage gehört zum Gespräch, nicht zur Sitzung: Ein
          // geladener Verlauf, der die Zahlen zeigt und die Papiere
          // verschweigt, wäre die schlechtere Hälfte davon.
          evidence: tn.sources?.evidence ?? [],
          // Der Schnappschuss trägt die Route, aber keinen Seitennamen —
          // dann steht in der Zäsur die Route. Sie ist immerhin wahr.
          route: tn.sources?.route,
          // Wo gefragt wurde, steht im Schnappschuss — der Element-TEXT nicht
          // (Regel 2: Seiteninhalt wird nicht im Konto verdoppelt).
          kontext: tn.sources?.element_title || tn.sources?.route || "",
          // Die ersten 200 Zeichen der Markierung stehen im Schnappschuss
          // (routers/council.py) — genug für das Zitat über der Frage.
          zitat: tn.sources?.selection || undefined,
        })));
        setGespraechId(ladeGespraech);
      } catch {
        // Kein Toast: Das Fenster steht offen, und eine leere Fläche mit
        // dem Begrüßungssatz ist eine ehrlichere Antwort als eine Meldung,
        // die man wegklickt. Die Liste „Gespräche" bleibt, wo sie war.
      } finally {
        if (!abgebrochen) onGespraechGeladen?.();
      }
    })();
    return () => { abgebrochen = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ladeGespraech, offen]);

  const neuAnfangen = () => {
    abbruch.current?.abort();
    setTurns([]);
    setFrage("");
    setGespraechId(null);
    try { sessionStorage.removeItem(SPEICHER); } catch { /* egal */ }
    eingabeRef.current?.focus();
  };

  /** Ein „Zeig mir"-Chip: hinscrollen, hervorheben — und auf dem Handy das
   *  Fenster schließen, weil es genau die Fläche bedeckt, auf die gezeigt
   *  wird. Am Schreibtisch
   *  bleibt es offen: Dort steht es neben der Seite, und das Gespräch geht
   *  weiter. */
  const zeigMir = (anker: Anker) => {
    const handy = !window.matchMedia?.(DESK).matches;
    if (handy) onSchliessen();
    // Erst schließen, dann scrollen: Solange das Fenster steht, rechnet der
    // Browser die Mitte des Viewports mit ihm.
    window.setTimeout(() => zeigeBaustein(anker), handy ? 60 : 0);
  };

  /** „Im Ratsarchiv nachsehen" — der Nachweg, wenn Lotti geantwortet hat und
   *  die Person trotzdem tiefer will.
   *
   *  **Ein Verb, das sagt, was passiert.** Der Knopf hieß bis 22.09.2026 „Den
   *  Rat fragen" und war ein Name aus der Innensicht: Für uns ist „Frag den
   *  Rat" das andere Feature, für die Person ist Lotti *die* Stelle, an der
   *  sie den Rat fragt (Tim: „Ich dachte, ich frage gerade die Informationen
   *  aus dem Rat"). */
  const zurRatsfrage = (t: LottiTurn) => {
    void ratsfrageStellen(t.question || "Was wurde dazu beschlossen?");
  };

  /** „<Titel> erklären" — den Baustein am DOM-Knoten ernten und samt
   *  `element_key` schicken. **Ohne Scrollen**: Wer hier fragt, will die
   *  Erklärung im Fenster lesen, nicht an eine andere Stelle der Seite
   *  gebracht werden — dafür gibt es „Zeig mir". */
  const erklaerAnker = (a: Anker) => {
    const el = ankerKnoten(a);
    // Weg (nachgeladen, Reiter gewechselt)? Dann passiert nichts — eine
    // Meldung über einen verschwundenen Kasten hülfe niemandem.
    if (!el) return;
    void fragen("", false,
      { ...ernteElement(el), pfad: ueberschriftenPfad(el, document, anzeigename) },
      { anker: a });
  };

  if (!offen) return null;

  /** Welche Bausteine in dieser Sitzung schon erklärt wurden.
   *
   *  Der Verlauf IST dieses Gedächtnis; ein eigener Zustand daneben liefe
   *  beim Seitenwechsel und beim Laden eines gespeicherten Gesprächs
   *  auseinander. */
  const erklaert = new Set<string>();
  for (const t of turns) {
    if (t.baustein) erklaert.add(ankerKennung(t.baustein));
  }
  // Die Landkarte der AKTUELLEN Seite. Sie steht nur der letzten Runde zu:
  // Ein „Erklär mir: …" unter einer Antwort von vor drei Seiten zeigte auf
  // Bausteine, die dort gar nicht stehen.
  //
  // **Nicht während des Stroms.** Jedes Token zeichnet das Fenster neu; ein
  // `querySelectorAll` je Zeichen wäre Arbeit für eine Antwort, die noch gar
  // nicht fertig ist — und Chips unter einem halben Satz sind ohnehin falsch.
  const ankerJetzt = laden ? [] : ankerListe(document);

  const kontextZeile = [
    // **Dieselbe Überschrift, die auch das Backend bekommt** — ohne den
    // Anzeigenamen und ohne einen reinen Gruß. Bleibt nichts übrig (auf
    // `/dashboard` ist die `h1` nur „Moin, …!"), steht hier der Seitentitel:
    // „Du bist auf: Heute". Eine zweite Tabelle mit Seitennamen entsteht so
    // nicht — der Titel steht ohnehin im Fenstertitel der Seite.
    seitenName(document, anzeigename),
    markierung ? `markiert: „${kuerze(markierung, 40)}“` : null,
  ].filter(Boolean).join(" · ");

  return (
    <div
      id="lotti-fenster"
      ref={fensterRef}
      role="dialog"
      aria-label="Lotti fragen"
      data-lotti-fenster
      // **Die Tastatur schiebt das Fenster hoch, statt es zu verdecken.**
      // Als `margin-bottom` und nicht als eigene `bottom`-Klasse: Das Fenster
      // rechnet seinen Abstand oben wie unten aus zwei Variablen zusammen,
      // und zwar je Breakpoint verschieden. Ein Rand davor schiebt beide
      // Fassungen gleich weit hoch, ohne dass hier eine dritte Rechnung
      // entsteht, die mit der nächsten Änderung auseinanderläuft.
      // Die Tastatur schiebt das Fenster hoch, statt es zu verdecken. Als
      // Variable und nicht als fertige Klasse: Tailwind kennt den Wert nicht
      // zur Bauzeit, er entsteht erst beim Tippen.
      style={{ "--rl-tastatur": `${tastatur}px` } as React.CSSProperties}
      className={cn(
        "fixed z-50 flex flex-col overflow-hidden rounded-2xl border border-border",
        "bg-card shadow-lifted print:hidden",
        "animate-in fade-in-0 slide-in-from-bottom-4 duration-buehne ease-out-strong",
        // Handy: die Fläche zwischen Kopfleiste und Knopf.
        "inset-x-2 top-[calc(env(safe-area-inset-top)+4.5rem)]",
        "bottom-[calc(var(--rl-unten,0px)+var(--rl-composer,0px)+5rem+var(--rl-tastatur,0px))]",
        // Schreibtisch: ein Fenster über dem Knopf.
        "desk:inset-x-auto desk:top-auto desk:right-6 desk:w-96",
        "desk:bottom-[calc(var(--rl-composer,0px)+5.5rem+var(--rl-tastatur,0px))]",
        "desk:h-[min(40rem,100dvh-9rem)]",
      )}
    >
      {/* Kopfzeile */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Mascot
          regung={laden ? "schreibt" : "ruht"}
          decorative
          className="h-8 w-8 flex-none"
        />
        <span className="flex-1 font-display text-base font-bold text-foreground">Lotti</span>
        {turns.length > 0 && (
          <button
            type="button"
            onClick={neuAnfangen}
            aria-label="Neu anfangen"
            title="Neu anfangen"
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <RotateCcw className="h-4 w-4" aria-hidden />
          </button>
        )}
        <button
          type="button"
          onClick={onSchliessen}
          aria-label="Lotti schließen"
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring desk:hidden"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {/* Kontext-Pille: worüber reden wir gerade? */}
      {kontextZeile && (
        <p data-lotti-kontext className="border-b border-border/60 bg-muted/40 px-3 py-1.5 text-meta text-muted-foreground">
          <span className="font-medium text-foreground/80">Du bist auf:</span> {kontextZeile}
        </p>
      )}

      {/* Verlauf */}
      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {merken === null && (
          <GespraecheEinwilligung
            kompakt
            onEntschieden={(ja) => { setMerken(ja ? 1 : 0); refresh(); }}
          />
        )}
        {turns.length === 0 && merken !== null && (
          <div className="flex flex-col items-center gap-2 px-2 pt-4 text-center">
            <Mascot pose="wave" decorative className="h-16 w-16" />
            <p className="text-hinweis text-muted-foreground">
              Moin! Ich erkläre dir, was du hier siehst. Markier etwas auf der
              Seite oder frag mich einfach.
            </p>
          </div>
        )}
        {turns.map((t, i) => {
          // **Alles, was weiterführt, gehört der LETZTEN Runde auf DIESER
          // Seite** — der Chip wie der Textlink ins Archiv. „Als Nächstes"
          // gibt es nur einmal; bis 22.09.2026 trug jede ältere Runde ihren
          // eigenen „Den Rat fragen"-Knopf, und zusammen war das die Wand,
          // die Tim gesehen hat.
          const jetzt = i === turns.length - 1 && t.route === route;
          const vorschlaege = jetzt
            ? anschlussfragen(t, ankerJetzt, erklaert, route) : [];
          // Der Nachweg ins Archiv — nur unter einer Runde, die NICHT schon
          // von dort kam (das wäre ein Kreis), und nur unter der letzten.
          const archivLink = jetzt && t.answer && !t.fehler
            && !t.ratsfrage && t.mode !== "local";
          return (
          <div key={t.key} className="space-y-2">
            {/* Die Zäsur: Ab hier wurde auf einer anderen Seite gefragt.
                Dieselbe stille Bauform wie die Kontextzeile an der Frage
                (mono, 10 px, Versalien, Muted), dazu eine Linie darüber —
                sie ordnet ein, sie ruft nicht. Die Linie steht OBEN und nicht
                links und rechts daneben: Ein Beschlusstitel füllt die 384 px
                allein und schiebt beide Striche auf null (gemessen am
                Weitenmesser-Beschluss, 21.09.2026). */}
            {zaesur(turns, i) && (
              <p data-lotti-zaesur
                className="mt-1 border-t border-border pt-2 text-center font-mono text-[10px] uppercase leading-relaxed tracking-[0.1em] text-muted-foreground">
                Jetzt auf: {zaesur(turns, i)}
              </p>
            )}
            {t.question && !t.frageVerborgen && (
              <p data-lotti-frage
                className="ml-6 rounded-xl rounded-br-sm border border-primary/[0.18] bg-primary/[0.07] px-2.5 py-1.5 text-[13.5px] text-foreground">
                {frageMitZitat(t)}
              </p>
            )}
            {t.kontext && (
              <p className="ml-6 text-right font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                {t.kontext}
              </p>
            )}
            <div className="flex gap-2">
              <Mascot
                regung={t.fehler ? "ist-traurig" : "erklaert"}
                decorative
                className="mt-0.5 h-6 w-6 flex-none"
              />
              <div className="min-w-0 flex-1">
                {t.answer
                  ? (
                    /* **Fachwörter klappen hier auf, statt zu überlagern.**
                       Der Popover aus `glossary-text.tsx` ist bis zu 17 rem
                       breit und liegt am Wort; im 384-px-Fenster mit
                       `overflow-hidden` schneidet ihn der Rand ab, sobald das
                       Wort rechts steht (Tim, 22.09.2026). Der Bereich steht
                       um EINE Antwort: ein zweites Wort ersetzt das erste. */
                    <GlossarAufklappBereich className="text-[13.5px] leading-relaxed text-foreground/90">
                      <AntwortText text={t.answer} idToNum={new Map()} />
                    </GlossarAufklappBereich>
                  )
                  : <Tippt schritt={t.schritt} ratsfrage={t.ratsfrage} />}
                {t.answer && !t.fehler && t.ratsfrage && (
                  <Quellen turn={t} onSchliessen={onSchliessen} />
                )}
                {/* „Zeig mir": der Weg zum Baustein — dieselbe Chip-Bauform
                    wie die Vorschläge unten, damit ein Chip überall dasselbe
                    verspricht. Ein Klick scrollt hin und setzt für zwei
                    Sekunden einen Ring. */}
                {t.zeigen?.length ? (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {t.zeigen.map((a) => (
                      <Chip key={`${a.key}|${a.titel}`} onClick={() => zeigMir(a)}>
                        Zeig mir: {a.titel}
                      </Chip>
                    ))}
                  </div>
                ) : null}
                {/* **Höchstens EIN Chip** (PR 24) — deterministisch aus dem
                    Wegweiser, den Ankern der Seite und den Fachwörtern der
                    Antwort, ohne zweiten Modellaufruf. Bis 22.09.2026 standen
                    hier bis zu zwei Chips PLUS der Archiv-Knopf, darunter die
                    Daumen und darunter die Grund-Chips: sieben Bedienelemente
                    für eine Antwort. Jedes war einzeln begründet; die Summe
                    hat sich niemand angesehen. */}
                {vorschlaege.length > 0 && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {vorschlaege.map((v) => (
                      v.art === "seite"
                        ? (
                          /* Der Weg zur richtigen Haushalts-Seite. Das Fenster
                             bleibt OFFEN: Der Verlauf überlebt den Wechsel und
                             bekommt die Zäsur „Jetzt auf: …" (PR 13) — wer
                             dort weiterfragt, fragt auf der neuen Seite. */
                          <Chip key={`s-${v.seite.route}`}
                            onClick={() => router.push(v.seite.route)} disabled={laden}>
                            Weiter zu: {chipTitel(v.seite.title)}
                          </Chip>
                        )
                        : v.art === "anker"
                        ? (
                          /* **Eine Handlung, kein Etikett.** „Erklär mir: Die
                             Anzeigetafel" war die Innensicht — es beschrieb,
                             was das Fenster verschickt. */
                          <Chip key={`a-${ankerKennung(v.anker)}`}
                            onClick={() => erklaerAnker(v.anker)} disabled={laden}>
                            {erklaerAktion(v.anker.titel)}
                          </Chip>
                        )
                        : null
                    ))}
                  </div>
                )}
                {/* Die Turn-Fußzeile: Daumen nur unter einer Antwort, die ein
                    MODELL geschrieben hat (B6 der zweiten Durchsicht). Der
                    Endpunkt nimmt `source = "lotti"` seit PR 7 an — gezählt
                    wurde bisher nur die Annahme, nie die Güte.

                    **Deterministische Antworten bekommen keinen Daumen**
                    (`mode === "deterministic"`: Glossar, Seiten-Wissen,
                    „Lotti erklärt's einfach"). Das ist geprüfter, von
                    Menschen bzw. in einem eigenen Lauf erzeugter Text, den
                    das Fenster nur durchreicht; ein Daumen darunter bewertete
                    das Glossar, nicht die Assistentin — und stünde in
                    derselben Quote wie ihre Erklärungen. */}
                {/* **Die Grundlage steht VOR den Daumen** — sie gehört zur
                    Antwort, der Daumen ist das Urteil darüber. Wer wissen
                    will, worauf das beruht, soll es lesen, bevor er bewertet.
                    Sie ist kein Chip im Sinne von PR 24: Diese Regel zählt
                    Angebote, die eine neue Runde auslösen; ein Beleg löst
                    nichts aus, er öffnet ein Dokument. */}
                {t.answer && !t.fehler && <Grundlage belege={t.evidence} />}
                {(daumenZeigen(t) || archivLink) && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                    {daumenZeigen(t) && (
                      <FeedbackDaumen question={t.question} answer={t.answer} source="lotti" />
                    )}
                    {/* **Kein Chip, ein Textlink.** Der Chip war die laute
                        Bauform für einen Weg, den Lotti seit PR 23 von selbst
                        geht; was hier steht, ist der Nachweg für den Fall,
                        dass die Erklärung nicht gereicht hat — still, wie die
                        Icon-Aktionen einer Turn-Fußzeile. */}
                    {archivLink && (
                      <button
                        type="button"
                        onClick={() => zurRatsfrage(t)}
                        disabled={laden}
                        className="text-[11.5px] font-medium text-primary hover:underline disabled:opacity-50"
                      >
                        Im Ratsarchiv nachsehen
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
          );
        })}
        <div ref={endeRef} />
      </div>

      {/* **Die Grund-Chips stehen nur im LEEREN Fenster** (PR 24). Sie sagen,
          was man hier tun kann — das braucht, wer noch nichts gefragt hat.
          Danach steht dieselbe Aufforderung im Composer-Platzhalter. Bis
          22.09.2026 standen sie dauerhaft unter jedem Gespräch und waren zwei
          der sieben Bedienelemente unter Tims Antwort.

          **Die zwei Startfragen (PR 25) stehen an der Stelle, an der bis
          22.09.2026 „Was sehe ich hier?" allein stand** — wer nicht weiß, was
          er fragen kann, fragt nichts, und zwei kuratierte Fragen sagen das
          vor. „Was sehe ich hier?" bleibt, aber als DRITTER, kleinerer Chip
          im Sekundärstil darunter: Sie ist immer noch die richtige Antwort
          auf „ich weiß gar nicht, was ich fragen soll", nur nicht mehr die
          lauteste. Ohne geladene Startfragen (kurz beim Öffnen, oder eine
          Seite ohne welche) bleibt „Was sehe ich hier?" allein und im
          gewohnten Stil — sie ist der Fall, der IMMER geht.

          **Was hier seit 23.09.2026 fehlt:** „Etwas auf der Seite zeigen"
          (der Erklär-Modus, samt seinem Icon am Composer) und „Markiertes
          erklären". Beides macht jetzt der Knopf „Lotti fragen" an der
          Markierung selbst (`markier-knopf.tsx`) — am Wort statt hier unten,
          dieselbe Regel wie beim Fachwort: Der Weg AM WORT gewinnt. Wer bei
          stehender Markierung tippt, fragt weiterhin mit ihr (Kontext-Pille
          „markiert: …"). */}
      {turns.length === 0 && (
        <div className="flex flex-col gap-1.5 px-3 pb-1.5">
          {startfragen.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {startfragen.map((frage) => (
                <Chip key={frage} onClick={() => void fragen(frage, false)}
                     disabled={laden || merken == null}>
                  {frage}
                </Chip>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-1.5">
            <Chip onClick={() => void fragen("Was sehe ich hier?", false)}
                 disabled={laden || merken == null} sekundaer={startfragen.length > 0}>
              Was sehe ich hier?
            </Chip>
          </div>
        </div>
      )}

      {/* Composer */}
      <form
        onSubmit={(e) => { e.preventDefault(); void fragen(frage, !!markierung); }}
        className="flex items-center gap-2 border-t border-border px-3 py-2"
      >
        <Sparkles className="h-4 w-4 flex-none text-signal" aria-hidden />
        <input
          ref={eingabeRef}
          value={frage}
          onChange={(e) => setFrage(e.target.value)}
          placeholder="Frag mich zu dieser Seite …"
          aria-label="Frage an Lotti"
          className="min-w-0 flex-1 bg-transparent text-[13.5px] text-foreground outline-none placeholder:text-muted-foreground"
        />
        <button
          type="submit"
          disabled={laden || !frage.trim() || merken == null}
          aria-label="Fragen"
          className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors disabled:bg-primary/35"
        >
          <ArrowRight className="h-4 w-4" aria-hidden />
        </button>
      </form>
      {/* **Hier stand bis 22.09.2026 eine feste Fußzeile** („Erklärt aus
          Glossar, Seite und Haushaltsdaten. Keine Rechtsberatung, keine
          Bewertung."). Sie ist ersatzlos weg — Tims Befund: „der nimmt nur
          unnötig Platz weg". Zwei Zeilen à 11 px plus Trennlinie kosten im
          384-px-Fenster gut 30 px Verlaufshöhe, und zwar dauerhaft, für einen
          Satz, den man einmal liest.

          **Der rechtliche Hinweis hängt nicht daran** — er stand hier nie:
          Dass Frage und Auszüge über OpenRouter extern verarbeitet werden,
          sagt die Einwilligungs-Karte (`components/gespraeche-einwilligung.tsx`),
          die genau einmal und VOR der ersten Frage erscheint — auch in diesem
          Fenster; dauerhaft nachlesbar steht es in der Konto-Karte
          (`components/gespraeche-settings.tsx`) und unter /datenschutz. Dass
          Lotti nicht bewertet und nicht berät, setzt der Prompt durch
          (`kern/prompts.py`), nicht eine Zeile Kleingedrucktes. */}
    </div>
  );
}

/** Worauf die Zahlen ruhen: „Grundlage: Jahresabschluss 2024 · …"
 *
 *  **Ehrlich beschriftet.** Das sind die Papiere, die im Prompt STANDEN —
 *  nicht die Quelle einer bestimmten Zahl. Welchen Satz das Modell auf welche
 *  Zeile stützt, weiß niemand; die Auswahl dagegen ist nachprüfbar (sie kommt
 *  aus `qa.geld_auswahl`, derselben Schleife, die den Prompt füllt). Der
 *  `title` sagt es noch einmal für alle, die hovern.
 *
 *  **Dieselbe Bauform wie der Dokumentbeleg der Haushalts-Seiten**
 *  (`components/haushalt/source.tsx::Dokumentbeleg`): 11 px, gedämpfter
 *  Fließtext, das Dokument als halbfetter Primärlink mit dem
 *  Außen-Pfeil-Symbol. **Bewusst nachgebaut statt importiert**, und das ist
 *  kein Versehen: Dieses Fenster lebt in der App-Hülle und lädt damit auf
 *  JEDER Seite mit — `source.tsx` zöge `haushalt-quellen.ts` (50 KB),
 *  `haushalt-dokumente.ts` und `haushalt-streit.ts` in das Bündel jeder
 *  öffentlichen Seite, für zwölf Zeilen Markup. Wer die Optik dort ändert,
 *  ändert sie hier mit.
 *
 *  Wie aus einem Provenienz-Titel ein Chip-Name wird (Untertitel weg, Jahr
 *  nur wo es fehlt, dann kappen), steht in `lib/assistentin.ts::belegName` —
 *  mit den gemessenen Titeln, an denen es sich entschieden hat.
 */
function Grundlage({ belege }: { belege?: LottiBeleg[] }) {
  if (!belege?.length) return null;
  return (
    <p
      data-lotti-grundlage
      title="Quellen, die Lotti für diese Antwort vorlagen"
      className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[11px] leading-relaxed text-muted-foreground"
    >
      <span className="font-medium">Grundlage:</span>
      {belege.map((b, i) => {
        const name = belegName(b);
        return (
          <span key={`${b.label}|${b.year ?? ""}|${b.url ?? ""}|${i}`}
            className="inline-flex items-baseline gap-1">
            {b.url ? (
              <a href={b.url} target="_blank" rel="noopener noreferrer"
                // Der volle Name im `title`: Gekappt wird, was nicht ins
                // Fenster passt, nicht was wir wissen.
                title={b.label}
                className="inline-flex items-baseline gap-1 font-semibold text-primary hover:underline">
                {name}
                <ExternalLink className="h-3 w-3 flex-none self-center" aria-hidden />
              </a>
            ) : (
              /* Kein Link, aber der Name bleibt — genau wie beim
                 Dokumentbeleg: „Wir wissen, aus welchem Papier das stammt,
                 nur nicht, wo es liegt" ist eine Auskunft. */
              <span className="font-semibold text-foreground/80" title={b.label}>{name}</span>
            )}
          </span>
        );
      })}
    </p>
  );
}

/** Die Belege unter einer Ratsantwort — schlank.
 *
 *  **Was hier NICHT steht:** Presse, Debatten, der Parteien-Baustein, die
 *  Grafik. Dafür ist das Ratsgespräch da, und der Link dorthin steht
 *  darunter. In 384 px Breite wäre das alles eine Bleiwüste; die Frage, die
 *  hier beantwortet wird, ist „worauf beruht das?", nicht „zeig mir alles".
 */
function Quellen({ turn, onSchliessen }: { turn: LottiTurn; onSchliessen: () => void }) {
  const [alle, setAlle] = useState(false);
  const router = useRouter();
  const zitiert = new Set(turn.cited ?? []);
  // Zitierte zuerst: Sie tragen die Antwort, die übrigen sind Fundsachen.
  const quellen = [...(turn.quellen ?? [])].sort(
    (a, b) => Number(zitiert.has(b.id)) - Number(zitiert.has(a.id)));
  // **Standard: nur die ZITIERTEN.** Bis 22.09.2026 standen die ersten drei
  // Fundstücke da — gemessen auf `/council/decision?id=2982`: „1 zitiert · 41
  // gefunden" und darunter drei Zeilen, von denen zwei (Toleranz-Fonds,
  // Bebauungsplan Nr. 56) nichts mit der Frage zu tun hatten. Eine Quelle,
  // die falsch wirkt, beschädigt die beiden richtigen mit; es ist dieselbe
  // Sorte Rauschen, gegen die die Chip-Regel oben gebaut ist. Der Rest bleibt
  // erreichbar — hinter „Alle N Quellen", wie bisher.
  //
  // **Mindestens eine.** Zitiert das Modell nichts (es kommt vor), wäre eine
  // Antwort ganz ohne Beleg schlechter als die beste Fundsache.
  const belege = quellen.filter((q) => zitiert.has(q.id));
  const sichtbar = alle ? quellen : (belege.length ? belege : quellen.slice(0, 1));
  return (
    <div className="mt-2 space-y-1.5">
      {quellen.length > 0 && (
        <>
          <p className="font-mono text-[9.5px] uppercase tracking-[0.11em] text-muted-foreground">
            Quellen · {zitiert.size} zitiert · {quellen.length} gefunden
          </p>
          <ul className="space-y-1">
            {sichtbar.map((q) => (
              <li key={q.id}>
                <Link
                  href={decisionHref(q.id)}
                  onClick={onSchliessen}
                  className="block rounded-lg px-1.5 py-1 transition-colors hover:bg-primary/[0.06]"
                >
                  <span className={cn("text-[12.5px] leading-snug",
                    zitiert.has(q.id) ? "font-medium text-foreground" : "text-foreground/80")}>
                    {q.title ?? "Ohne Titel"}
                  </span>
                  <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground">
                    {[q.committee, q.session_date].filter(Boolean).join(" · ")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {quellen.length > sichtbar.length && (
            /* `block`, nicht inline: Der Abstandshalter des Elterndivs
               (`space-y-1.5`) greift nur zwischen BLOCK-Kindern — als
               inline-block stand „Alle 3 Quellen" ohne Lücke direkt vor
               „Im Ratsgespräch weiterführen" (gesehen am 22.09.2026, seit
               die Belege auf die zitierten zusammengeschrumpft sind und der
               Knopf damit überhaupt erscheint). */
            <button type="button" onClick={() => setAlle(true)}
              className="block text-[11.5px] font-medium text-primary hover:underline">
              Alle {quellen.length} Quellen
            </button>
          )}
        </>
      )}
      <button
        type="button"
        onClick={() => { onSchliessen(); router.push(fragenHref({ q: turn.question })); }}
        className="inline-flex min-h-8 items-center gap-1 text-[12px] font-medium text-primary hover:underline"
      >
        Im Ratsgespräch weiterführen
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </button>
    </div>
  );
}

/**
 * Die Tipp-Anzeige der Chat-Fenster — hier an einen echten Zustand gebunden.
 *
 * **Sie war bis 22.09.2026 kaum zu sehen**: drei 6-px-Punkte mit
 * `animate-pulse`, also eine reine Deckkraft-Welle, die sich im Fenster
 * verlor („man sieht fast nicht, dass da was lädt", Tim). Jetzt 8 px, eine
 * echte Hüpf-Animation mit Versatz (`lotti-tippt` in `app/globals.css`) —
 * und daneben der SCHRITT, den der Server ohnehin meldet. Ein Satz, der sagt
 * „Lotti liest die Seite", erklärt eine Sekunde Wartezeit; drei Punkte nicht.
 *
 * `role="status"` bleibt: Die Anzeige meldet sich, ohne den Fokus zu nehmen —
 * und mit dem Text meldet sie jetzt auch etwas Sagbares.
 */
function Tippt({ schritt, ratsfrage }: { schritt?: string | null; ratsfrage?: boolean }) {
  return (
    <span className="flex items-center gap-2 py-1" role="status">
      <span className="inline-flex flex-none items-center gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="lotti-tippt-punkt h-2 w-2 rounded-full bg-signal"
            // Der Versatz macht aus drei gleichen Punkten eine Welle. Als
            // Stil und nicht als Klasse: Tailwind kennt keine Staffelung.
            style={{ animationDelay: `${i * 160}ms` }}
          />
        ))}
      </span>
      <span className="min-w-0 text-hinweis text-muted-foreground">
        {lottiSchrittText(schritt, ratsfrage)} …
      </span>
    </span>
  );
}

function Chip({ children, onClick, disabled, sekundaer }: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean;
  /** Kleiner und blasser — für einen Chip, der neben den Startfragen (PR 25)
   *  nicht mehr der lauteste im Raum sein soll, aber trotzdem der Fall
   *  bleibt, der immer geht. */
  sekundaer?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center rounded-full border transition-colors disabled:opacity-50",
        sekundaer
          ? "min-h-7 border-border bg-transparent px-2 text-[11px] font-medium text-muted-foreground hover:bg-muted/60 hover:text-foreground"
          : "min-h-8 border-primary/30 bg-primary/[0.04] px-2.5 text-[12px] font-medium text-primary hover:bg-primary/10",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Wie hoch die Bildschirmtastatur gerade steht.
 *
 * Nötig, weil das Fenster `position: fixed` ist: Auf iOS schrumpft der
 * Layout-Viewport nicht, wenn die Tastatur aufgeht — die Eingabezeile läge
 * dahinter, und der Browser kann ein fixiertes Fenster nicht hereinscrollen.
 * Die Rechnung selbst steht in `lib/tastatur.ts` und ist dort geprüft.
 */
export function useTastatur(): number {
  const [hoehe, setHoehe] = useState(0);
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const messen = () => setHoehe(tastaturHoehe(vv, window.innerHeight));
    messen();
    vv.addEventListener("resize", messen);
    vv.addEventListener("scroll", messen);
    return () => {
      vv.removeEventListener("resize", messen);
      vv.removeEventListener("scroll", messen);
    };
  }, []);
  return hoehe;
}

/** Der markierte Text der Seite — als Hook, damit Knopf und Fenster dieselbe
 *  Quelle haben. Läuft über `selectionchange` mit kurzer Ruhepause: Während
 *  man mit der Maus zieht, feuert das Ereignis bei jedem Pixel. */
export function useMarkierung(): string {
  const [text, setText] = useState("");
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const onChange = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const fenster = document.querySelector("[data-lotti-fenster]");
        setText(auswahlText(document.getSelection(), fenster, document.activeElement));
      }, 250);
    };
    document.addEventListener("selectionchange", onChange);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("selectionchange", onChange);
    };
  }, []);
  return text;
}
