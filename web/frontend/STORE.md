# App-Store-Eintrag — fertige Feldwerte

Die Texte stammen aus dem Design-Canvas „App-Store-Release" und liegen hier,
weil App Store Connect sie nicht versioniert: Wer den Eintrag ändert, ändert ihn
hier mit. **Ergänzung zur Einreichungs-Checkliste in [MOBILE.md](MOBILE.md).**

Stand 14.08.2026, per App-Store-Connect-API gegen die App `6786553049`
(`de.ratslotse.app`) gesetzt und gegengelesen.

## Was in App Store Connect steht

| Feld | Stand |
|---|---|
| App-Datensatz, Bundle-ID, primäre Sprache `de-DE` | ✅ angelegt |
| Untertitel, Kategorien (Nachrichten/Bildung) | ✅ gesetzt |
| Beschreibung, Keywords, Werbetext, Support-/Marketing-/Datenschutz-URL | ✅ gesetzt |
| Altersfreigabe-Fragebogen | ✅ vollständig beantwortet → **4+** |
| Inhalte Dritter (`contentRightsDeclaration`) | ✅ `USES_THIRD_PARTY_CONTENT` (Begründung in den Prüfer-Notizen) |
| App-Review-Informationen: Kontakt, Demo-Zugang, Notizen | ✅ gesetzt |
| Screenshots iPhone 6.9" | ✅ 6 × 1320×2868, echte Simulator-Aufnahmen |
| Builds | ✅ 1–9 hochgeladen, Build 9 (12.08.) gültig |
| Version 1.0 | Status `PREPARE_FOR_SUBMISSION` — **nicht eingereicht** |
| „Neue Funktionen" | — bei Version 1.0 nicht editierbar (erst ab dem ersten Update) |
| EU-DSA-Trader-Status | ❌ offen, nur in der Oberfläche zu erklären |
| App-Datenschutz (Nutrition Labels) | ❌ offen, nur in der Oberfläche zu pflegen (Werte unten) |

Ab **September 2026** verlangt Apple die Antworten auf den neuen
Altersfreigabe-Fragebogen bei jeder Einreichung — sie stehen bereits drin.

## Metadaten

