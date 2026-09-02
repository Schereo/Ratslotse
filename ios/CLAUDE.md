# Regeln für `ios/`

Native SwiftUI-App. Sie ist der Client, den die Testsuite des Backends **nicht**
erreicht — hier fällt eine Schnittstellenänderung erst im Simulator auf, oder
gar erst im Store. Siehe auch [`README.md`](README.md) und
[`../CLAUDE.md`](../CLAUDE.md).

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
