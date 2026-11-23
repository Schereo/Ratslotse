import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

// ESLint für das Frontend (Flat Config, seit Next 16).
//
// Bis Next 15 stand das in `.eslintrc.json` und lief über `next lint`. Den
// Befehl gibt es nicht mehr, `eslint-config-next` 16 verlangt ESLint 9 und
// dieses Format. Regeln und Umfang sind dieselben geblieben; was sich durch
// den Sprung von selbst geändert hätte, ist unten ausdrücklich abgeschaltet.

// DERSELBE UMFANG WIE `next lint`: Der prüfte nur seine Standardordner. Hier
// steht das als Ausschluss von allem anderen in der Wurzel, damit `eslint .`,
// `npm run lint` und der Editor dasselbe sehen. Wer einen Ordner dazunimmt,
// nimmt seinen Bestand mit (`scripts/`, `tests/e2e/` und die Dateien in der
// Wurzel sind nie geprüft worden).
const GEPRUEFT = ["app", "components", "lib"];

// Das Plugin holt `eslint-config-next` nur für .ts/.tsx herein. Es wird hier
// für alle geprüften Dateien angemeldet, wie es die alte Konfiguration tat
// (`"plugins": ["@typescript-eslint"]`): Ein `eslint-disable` mit einer seiner
// Regeln bleibt damit überall gültig. Aus der Next-Konfiguration genommen
// statt neu importiert, denn ESLint lässt unter einem Namen nur EIN Objekt zu.
const typescriptPlugin = nextVitals
  .find((eintrag) => eintrag.plugins?.["@typescript-eslint"])
  .plugins["@typescript-eslint"];

// DIE NEUEN HOOK-REGELN SIND AUS, UND ZWAR BEWUSST.
//
// `eslint-plugin-react-hooks` 7 (kommt mit `eslint-config-next` 16) bringt in
// `recommended` vierzehn Regeln des React Compilers mit. Gezählt am
// 22.11.2026 auf dem Bestand: 141 Treffer, alle als Fehler, die Zahl steht
// hinter der Regel. Sie einzuschalten hieße, den Bestand umzubauen — das
// gehört nicht in denselben Schritt wie der Sprung auf Next 16 (dieselbe
// Überlegung wie bei `react/no-unescaped-entities`, s. frontend.yml).
// Folgearbeit: je Regel entscheiden, aufräumen, einschalten.
const NEUE_HOOK_REGELN = {
  "react-hooks/set-state-in-effect": "off", // 97
  "react-hooks/refs": "off", // 21
  "react-hooks/immutability": "off", // 9
  "react-hooks/static-components": "off", // 6
  "react-hooks/purity": "off", // 4
  "react-hooks/preserve-manual-memoization": "off", // 4
  "react-hooks/use-memo": "off", // 0
  "react-hooks/incompatible-library": "off", // 0
  "react-hooks/globals": "off", // 0
  "react-hooks/error-boundaries": "off", // 0
  "react-hooks/set-state-in-render": "off", // 0
  "react-hooks/unsupported-syntax": "off", // 0
  "react-hooks/config": "off", // 0
  "react-hooks/gating": "off", // 0
};

const NACKTES_FETCH =
  "Der Wrapper übersetzt Fehler, behandelt 401 zentral und setzt die Zeitgrenze. api.get/post/put/del aus lib/api.ts nehmen — oder, wo der Wrapper nicht passt (Streams), apiUrl() aus demselben Modul.";

export default defineConfig([
  ...nextVitals,
  {
    name: "ratslotse",
    plugins: { "@typescript-eslint": typescriptPlugin },
    // ESLint 9 meldet ein `eslint-disable`, das nichts mehr unterdrückt, von
    // sich aus als Hinweis; ESLint 8 tat das nicht. Vier Stellen im Bestand
    // (22.11.2026). Aus demselben Grund aus wie die Hook-Regeln oben, und
    // dieselbe Folgearbeit.
    linterOptions: { reportUnusedDisableDirectives: "off" },
    rules: {
      // Meldet das typografische Anführungszeichen in deutschem JSX-Text und
      // hat noch nie einen Fehler gefunden (s. frontend.yml).
      "react/no-unescaped-entities": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      ...NEUE_HOOK_REGELN,
      // Ans Backend nur über lib/api.ts (s. CLAUDE.md). Trifft genau ein
      // Zeichenketten- oder Template-Literal, das mit `/api/` beginnt.
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name='fetch'] > Literal[value=/^\\u002fapi\\u002f/]",
          message: `Nacktes fetch("/api/…"): ${NACKTES_FETCH}`,
        },
        {
          selector:
            "CallExpression[callee.name='fetch'] > TemplateLiteral > TemplateElement:first-child[value.raw=/^\\u002fapi\\u002f/]",
          message: `Nacktes fetch(\`/api/…\`): ${NACKTES_FETCH}`,
        },
      ],
    },
  },
  // Alles in der Wurzel außer den geprüften Ordnern (s. o.).
  globalIgnores(["*", ...GEPRUEFT.map((ordner) => `!${ordner}/`)], "ratslotse/umfang"),
  // Ausdrücklich, auch wenn der Umfang sie schon ausschließt: Bauverzeichnisse
  // (`.next`, `.next-dev`, `.next-build`, `.next-alt`), die gebaute Doku unter
  // `public/docs`, Berichte der Browsertests und die Clip-Drehbücher.
  globalIgnores(
    [".next*/**", "public/**", "playwright-report/**", "test-results/**", "release-clips/**"],
    "ratslotse/erzeugtes",
  ),
]);
