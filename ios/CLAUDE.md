# Regeln für `ios/`

Native SwiftUI-App. Sie ist der Client, den die Testsuite des Backends **nicht**
erreicht — hier fällt eine Schnittstellenänderung erst im Simulator auf, oder
gar erst im Store. Siehe auch [`README.md`](README.md) und
[`../CLAUDE.md`](../CLAUDE.md).

## Ein Feldname ändert sich hier NICHT von selbst

Web und Backend teilen sich einen erzeugten Typ; die App tippt ihre `struct`s
und `CodingKeys` von Hand. Eine Umbenennung im Backend erreicht sie deshalb auf
keinem Weg — sie liest weiter den alten Namen, bekommt nichts und setzt ihre
Vorgabe ein. Genau so stand nach #826 unter jedem Thema eine 0, monatelang, auf
Prod.

Vor **jeder** Änderung an einem Modell und nach jedem Merge aus `dev`:

```bash
python scripts/ios_vertrag.py
```

Das rechnet die Bindung aus der Aufrufstelle aus (Pfad und Zieltyp stehen in
derselben Zeile) und hält jede `struct` gegen das Schema, das sie decodieren
muss. Was dabei offen bleiben darf, steht mit Begründung in
`tests/test_ios_vertrag.py`; die Liste darf schrumpfen und nicht wachsen.

Drei Dinge, die dabei auffallen und im Simulator NICHT:

- ein Feld, das der Vertrag nicht kennt — die App liest ins Leere,
- ein nicht-optionales Feld, das der Vertrag weglassen darf — `JSONDecoder`
  wirft, die Seite bleibt leer statt falsch,
- ein Typ, der nicht passt (`Int` gegen einen String-Schlüssel) — ebenfalls ein
  Abbruch.

## Neue Datei heißt: neu generieren

Das Projekt entsteht aus `project.yml` per XcodeGen, **die `.xcodeproj` ist
trotzdem eingecheckt**, damit man ohne XcodeGen öffnen kann. Nach jeder neuen
Datei unter `RatslotseApp/` oder `Resources/` und nach jeder Änderung an
`project.yml`:

```bash
xcodegen generate --spec ios/project.yml
```

und das Ergebnis mitcommitten. Die `sources`-Einträge sind Verzeichnisse — wer
das vergisst, hat die Datei nur bei sich. **Die CI merkt es nicht**, sie
generiert vor dem Build selbst.

Dateien innerhalb der Pakete unter `Packages/` brauchen das nicht.

## Paketgrenzen

| Paket | Inhalt | Abhängigkeiten |
|---|---|---|
| `RatslotseAPI` | Client, Modelle, SSE, Keychain, Routing | keine, deshalb ohne Simulator testbar |
| `RatslotseDesign` | Tokens und Bausteine | keine |
| `RatslotseFeatures` | alle Screens, `AppModel` | beide |
| `RatslotseApp/` | Lebenszyklus, Push, Entitlements | — |

Kein SwiftUI in `RatslotseAPI`. Das ist der Grund, warum seine Tests in
Sekunden laufen.

## Die Modelle sind handgeschrieben — und das ist die Schwachstelle

`Models.swift` bildet Feldnamen pro Struct über `CodingKeys` ab; der Decoder
wandelt nichts automatisch um. Eine Umbenennung im Backend trifft also genau
die Structs, die den alten Namen führen, und je nach Struct auf zwei Arten:

- **Gehärtet** (`decodeIfPresent` mit Default): Das Feld wird still `nil`, die
  Oberfläche bleibt leer. Kein Fehler, keine Meldung.
- **Hart** (`decode`): Der Decode der **ganzen** Antwort kippt. Der Client
  ersetzt jeden Decode-Fehler durch „Die Antwort des Servers hat ein
  unerwartetes Format" — ohne zu sagen, welcher Schlüssel fehlte.

Deshalb gilt: **Wer im Backend ein Feld anfasst, fasst `Models.swift` mit an.**
Der Vertrag `api/openapi.json` ist die Referenz; die aufgezeichneten Antworten
unter `Packages/RatslotseAPI/Tests/RatslotseAPITests/Fixtures/` sind die Probe.

Ein Feld, das die App aktiv als `null` senden muss, gehört mit `encode` und
nicht `encodeIfPresent` geschrieben — sonst schaltet sich die Funktion
unbemerkt ab.

## Die CI läuft nur bei Änderungen unter `ios/`

Eine reine Backend-Änderung löst die iOS-Tests **nicht** aus. Wer eine
Schnittstelle ändert, prüft die App von Hand oder zieht die Fixtures nach.

## Vor einem Upload

`CURRENT_PROJECT_VERSION` in `project.yml` erhöhen **und neu generieren**.
Bundle-IDs kommen aus den xcconfig-Dateien, nicht aus dem Projekt.

`MARKETING_VERSION` dagegen fasst niemand von Hand an: Sie zieht der
Versionsschnitt mit (`scripts/changelog_schnitt.py x.y.z`), und
`tests/test_app_version.py` hält sie gegen die jüngste Version im Changelog —
in **beiden** Dateien, denn die eingecheckte `.xcodeproj` schleppt den Wert
mit. Sie stand am 04.09.2026 auf 2.0.0, während 2.1.0 draußen war; gemerkt
hätte es erst, wer eine Fehlermeldung zur falschen Fassung sucht.
