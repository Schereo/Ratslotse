"""Zuwendungen an die Stadt (council/spenden.py).

Die Fixtures sind gekürzte, aber wörtliche Auszüge echter Vorlagen (Stand
18.08.2026). Jede beweist eine Falle, die beim Vermessen der 218
Beschlusszeilen aufgefallen ist — die Vorlagen-Nummer steht jeweils dabei,
damit sich das im Bürgerinfo nachschlagen lässt.

Der Aufbau folgt ``tests/test_ausgabenreihe.py``.
"""

from council import herkunft, donations
from council.store import CouncilStore

# --- Fixtures: echte Vorlagen, gekürzt --------------------------------------

# 26/0207 — das heutige Layout: „Auswirkungen: a) Finanzen", Zerlegung in
# Mehrerträge und sachliche Zuwendungen. 421.316 + 14.625 = 435.941.
VORLAGE_NEU = """
Annahme von Zuwendungen durch den Rat
- Beschluss

Beschlussvorschlag:
Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von insgesamt
435.941 Euro gemäß der anliegenden Liste an.

Anlass:
Gemäß § 111 Absatz 8 NKomVG und § 26 KomHKVO sowie der Ratsentscheidung vom
22. Februar 2010 nach § 26 Absatz 2 KomHKVO entscheiden der Oberbürgermeister (bis
100 Euro), der Verwaltungsausschuss (von 100,01 Euro bis 2.000 Euro) und der Rat (ab
2.000,01 Euro) über die Annahme und Vermittlung von Zuwendungen.

Auswirkungen:
 a) Finanzen
Durch die Zuwendungen entstehen in den Teilhaushalten 04, 06 und 11 sowie im
Schulbudget und im Budget des EGH Mehrerträge in Höhe von insgesamt 421.316
Euro. Die Mehrerträge werden unterjährig eingesetzt und führen zu entsprechenden
Mehraufwendungen.

Die sachlichen Zuwendungen im Wert von 14.625 Euro wirken sich nicht auf den
Teilhaushalt 06 aus.
b) Klima
./.
"""

# 18/0002 — das ältere Layout: „Finanzielle Auswirkungen:". Dieselbe Rechnung
# unter anderem Namen. Genau daran ist eine frühere Messung gescheitert.
VORLAGE_ALT = """
Annahme von Zuwendungen durch den Rat
- Beschluss -

Beschlussvorschlag:

Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von insgesamt
140.664,24 EUR laut anliegender Liste an.

Begründung:

Eine Begründung für die Annahme der einzelnen Zuwendungen ist in der Anlage aufg e-
führt.

Finanzielle Auswirkungen:

Durch die Zuwendungen entstehen in den einzelnen Teilhaushalten zweckgebundene
Mehrerträge in Höhe von 118.349,24 EUR (siehe Anlage). Die Mehrerträge werden unter-
jährig eingesetzt und führen zu entsprechenden Mehraufwendungen.

Die Sachspenden im Wert von 22.315,00 EUR wirken sich nicht auf die Teilhaushalte aus.

In Vertretung
"""

# 19/0709 — „1.800,00 E UR": Der Textextrakt zerlegt das Währungswort.
VORLAGE_EUR_ZERLEGT = """
Annahme von Zuwendungen durch den Verwaltungsausschuss
Beschlussvorschlag:
Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von insgesamt
1.800,00 EUR laut anliegender Liste an.

Finanzielle Auswirkungen:
Durch die Zuwendungen entstehen im Schulbudget und im Teilhaushalt 11 zweckgebund e-
ne Mehrerträge in Höhe von 1.800,00 E UR. Die Mehrerträge werden unterjährig eingesetzt.
"""

# 19/0293 — „154 .472,86": Leerzeichen VOR dem Tausenderpunkt.
VORLAGE_ZAHL_ZERLEGT = """
Annahme von Zuwendungen durch den Rat
Beschlussvorschlag:
Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von insgesamt
154.472,86 EUR laut anliegender Liste an.

Finanzielle Auswirkungen:
Durch die Zuwendungen entstehen zweckgebundene Mehrerträge in Höhe von 154 .472,86 EUR.
"""

