"""Der Kritiker, geprüft an den echten Fehlern des ersten Produktionslaufs.

Am 30.08.2026 gingen 22 Kartentexte für die Woche 31.8.–6.9. in den ersten
Lauf. Drei mussten von Hand korrigiert werden, zwei davon frei erfunden. Die
Fälle stehen hier als Testdaten — was einmal durchgerutscht ist, soll nie
wieder durchrutschen.
"""
from __future__ import annotations

from council import kritiker


# Auszug aus der echten Windenergie-Vorlage (26/0403), auf das Wesentliche
# gekürzt.
QUELLE_WIND = (
    "Sachverhalt: Die Stadt Oldenburg muss die Vorgaben des Niedersächsischen "
    "Windenergieflächenbedarfsgesetzes (NWindG) von 0,66 Prozent (69 Hektar) bis zum "
    "31. Dezember 2027 und von 0,86 Prozent (89 Hektar) bis zum 31. Dezember 2032 "
    "erfüllen. Nach Auswertung der Stellungnahmen wurde die Sonderbaufläche "
    "Windenergie von 105,05 Hektar auf 91,84 Hektar reduziert."
)


def test_erfundene_zahl_faellt_durch():
    """„94 Hektar" stand am 30.08. auf der Karte. In der Vorlage stehen
    105,05 / 91,84 / 69 / 89 — die 94 gibt es nirgends."""
    maengel = kritiker.pruefe(
        "Beantragt ist der Plan, der bis 2032 Flächen von total 94 Hektar ausweist.",
        QUELLE_WIND)
    assert any("94" in m for m in maengel), maengel


def test_zahlen_aus_der_quelle_kommen_durch():
    """Der korrigierte Satz muss anstandslos durchgehen — ein Wächter, der
    auch bei richtigen Texten anschlägt, wird abgeschaltet."""
    assert kritiker.pruefe(
        "Zur Abstimmung steht der Entwurf des Teilflächennutzungsplans Windenergie "
        "mit 91,84 Hektar Sonderbaufläche. Gesetzlich gefordert sind 69 Hektar bis "
        "Ende 2027 und 89 Hektar bis 2032.", QUELLE_WIND) == []


def test_grosse_betraege_in_allen_schreibweisen():
    """Die Vorlage schreibt „13.500.000,00 Euro", die Karte „13,5 Millionen"
    — oder umgekehrt. Beides ist dieselbe Zahl."""
    quelle = "Bürgschaft für ein Darlehen in Höhe von 13.500.000,00 Euro."
    assert kritiker.pruefe("Beantragt ist eine Bürgschaft über 13.500.000 Euro.", quelle) == []
    assert kritiker.pruefe("Beantragt ist eine Bürgschaft über 13,5 Millionen Euro.", quelle) == []
    # Eine andere Zahl bleibt eine andere Zahl.
    assert kritiker.pruefe("Beantragt ist eine Bürgschaft über 15,5 Millionen Euro.", quelle)


def test_ohne_vorlage_faellt_jede_angabe_durch():
    """Der P+R-Punkt vom 31.08. hatte gar keine Vorlage — das Modell sah nur
    den Titel und schrieb „fünf Standorte". Zahlwörter fängt erst der
    LLM-Kritiker; die Ziffer fängt schon die deterministische Prüfung."""
    nur_titel = ("Tagesordnungspunkt: Umsetzung Aufwertung und Bewerbung von "
                 "P + R Standorten (SPD-Fraktion vom 10.06.2026)")
    assert kritiker.pruefe("Beantragt ist die Aufwertung von 5 P+R-Standorten.", nur_titel)


def test_wertungen_und_vorweggenommene_ergebnisse():
    """Was der Prompt verbietet, prüft der Kritiker nach: Ein Prompt ist eine
    Bitte, das hier ist eine Prüfung."""
    quelle = "Bürgschaft über 13.500.000 Euro für das Klinikum."
    assert any("wertet" in m for m in kritiker.pruefe(
        "Die Bürgschaft trägt ein hohes Risiko für die Stadt.", quelle))
    assert any("Ergebnis" in m for m in kritiker.pruefe(
        "Der Rat beschließt eine Bürgschaft über 13.500.000 Euro.", quelle))
    assert any("wichtig" in m.lower() for m in kritiker.pruefe(
        "Eine wichtige Entscheidung steht an.", quelle))


