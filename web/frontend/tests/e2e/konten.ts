/**
 * Die Identitäten der Browser-Suite — und wo ihre fertige Sitzung liegt.
 *
 * WARUM ES DAS GIBT. Bis 09/2026 meldete sich fast jeder Test neu an: `/login`
 * aufrufen, zwei Felder ausfüllen, klicken, auf die Navigation warten, den
 * Einrichtungs-Assistenten per POST wegräumen, neu laden. Gemessen an einem
 * CI-Lauf kostete das rund 5 Sekunden je Test — bei einer Seite, die selbst in
 * 0,1 Sekunden da ist:
 *
 *     ✓ /login bleibt in der Breite            (1.5s)   ← ohne Anmeldung
 *     ✓ /topics bleibt in der Breite (angem.)  (6.3s)   ← mit Anmeldung
 *       [WebServer] GET /topics 200 in 129ms             ← die Seite selbst
 *
 * Über die ganze Suite war das gut die Hälfte der Laufzeit — für einen Vorgang,
 * den kein einziger dieser Tests prüfen will. Geprüft wird das Anmelden in
 * `01-auth.spec.ts`, und nur dort.
 *
 * Jetzt meldet `auth.setup.ts` jede Identität EINMAL je Lauf an und legt die
 * Sitzung als Datei ab; die Specs sagen `test.use({ storageState: … })` und
 * starten angemeldet. Der Browser bekommt das Cookie mit, statt es sich zu
 * erklicken.
 *
 * WAS EINE IDENTITÄT MITBRINGT. Nicht nur das Cookie: Der Einrichtungs-
 * Assistent ist abgehakt und „Gespräche merken?" beantwortet. Beides ist
 * Zustand am KONTO, kein Browser-Zustand — es steht nach dem Setup in der
 * Datenbank und gilt für jeden Test, der diese Identität benutzt.
 */
import path from "node:path";

/** Alle Saat-Konten tragen dasselbe (siehe `scripts/saat_konten.py`). */
export const PASSWORT = "password123";

export type Konto = {
  /** Kurzname — zugleich der Dateiname der abgelegten Sitzung. */
  name: string;
  email: string;
  /** Legt das Setup das Konto an? Die Saat-Konten gibt es schon. */
  anlegen?: boolean;
  wozu: string;
};

export const KONTEN: Konto[] = [
  {
    name: "admin",
    email: "admin@test.de",
    // Das einzige Konto, das die Suite selbst anlegt: Es ist die
    // `WEB_ADMIN_EMAIL` aus `tests/start-backend.sh` und wird damit beim
    // Bestätigen zum Admin. Die Saat lässt es ABSICHTLICH aus.
    anlegen: true,
    wozu: "Der Normalfall der meisten Specs; Admin, weil WEB_ADMIN_EMAIL.",
  },
  {
    name: "nutzerin",
    email: "nutzerin@example.org",
    wozu: "Ein gewöhnliches Konto ohne besondere Rechte.",
  },
  {
    name: "ratsfrau",
    email: "ratsfrau@example.org",
    wozu: "Trägt die Rolle `council_member` — das Recht `budget`.",
  },
  {
    name: "chef",
    email: "chef@example.org",
    wozu: "Admin aus der Saat — für die Grenze zum Admin-Panel.",
  },
];

/** Wo die fertige Sitzung einer Identität liegt.
 *
 *  Das Verzeichnis ist gitignored und wird je Lauf neu geschrieben: Die
 *  Datenbank hinter den Tests ist eine Wegwerf-Datei (`mktemp -d` in
 *  `tests/start-backend.sh`), ein Cookie von gestern zeigt also auf ein Konto,
 *  das es nicht mehr gibt. */
export function zustandsDatei(name: string): string {
  return path.join(__dirname, ".auth", `${name}.json`);
}