# 18/0587 — der Rat hat die Liste GEÄNDERT: „(ohne lfd. Nr. 2)".
VORLAGE_GEAENDERT = """
Annahme von Zuwendungen durch den Verwaltungsausschuss
Beschlussvorschlag:
Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von insgesamt
22.500,00 EUR laut anliegender Liste an.

Finanzielle Auswirkungen:
Durch die Zuwendungen entstehen zweckgebundene Mehrerträge in Höhe von 22.500,00 EUR.
"""

# Eine Vorlage OHNE Zweitstelle: der Finanz-Abschnitt fehlt ganz.
VORLAGE_OHNE_ZWEITSTELLE = """
Annahme von Zuwendungen durch den Rat
Beschlussvorschlag:
Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von insgesamt
7.500,00 EUR laut anliegender Liste an.

Begründung:
Eine Begründung ist in der Anlage aufgeführt.
"""


def row(nr, raw, official_text, *, title=None, outcome="accepted",
          sitzung="2024-03-11", gremiensitzung="Rat", document_id=4711):
    return {"template_number": nr, "title": title or "Annahme von Zuwendungen durch den Rat",
            "official_text": official_text, "outcome": outcome, "session_date": sitzung,
            "gremiensitzung": gremiensitzung, "raw_text": raw,
            "document_id": document_id,
            "dokument_url": f"https://buergerinfo.example.org/getfile.php?id={document_id}"}


# --- Die Probe hält ---------------------------------------------------------

def test_die_zerlegung_traegt_den_betrag():
    """26/0207: 421.316 + 14.625 = 435.941 — die Zweitstelle als Rechnung."""
    erg = donations.lies([row(
        "26/0207", VORLAGE_NEU,
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "insgesamt 435.941 Euro gemäß der anliegenden Liste an.")])
    assert len(erg["vorlagen"]) == 1
    v = erg["vorlagen"][0]
    assert v["amount"] == 435_941
    assert v["second_mention"] == "split"
    assert v["layout"] == "new"
    assert donations.ZWEITSTELLE in v["probes"]
    assert donations.PROTOKOLLABGLEICH in v["probes"]


def test_das_aeltere_layout_traegt_dieselbe_probe():
    """18/0002: „Finanzielle Auswirkungen" statt „Auswirkungen a) Finanzen".

    Eine frühere Messung hielt 88 Vorlagen für „ohne Struktur" — die Struktur
    war da und hieß nur anders. Ohne diesen Test käme das zurück."""
    erg = donations.lies([row(
        "18/0002", VORLAGE_ALT,
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "insgesamt 140.664,24 EUR laut anliegender Liste an.")])
    v = erg["vorlagen"][0]
    assert v["amount"] == 140_664.24
    assert v["layout"] == "old"
    assert v["second_mention"] == "split"


def test_die_identische_zweitstelle_zaehlt_auch():
    """19/0709: Der Abschnitt nennt denselben Betrag, ohne ihn zu zerlegen."""
    erg = donations.lies([row(
        "19/0709", VORLAGE_EUR_ZERLEGT,
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "insgesamt 1.800,00 EUR laut anliegender Liste an.",
        title="Annahme von Zuwendungen durch den Verwaltungsausschuss")])
    v = erg["vorlagen"][0]
    assert v["amount"] == 1_800
    assert v["second_mention"] == "identical"
    assert v["committee"] == "Verwaltungsausschuss"


# --- Die Probe hält NICHT ---------------------------------------------------

def test_eine_vorlage_ohne_zweitstelle_kommt_nicht_rein():
    """Der Betrag steht nur einmal — dann fehlt die Zeile, mit Begründung."""
    erg = donations.lies([row(
        "24/9999", VORLAGE_OHNE_ZWEITSTELLE,
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "insgesamt 7.500,00 EUR laut anliegender Liste an.")])
    assert erg["vorlagen"] == []
    assert len(erg["verworfen"]) == 1
    reason = erg["verworfen"][0]["reason"]
    assert "finanziellen" in reason and reason.endswith(".")


def test_ein_geaenderter_beschluss_kommt_nicht_ungeprueft_rein():
    """18/0587: Vorschlag 22.500, beschlossen 2.500 „(ohne lfd. Nr. 2)".

    Der Rat hat eine Position gestrichen. Die Vorlage belegt damit den
    beschlossenen Betrag nicht mehr — die Zeile fällt, statt 20.000 Euro zu
    buchen, die nie angenommen wurden."""
    erg = donations.lies([row(
        "18/0587", VORLAGE_GEAENDERT,
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "insgesamt 2.500,00 EUR laut anliegender Liste an (ohne lfd. Nr. 2).",
        title="Annahme von Zuwendungen durch den Verwaltungsausschuss")])
    assert erg["vorlagen"] == []
    assert "22.500,00" in erg["verworfen"][0]["reason"]
    assert "2.500,00" in erg["verworfen"][0]["reason"]