def test_aktenzeichen_und_laenge():
    quelle = "Bericht der Verwaltung zur Grundsteuer C."
    assert any("Aktenzeichen" in m for m in kritiker.pruefe(
        "Vorgestellt wird ein Bericht der Verwaltung [26/0666].", quelle))
    assert any("zu lang" in m for m in kritiker.pruefe("Beantragt ist " + "x" * 300, quelle))


def test_jahreszahlen_brauchen_keinen_beleg():
    """Sonst schlüge die Prüfung bei jedem „bis 2032" an, ohne je einen
    echten Fehler zu fangen."""
    assert kritiker.pruefe("Geplant ist die Umsetzung bis 2032.", "Ein Vorhaben.") == []
    assert kritiker.pruefe("Der 1. Bauabschnitt beginnt.", "Ein Vorhaben.") == []


def test_leerer_text_faellt_durch():
    assert kritiker.pruefe("   ", "egal") == ["leer"]


def test_llm_kritiker_verwirft_was_nicht_dasteht(monkeypatch):
    """Die „Baugruppe" vom 30.08.: In der Vorlage stehen „Eigentümer
    beziehungsweise die Antragsteller". Keine Zahl — das fängt erst der
    zweite Blick."""
    class _Antwort:
        def __init__(self, inhalt):
            self.choices = [type("C", (), {"message": type("M", (), {"content": inhalt})()})()]

    monkeypatch.setattr(kritiker.prompts, "get", lambda *a, **k: "system")
    monkeypatch.setattr(kritiker.prompts, "render", lambda *a, **k: "user")
    monkeypatch.setattr(kritiker.llm, "chat_complete", lambda **kw: _Antwort(
        '{"covered": false, "reason": "Von einer Baugruppe steht nichts in der Vorlage."}'))

    gedeckt, reason = kritiker.pruefe_llm("Die Kosten trägt die Baugruppe.", "Eigentümer …")
    assert not gedeckt
    assert "Baugruppe" in reason


def test_ausfall_des_kritikers_laesst_durch(monkeypatch):
    """Ein Netzfehler darf nicht die halbe Wochenvorschau leeren — der Text
    hat die deterministische Prüfung ja bestanden."""
    def _kaputt(**kw):
        raise RuntimeError("Netz weg")

    monkeypatch.setattr(kritiker.prompts, "get", lambda *a, **k: "system")
    monkeypatch.setattr(kritiker.prompts, "render", lambda *a, **k: "user")
    monkeypatch.setattr(kritiker.llm, "chat_complete", _kaputt)
    assert kritiker.pruefe_llm("Ein Satz.", "Eine Quelle.") == (True, "")


def test_verworfener_text_wird_nicht_gespeichert(monkeypatch):
    """Der ganze Weg: Was der Kritiker verwirft, kommt nicht zurück — der
    Bot fällt dann auf die Kurzfassung zurück."""
    from council import social_text

    class _Antwort:
        def __init__(self, inhalt):
            self.choices = [type("C", (), {"message": type("M", (), {"content": inhalt})()})()]

    monkeypatch.setattr(social_text.prompts, "get", lambda *a, **k: "system")
    monkeypatch.setattr(social_text.prompts, "render", lambda *a, **k: "user")
    monkeypatch.setattr(social_text.llm, "chat_complete", lambda **kw: _Antwort(
        '{"text": "Beantragt ist ein Betrag von 94 Millionen Euro."}'))
    monkeypatch.setattr(kritiker, "pruefe_llm", lambda *a: (True, ""))

    punkt = {"committee": "Rat", "session_date": "2026-08-31",
             "title": "Ein Punkt", "raw_text": "Sachverhalt: Es geht um 13 Millionen Euro."}
    assert social_text.text_fuer(punkt, []) is None


def test_zahlwoerter_zaehlen_als_beleg():
    """Die Vorlage schreibt „innerhalb von zehn Jahren", die Karte „10
    Jahren". Sachlich dasselbe — ohne diese Brücke meldete der Kritiker
    einen Fehler, wo keiner ist (der einzige Fehlalarm auf 22 Texte im
    ersten Produktionslauf)."""
    quelle = ("das verlorengehende Kronenvolumen innerhalb eines Zeitraums von zehn "
              "Jahren durch Ersatzpflanzungen vollständig auszugleichen")
    assert kritiker.pruefe(
        "Beantragt ist, Verluste innerhalb von 10 Jahren durch Ersatzpflanzungen "
        "auszugleichen.", quelle) == []
    # Eine andere Zahl bleibt trotzdem eine andere.
    assert kritiker.pruefe("Beantragt ist ein Ausgleich in 14 Jahren.", quelle)