| Feld | Wert |
|---|---|
| App-Name (max. 30) | `Ratslotse: Oldenburg` (20) — aktuell steht nur „Ratslotse" drin. Mit dem Zusatz ist „Oldenburg" indexiert und kann aus den Keywords raus. |
| Untertitel (max. 30) | `Beschlüsse verständlich` (23) |
| Kategorie | Primär **Nachrichten**, sekundär **Bildung** |
| Keywords (max. 100) | `oldenburg,stadtrat,rat,kommunalpolitik,ratsinfo,beschlüsse,gemeinderat,lokalpolitik,bürger,rathaus` (98; „oldenburg" streichen, falls der Name den Zusatz bekommt) |
| Support-URL | `https://ratslotse.de/hilfe` (erreichbar) |
| Marketing-URL | `https://ratslotse.de` |
| Datenschutz-URL | `https://ratslotse.de/datenschutz` |
| Copyright | `© 2026 Tim Sigl` |
| Preis · Verkaufsgebiet | kostenlos, keine In-App-Käufe · Deutschland (AT/CH optional) |
| Veröffentlichung | manuell freigeben, danach stufenweise über 7 Tage |

## Beschreibung (max. 4000)

Der Unabhängigkeitssatz steht **zuerst**: Sichtbar sind ohne Klick nur die
ersten Zeilen, und genau dort will Guideline 5.2 die Klarstellung sehen. (Der
Canvas-Entwurf hat den Satz am Ende — das widerspricht seiner eigenen Vorgabe
aus Blocker B2.)

```
Ratslotse ist ein unabhängiges Bürgerprojekt und wird nicht von der Stadt Oldenburg herausgegeben.

Was beschließt eigentlich der Rat? Ratslotse macht die Arbeit des Oldenburger Stadtrats verständlich — für alle.

Kein PDF-Wälzen mehr: Frag in normaler Sprache, was der Rat zu einem Thema beschlossen hat, und bekomme eine verständliche Antwort mit Quellen. Durchsuche acht Jahre Beschlüsse, folge deinen Themen und behalte den Überblick, ohne jede Sitzung zu verfolgen.

FRAG DEN RAT
Stell eine Frage in deinen Worten. Die Antwort nennt Fußnoten und verlinkt jedes Original — nachprüfbar, nicht geraten.

JEDER BESCHLUSS, DURCHSUCHBAR
Volltextsuche mit Filtern nach Thema, Ausschuss, Ergebnis und Zeitraum. Mit einem Blick sehen, ob etwas angenommen, abgelehnt oder vertagt wurde.

DEINE THEMEN IM AUGE
Lege Themen wie „Radwege" oder „Kitas" an oder abonniere einen Ausschuss. Ratslotse meldet sich, wenn etwas dazu auf der Tagesordnung steht — höchstens zweimal am Tag, nachts nie.

ZAHLEN UND ZUSAMMENHÄNGE
Wer bringt welche Anträge ein, wohin fließt das Geld, wo in der Stadt ist der Rat gerade aktiv.

UND EIN QUIZ
Wie gut kennst du deine Stadt? Zehn Fragen, ehrlich schwerer als gedacht.

Alle Daten stammen aus dem offiziellen Ratsinformationssystem der Stadt Oldenburg und verlinken auf die Originaldokumente. Es besteht keine Verbindung zur Stadtverwaltung oder zum Stadtrat.

KI-Antworten können unvollständig sein — jede Antwort nennt ihre Quellen zum Nachprüfen. Für rechtsverbindliche Auskünfte gilt allein das amtliche Original.
```

**Werbetext** (max. 170, jederzeit ohne neue Version änderbar):

```
Verstehe, was dein Stadtrat beschließt — frag in normaler Sprache, folge deinen Themen und verpasse keine Entscheidung mehr. Aus der amtlichen Quelle.
```

**Neue Funktionen (v1.0):**

```
Moin! Das ist die erste Version von Ratslotse. Frag den Rat, durchsuche acht Jahre Beschlüsse, folge deinen Themen und probier das Quiz. Was fehlt dir? Schreib es Lotti direkt in der App.
```

## Altersfreigabe — Antworten auf den neuen Fragebogen

Ergebnis: **4+**. Die Feldnamen sind die der API (`ageRatingDeclaration`), damit
beim Ausfüllen nichts verwechselt wird.

| Feld | Antwort | Warum |
|---|---|---|
| `unrestrictedWebAccess` | nein | Kein eingebauter Browser; externe Links (Originaldokumente) öffnen im System-Browser. |
| `messagingAndChat` | nein | „Frag den Rat" ist keine Kommunikation zwischen Personen, sondern eine Auskunft aus den importierten Ratsdokumenten. Kein offener Chat, keine Websuche, keine Bildgenerierung. |
| `userGeneratedContent` | **ja** | Eine Person kann eine KI-Antwort bewusst als öffentlichen, nicht gelisteten Link veröffentlichen. Es gibt keinen Feed und keine Suche danach, aber Empfänger*innen können den Inhalt auch ohne Konto lesen und melden. Deshalb ehrlich als UGC deklarieren. |
| `socialMedia`, `socialMediaAgeRestricted` | nein | Keine Profile, keine Feeds, keine Kontakte. |
| `contests`, `gambling`, `gamblingSimulated`, `lootBox` | nein | Das Quiz hat keine Preise und keinen Einsatz. |
| `advertising` | nein | Keine Werbung, keine Werbe-SDKs. |
| `healthOrWellnessTopics`, `medicalOrTreatmentInformation` | nein | — |
| Gewalt, Sexualität, Schimpfwörter, Horror, Drogen, Waffen | nein / keine | Amtliche Ratsdokumente. |
| `kidsAgeBand` | leer | Keine Kids-Kategorie. |
| `ageAssurance`, `parentalControls` | keine | Keine Altersprüfung nötig. |

UGC ist im aktuellen Fragebogen eine Capability und kann bei ansonsten
unbedenklichen Inhalten weiterhin zu 4+ führen; entscheidend ist die ehrliche
Angabe. Freier, unmoderierter Web-/KI-Zugang oder tatsächlich problematische
Inhalte wären anders zu bewerten — Ratslotse bietet beides nicht.

## App-Datenschutz (App Privacy)

Muss exakt zu `ios/App/App/PrivacyInfo.xcprivacy` **und** zur
Datenschutzerklärung passen — Widersprüche sind ein häufiger Ablehnungsgrund.

| Datentyp | Verknüpft | Tracking | Zweck |
|---|---|---|---|
| Kontaktdaten → E-Mail-Adresse | ja | nein | App-Funktionalität (Konto, Login; bei Apple-Login ggf. Relay-Adresse) |
| Kontaktdaten → Name | ja | nein | App-Funktionalität (optionaler Anzeigename) |
| Nutzerinhalte → Themen, Fragen, gespeicherte und bewusst geteilte Antworten, Einstellungen | ja | nein | App-Funktionalität |
| Kennungen → Nutzer-ID | ja | nein | App-Funktionalität (Kontozuordnung) |
| Kennungen → Geräte-ID / Push-Token | ja | nein | App-Funktionalität (nur bei erteilter Push-Erlaubnis) |

Kein Tracking über Apps/Websites Dritter, kein Werbe-SDK, kein Analytics.
KI-Anfragen gehen an einen Auftragsverarbeiter (OpenRouter) — in der
Datenschutzerklärung benannt, In-App-Hinweis vor der ersten Frage.

## App-Review-Informationen

**Demo-Zugang** (muss auf Prod existieren, dauerhaft gültig, mit angelegten
Themen und etwas Verlauf — sonst wirkt die App leer):

```
appreview@ratslotse.de · Passwort steht in App Store Connect (App-Review-Informationen) und im Passwortmanager
```

**Notizen für die Prüfer:**

```
Ratslotse macht die öffentlich zugänglichen Beschlüsse des Stadtrats Oldenburg durchsuchbar und verständlich. Die Daten stammen aus dem amtlichen Ratsinformationssystem der Stadt (buergerinfo.oldenburg.de).

Unabhängigkeit: Ratslotse ist ein privates Bürgerprojekt und wird nicht von der Stadt Oldenburg herausgegeben oder beauftragt. Der Hinweis steht in der Store-Beschreibung, im Impressum der App sowie auf Anmelde- und Registrierungsbildschirm.

KI-Funktion: Die Frage-Funktion antwortet ausschließlich auf Grundlage der importierten Ratsdokumente und nennt zu jeder Aussage die Quelle. Kein offener Chat, kein Zugriff auf das freie Web, keine Bildgenerierung.

Rechte an den Inhalten: Die gezeigten Dokumente sind amtliche Werke der Stadt Oldenburg (§ 5 UrhG) und damit gemeinfrei; sie sind öffentlich unter buergerinfo.oldenburg.de abrufbar. Ratslotse gibt sie aufbereitet wieder, nennt zu jeder Aussage die Quelle und verlinkt jedes Originaldokument. Es werden keine kostenpflichtigen oder zugangsbeschränkten Inhalte verwendet.

Personenbezogene Daten Dritter: In den amtlichen Protokollen kommen Ratsmitglieder in ihrer öffentlichen Funktion vor (Fraktion, Ämter, Anwesenheit, sinngemäße Wortbeiträge). Es werden keine privaten Daten und keine weiteren Quellen zusammengeführt. Grundlage, Umfang und ein Widerspruchsweg stehen unter ratslotse.de/datenschutz („Daten von Ratsmitgliedern und Verwaltung").

Native Funktionen: Push-Benachrichtigungen zu abonnierten Themen und Gremien (APNs, ohne Firebase), Offline-Zugriff auf zuletzt gelesene Beschlüsse, Teilen über das System-Menü, Termin-Export ins Share-Sheet, Universal Links, Anmeldung mit Apple.

Administrationsbereich: Konten mit der Rolle „admin" sehen zusätzlich einen Verwaltungsbereich (Statistik, Prompts, Moderation). Der Demo-Zugang hat diese Rolle nicht — der Bereich ist kein verstecktes Feature, sondern die Betriebsoberfläche des Betreibers.

Keine Käufe und keine Werbung. Bewusst geteilte KI-Antworten sind öffentliche,
nicht gelistete Links: Jeder Link hat einen Meldeweg ohne Anmeldung; Admins
können den Link entfernen und das zugehörige Konto sperren. Es gibt keinen
öffentlichen Feed, keine Suche nach Shares und keine Kommunikation zwischen
Nutzer*innen.
Konto löschen: Konto → Konto löschen (löscht Konto, Themen und Push-Token).
```

## Screenshots

Sechs Motive, Reihenfolge aus dem Canvas (die ersten drei entscheiden):
Frag den Rat · Suche · Benachrichtigungen · Analyse · Quiz · Stadtkarte.

Der gebrandete Balken mit der Headline ist Store-Material und darf gestaltet
sein — **der Screen darunter muss eine echte Aufnahme der App sein**
(Guideline 2.3.3: keine Titelbilder, kein Login-Screen; Apple prüft
Screenshots gegen die App). Entwürfe aus dem Canvas als Vorlage nehmen, den
Inhalt aber im Simulator eines aktuellen großen iPhone aufnehmen, mit echten,
veröffentlichten Beschlüssen und ohne Namen von Privatpersonen. Statusleiste
überall 9:41. Die geforderten Pixelmaße unmittelbar vor dem Hochladen in App
Store Connect ablesen — sie ändern sich mit jeder iPhone-Generation.

## Was außerhalb dieser Datei zu erledigen ist

- **DSA-Trader-Status** deklarieren (ohne Angabe keine Einreichung in der EU) —
  nicht-kommerzielles Privatprojekt ⇒ „Non-Trader" plausibel.
- **App-Datenschutz-Formular** ausfüllen (Werte oben) — die API bietet dafür
  keinen Weg, das geht nur in der Oberfläche.
- **Marke „Ratslotse"** recherchieren, **Rückmeldung der Stadt** zur Datennutzung
  einholen (beides aus Abschnitt ⑨ des Canvas). Für die Rechte-Erklärung
  gegenüber Apple ist die Rückmeldung nicht nötig — amtliche Werke sind nach
  § 5 UrhG gemeinfrei; sie deckt das Datenbankherstellerrecht (§ 87a ff. UrhG)
  und die gute Nachbarschaft ab.
- **Fehler-Überwachung im Frontend** — gibt es noch nicht; ohne sie kommen
  Abstürze als Ein-Stern-Bewertung.

## Demo-Konto pflegen

`appreview@ratslotse.de` (Konto-ID 19, Rolle `user`, seit 14.08.2026) trägt drei
Themen und drei gespeicherte Gespräche, damit die App im Review nicht leer
wirkt. **Nicht löschen** — Apple prüft bei jedem Update erneut. Wenn der Bestand
altert, eine Frage neu stellen und ein Thema ergänzen; das Passwort steht in den
App-Review-Informationen.