def test_der_grund_traegt_die_zahlen_der_zeile_und_nicht_die_deutung():
    """Was für die ganze Kategorie gilt, steht nicht in jeder einzelnen Zeile.

    Bis 24.08.2026 hängte dieser Grund seine Deutung an — „entweder hat der
    Rat die Liste geändert oder eines der beiden Dokumente trägt einen
    Zahlendreher". Der Satz stimmt, gilt aber für jeden Fall dieser Art und
    stand deshalb auf ``/haushalt/einnahmen`` in vier von sechs Lücken-Feldern
    wörtlich untereinander. Er steht jetzt einmal über der Liste. Wer ihn
    hierher zurückholt, löscht diesen Test — dann ist es eine Entscheidung,
    kein Versehen."""
    erg = donations.lies([row(
        "18/0587", VORLAGE_GEAENDERT,
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "insgesamt 2.500,00 EUR laut anliegender Liste an (ohne lfd. Nr. 2).",
        title="Annahme von Zuwendungen durch den Verwaltungsausschuss")])
    reason = erg["verworfen"][0]["reason"]
    assert "Zahlendreher" not in reason and "geändert" not in reason
    assert len(reason) < 120, reason


def test_ein_abgesetzter_punkt_ist_keine_einnahme():
    """21/0694: „Der Tagesordnungspunkt wurde abgesetzt.“"""
    erg = donations.lies([row(
        "21/0694", None, "Der Tagesordnungspunkt wurde abgesetzt.",
        outcome="postponed")])
    assert erg["vorlagen"] == []
    assert "nicht beschlossen" in erg["verworfen"][0]["reason"]


# --- Die drei Reparaturen am Textextrakt ------------------------------------

def test_das_zerlegte_waehrungswort_wird_gelesen():
    """„1.800,00 E UR" — ein Leerzeichen im Wort, nicht zwischen zwei Zahlen."""
    assert donations.betraege("Mehrerträge in Höhe von 1.800,00 E UR.") == [1_800.0]
    assert donations.betraege("60,00 E UR") == [60.0]


def test_die_zerlegte_zahl_wird_gelesen_die_satzgrenze_nicht():
    """„154 .472,86" ist eine Zahl, „Teilhaushalt 06. 500,00 Euro" sind zwei.

    Deshalb steht das Leerzeichen NUR vor dem Tausenderpunkt im Muster: Ein
    Satzende trägt seinen Punkt direkt am Wort und das Leerzeichen dahinter."""
    assert donations.betraege("Mehrerträge in Höhe von 154 .472,86 EUR") == [154_472.86]
    assert donations.betraege("Teilhaushalt 06. 500,00 Euro") == [500.0]


def test_die_kurzform_mit_strich_wird_gelesen():
    """„6.000,- EUR" ist die Protokoll-Kurzform für 6.000,00."""
    assert donations.betraege("in Höhe von insgesamt 6.000,- EUR") == [6_000.0]


# --- Zuständigkeit ----------------------------------------------------------

def test_die_schwellen_sagen_wer_entscheidet():
    assert donations.zustaendig(50) == "Oberbürgermeister"
    assert donations.zustaendig(100) == "Oberbürgermeister"
    assert donations.zustaendig(100.01) == "Verwaltungsausschuss"
    assert donations.zustaendig(2_000) == "Verwaltungsausschuss"
    assert donations.zustaendig(2_000.01) == "Rat"
    assert donations.zustaendig(435_941) == "Rat"


def test_die_summe_einer_va_vorlage_darf_ueber_der_schwelle_liegen():
    """22/0020: 2.746,20 Euro, beschlossen vom Verwaltungsausschuss.

    Maßgeblich ist die EINZELNE Zuwendung, nicht die Summe der Liste. Wer die
    Summe gegen 2.000 prüfte, prüfte etwas, das die Regel nicht behauptet —
    dieser Test hält fest, dass wir das nicht tun."""
    erg = donations.lies([row(
        "22/0020",
        "Beschlussvorschlag:\nDie Stadt Oldenburg nimmt die angebotenen Zuwendungen "
        "in Höhe von insgesamt 2.746,20 Euro laut anliegender Liste an.\n\n"
        "Finanzielle Auswirkungen:\nMehrerträge in Höhe von 2.000,00 Euro sowie im "
        "Schulbudget 500,00 Euro. Die Sachspenden im Wert von 246,20 Euro wirken "
        "sich nicht aus.",
        "Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe von "
        "insgesamt 2.746,20 Euro laut anliegender Liste an.",
        title="Annahme von Zuwendungen durch den Verwaltungsausschuss")])
    v = erg["vorlagen"][0]
    assert v["amount"] == 2_746.20
    assert v["committee"] == "Verwaltungsausschuss"


# --- Aufbereitung -----------------------------------------------------------

def test_je_vorlage_bleibt_eine_zeile():
    """Dieselbe Liste läuft durch Fachausschuss UND Rat — einmal zählen."""
    official_text = ("Die Stadt Oldenburg nimmt die angebotenen Zuwendungen in Höhe "
                 "von insgesamt 435.941 Euro gemäß der anliegenden Liste an.")
    erg = donations.lies([
        row("26/0207", VORLAGE_NEU, official_text, sitzung="2026-04-08",
              gremiensitzung="Ausschuss für Finanzen und Beteiligungen"),
        row("26/0207", VORLAGE_NEU, official_text, sitzung="2026-04-13",
              gremiensitzung="Rat"),
    ])
    assert len(erg["vorlagen"]) == 1
    # Gezählt wird die Sitzung, in der entschieden wurde.
    assert erg["vorlagen"][0]["session_date"] == "2026-04-13"
    assert [j["amount"] for j in erg["years"]] == [435_941]
    assert erg["years"][0]["vorlagen"] == 1


def test_die_jahresreihe_trennt_rat_und_verwaltungsausschuss():
    erg = donations.lies([
        row("24/0001", VORLAGE_NEU,
              "Zuwendungen in Höhe von insgesamt 435.941 Euro", sitzung="2024-02-05"),
        row("24/0002", VORLAGE_EUR_ZERLEGT,
              "Zuwendungen in Höhe von insgesamt 1.800,00 EUR", sitzung="2024-03-04",
              title="Annahme von Zuwendungen durch den Verwaltungsausschuss"),
    ])
    assert erg["years"] == [{"year": 2024, "amount": 437_741.0, "vorlagen": 2,
                             "rat": 1, "verwaltungsausschuss": 1}]


def test_fremde_beschluesse_werden_nicht_angefasst():
    """`erkenne()` ist die einzige Stelle, die entscheidet, was hierher gehört."""
    assert donations.erkenne("Annahme von Zuwendungen durch den Rat")
    assert donations.erkenne("Annahme einer Zuwendung in Höhe von 9.000 Euro durch den Rat")
    assert not donations.erkenne("Richtlinien der Stadt Oldenburg für die Gewährung "
                               "von Zuwendungen")
    assert not donations.erkenne("Klimaoasen in Oldenburg - Beschluss über Zuwendung")
    assert not donations.erkenne(None)


def test_der_probennachweis_nennt_zahlen():
    erg = donations.lies([row(
        "26/0207", VORLAGE_NEU,
        "Zuwendungen in Höhe von insgesamt 435.941 Euro")])
    nachweis = donations.probennachweis(erg)
    assert "1" in nachweis and "Zweitstelle" in nachweis
    for wertung in ("gut", "zuverlässig", "korrekt", "sauber", "sorgfältig"):
        assert wertung not in nachweis.lower()


def test_euro_schreibt_deutsch():
    assert donations.euro(1_234_567.8) == "1.234.567,80"
    assert donations.euro(60) == "60,00"


# --- Der Weg in den Bestand -------------------------------------------------

def test_speichern_und_lesen(tmp_path):
    erg = donations.lies([row(
        "26/0207", VORLAGE_NEU,
        "Zuwendungen in Höhe von insgesamt 435.941 Euro")])
    lauf = herkunft.Herkunft(
        kind="ris", url="https://buergerinfo.example.org/vo040.asp",
        probe=[donations.ZWEITSTELLE], probe_result=donations.probennachweis(erg))
    for v in erg["vorlagen"]:
        v["herkunft"] = herkunft.Herkunft(
            kind="ris", document_id=v["document_id"], probe=v["probes"],
            citation=donations.FUNDSTELLE, probe_result="Zerlegung geht auf")

    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        assert store.save_spenden(erg["vorlagen"], erg["verworfen"], lauf) == 1
        zurueck = store.get_spenden()
        assert len(zurueck) == 1
        assert zurueck[0]["amount"] == 435_941
        assert zurueck[0]["probes"] == [donations.ZWEITSTELLE, donations.PROTOKOLLABGLEICH]
        assert all(z["herkunft_id"] for z in zurueck)
        assert store.spenden_jahre() == [2024]
        assert "council_spenden" not in store.herkunft_luecken()
    finally:
        store.close()


def test_verworfene_zeilen_kommen_mit_ihrem_grund_in_den_bestand(tmp_path):
    """Eine Lücke ist eine Auskunft — sie steht in der Datenbank, nicht nur im Log."""
    erg = donations.lies([row(
        "18/0587", VORLAGE_GEAENDERT,
        "Zuwendungen in Höhe von insgesamt 2.500,00 EUR laut anliegender Liste an "
        "(ohne lfd. Nr. 2).",
        title="Annahme von Zuwendungen durch den Verwaltungsausschuss")])
    lauf = herkunft.Herkunft(kind="ris", url="https://buergerinfo.example.org/vo040.asp",
                             probe=[donations.ZWEITSTELLE], probe_result="0 Vorlagen")
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_spenden(erg["vorlagen"], erg["verworfen"], lauf)
        ohne = store.get_spenden_verworfen()
        assert len(ohne) == 1
        assert ohne[0]["template_number"] == "18/0587"
        assert "22.500,00" in ohne[0]["reason"]
        assert ohne[0]["herkunft_id"]
    finally:
        store.close()


def test_eine_teillieferung_raeumt_den_bestand_nicht_ab(tmp_path):
    """`INSERT OR REPLACE`, kein `DELETE FROM` — sonst kostet ein halber Lauf
    die halbe Reihe."""
    lauf = herkunft.Herkunft(kind="ris", url="https://buergerinfo.example.org/vo040.asp",
                             probe=[donations.ZWEITSTELLE], probe_result="Probe")
    a = donations.lies([row("24/0001", VORLAGE_NEU,
                            "Zuwendungen in Höhe von insgesamt 435.941 Euro",
                            sitzung="2024-02-05")])
    b = donations.lies([row("25/0001", VORLAGE_ALT,
                            "Zuwendungen in Höhe von insgesamt 140.664,24 EUR",
                            sitzung="2025-02-05")])
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        store.save_spenden(a["vorlagen"], [], lauf)
        store.save_spenden(b["vorlagen"], [], lauf)
        assert {z["template_number"] for z in store.get_spenden()} == {"24/0001", "25/0001"}
    finally:
        store.close()


def test_die_tabelle_fuehrt_keine_gebenden(tmp_path):
    """Die härteste Zusicherung dieser Schicht.

    Die Namen der Spenderinnen und Spender stehen nur in der Anlage
    „Zuwendungsliste", die wir nicht einlesen. Was die Tabelle nicht führen
    kann, kann die API nicht liefern und das Frontend nicht versehentlich
    zeigen. Wer hier eine Spalte ergänzt, muss diesen Test löschen — und dann
    ist es eine Entscheidung und kein Versehen."""
    store = CouncilStore(tmp_path / "council.sqlite")
    try:
        spalten = {r[1].lower() for r in
                   store._conn.execute("PRAGMA table_info(council_spenden)")}
    finally:
        store.close()
    for verboten in ("spender", "spenderin", "geber", "name", "zuwendungsgeber",
                     "person", "firma", "liste"):
        assert verboten not in spalten


def test_die_tabellen_sind_als_herkunftstraeger_angemeldet():
    assert "council_spenden" in herkunft.HERKUNFT_TABELLEN
    assert "council_spenden_verworfen" in herkunft.HERKUNFT_TABELLEN


def test_die_proben_sind_fuer_leserinnen_erklaert():
    for name in (donations.ZWEITSTELLE, donations.PROTOKOLLABGLEICH):
        assert name in herkunft.PROBEN
        assert herkunft.PROBEN[name].endswith(".")
    assert herkunft.probe_texte(
        f"{donations.ZWEITSTELLE},{donations.PROTOKOLLABGLEICH}") != []
