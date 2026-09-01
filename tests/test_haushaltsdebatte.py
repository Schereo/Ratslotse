"""Der Streit ums Geld — Debatten-Zerlegung und ``CouncilStore.haushalt_streit``.

Die Fixtures sind keine erfundenen Kunststücke. Jede Eigenheit hier steht so
in den Oldenburger Ratsprotokollen und hat beim Bauen genau einmal etwas
kaputtgemacht:

- **Zwei Layouts.** Bis 2020 stehen die Reden ohne Leerzeile hintereinander,
  ab 2021 mit. Ein Parser, der auf Leerzeilen schneidet, verliert die frühen
  Jahrgänge komplett.
- **Der abgerissene Anfangsbuchstabe.** Die PDF-Extraktion setzt gelegentlich
  den ersten Buchstaben eines Absatzes auf eine eigene Zeile („R\\natsherr
  Prange …"). Betrifft 2020 und 2024 spürbar, andere Jahrgänge gar nicht —
  ohne Reparatur verlieren ausgerechnet zwei Jahrgänge ihre Reden.
- **Leerzeichen mitten im Namen** („Pi echotta", „P range") und vor dem
  Bindestrich („Niewerth -Baumann").
- **Namensvettern.** Kurt Bernhardt (Grüne) und Lidia Bernhardt (AfD) saßen
  gemeinsam im Rat. Nennt das Protokoll nur den Nachnamen, darf keine
  Fraktion behauptet werden.
- **Gruppe ≠ Fraktion.** „FDP/Volt" ist eine Gruppe; wer sie auf „FDP"
  zusammenzieht, macht Ratsherrn Lükermann (Volt) zum FDP-Mann.
- **Verfahren ist keine Rede.** „… die heute zur\\nAbstimmung vorgelegt
  würden" steht mitten in einer Rede — eine Abschneideregel, die auf das Wort
  „Abstimmung" am Zeilenanfang anspringt, kürzt genau die Fraktionen, deren
  Redner das Wort benutzen.
"""
from __future__ import annotations

import pytest

from council import haushaltsdebatte as hd
from council.scraper import AgendaItem, CouncilSession
from council.store import CouncilStore


# --------------------------------------------------------------------- Fixtures

@pytest.fixture
def store(tmp_path):
    s = CouncilStore(str(tmp_path / "council.sqlite"))
    yield s
    s.close()


ANWESEND = [
    {"name": "Kurt Bernhardt", "party": "Bündnis 90/Die Grünen", "role": "member"},
    {"name": "Lidia Bernhardt", "party": "AfD", "role": "member"},
    {"name": "Nicole Piechotta", "party": "SPD", "role": "member"},
    {"name": "Ulf Prange", "party": "SPD", "role": "member"},
    {"name": "Jens Lükermann", "party": "FDP/Volt", "role": "member"},
    {"name": "Thorsten van Ellen", "party": "Bündnis 90/Die Grünen", "role": "member"},
    {"name": "Dr. Esther Niewerth-Baumann", "party": "CDU", "role": "member"},
    {"name": "Dr. Sebastian Rohe", "party": "Bündnis 90/Die Grünen", "role": "member"},
    {"name": "Dr. Georg Rohe", "party": "FDP/Volt", "role": "member"},
    {"name": "Franz Norrenbrock", "party": "WFO-LKR", "role": "member"},
    {"name": "Vally Finke", "party": None, "role": "member"},
    {"name": "Tim Harms", "party": "Bündnis 90/Die Grünen", "role": "chair"},
    {"name": "Dr. Julia Figura", "party": "Verwaltung", "role": "administration"},
]


# ------------------------------------------------------------------ Textpflege

def test_seitenfuss_und_silbentrennung():
    roh = "Die Auszah-\nlung der Förder-\nmittel und die Haushalts-\nMehrheit \n  Seite: 8/23 \nstehen fest."
    sauber = hd.saeubern(roh)
    assert "Auszahlung" in sauber
    assert "Fördermittel" in sauber
    assert "Haushalts-Mehrheit" in sauber, "großer Folgebuchstabe = echtes Kompositum"
    assert "Seite:" not in sauber


def test_abgerissener_anfangsbuchstabe():
    """„R\\natsherr Prange …" ist ein Extraktionsartefakt, kein Zeilenumbruch."""
    assert "Ratsherr Prange" in hd.saeubern("R\natsherr Prange verweist auf die Lage.")
    # Nur der abgetrennte Buchstabe ALLEIN auf seiner Zeile wird zusammengezogen.
    # „Bereich B\nund die Folgen" bliebe sonst als „Bund" stehen.
    assert "B\nund" in hd.saeubern("Der Bereich B\nund die Folgen")


def test_bindestrich_mit_leerzeichen():
    assert "Niewerth-Baumann" in hd.saeubern("Ratsfrau Niewerth -Baumann erklärt")


# ---------------------------------------------------------------- TOP-Abschnitt

PROTOKOLL = """zu 5 Einwohnerfragestunde
Frau Vosteen stellt eine Frage zum Haushalt.

zu 6 Haushalt 2026
-Beschluss
Vorlage: 25/0667

Oberbürgermeister Krogmann bedankt sich bei den Fraktionen und betont, dass es
sich um einen Not-Haushalt handle, der die Handlungsfähigkeit sichere. Das
Gesamtvolumen betrage 880 Millionen Euro.

Ratsfrau Pi echotta nimmt Stellung im Namen der SPD-Fraktion. Die Änderungen,
die heute zur
Abstimmung vorgelegt würden, seien in den Beratungen entstanden. Sie dankt den
Kolleginnen und Kollegen für die vertrauensvolle Zusammenarbeit im Ausschuss.

Ratsherr Bernhardt hält dagegen, dass der Entwurf die Klimaziele verfehle und
mehr Mittel für den Radverkehr nötig seien, damit die Stadt ihre eigenen
Beschlüsse auch einhalten könne. Er verweist auf den Klimaschutzplan und
bittet die Verwaltung um eine belastbare Aufstellung der Folgekosten.

zu 6.5 Haushaltssatzung und Haushaltsplan 2026
Abstimmung über Änderungsliste der CDU-Fraktion
- mehrheitlich abgelehnt -
"""


def test_abschnitt_bis_unterpunkt():
    voll = hd.top_abschnitt(PROTOKOLL, "6")
    debatte = hd.top_abschnitt(PROTOKOLL, "6", bis_unterpunkt=True)
    assert "Einwohnerfragestunde" not in voll, "der vorige TOP gehört nicht dazu"
    assert "Änderungsliste der CDU-Fraktion" in voll
    assert "Änderungsliste der CDU-Fraktion" not in debatte, (
        "die Abstimmungen stehen im Unterpunkt, nicht in der Debatte"
    )
    assert "Krogmann" in debatte


def test_unbekannter_top_bleibt_leer():
    assert hd.top_abschnitt(PROTOKOLL, "99") == ""


# ----------------------------------------------------------------- Wortbeiträge

def test_debatte_zerlegt_und_ordnet_zu():
    beitraege = hd.debatte(hd.top_abschnitt(PROTOKOLL, "6", bis_unterpunkt=True), ANWESEND)
    # „Krogmann" steht nicht in der Anwesenheitsliste dieses Fixtures und
    # bleibt deshalb so stehen, wie das Protokoll ihn schreibt.
    assert [b.name for b in beitraege] == ["Krogmann", "Nicole Piechotta", "Bernhardt"]
    ob, spd, gruen = beitraege
    assert ob.role == "administration" and ob.fraktion is None
    assert spd.role == "council" and spd.fraktion == "SPD"
    # Namensvettern: ohne Vornamen im Protokoll KEINE Fraktion behaupten.
    assert gruen.fraktion is None and gruen.fraktion_unklar is True


def test_verfahrenswort_kuerzt_die_rede_nicht():
    """„… die heute zur\\nAbstimmung vorgelegt würden" steht mitten im Satz."""
    spd = hd.debatte(hd.top_abschnitt(PROTOKOLL, "6", bis_unterpunkt=True), ANWESEND)[1]
    assert "vertrauensvolle Zusammenarbeit" in spd.text, (
        "die Rede darf nicht am Wort Abstimmung abgeschnitten werden"
    )


def test_leerzeichen_im_namen():
    """Das PDF schreibt „Pi echotta"; gemeint ist Ratsfrau Piechotta."""
    spd = hd.debatte(hd.top_abschnitt(PROTOKOLL, "6", bis_unterpunkt=True), ANWESEND)[1]
    assert spd.name == "Nicole Piechotta"


def test_namenspartikel():
    """„Ratsherr van Ellen" — im Nordwesten häufig, sonst unauffindbar."""
    text = ("Ratsherr van Ellen führt aus, dass seine Fraktion sich das Ziel gesetzt habe, "
            "die Stadt bis zum Jahr 2035 klimaneutral zu machen. Dafür brauche es "
            "verlässliche Mittel im Haushalt und einen Zeitplan, an dem sich die "
            "Verwaltung messen lassen könne.")
    (b,) = hd.debatte(text, ANWESEND)
    assert b.name == "Thorsten van Ellen"
    assert b.fraktion == "Grüne"


def test_vorname_loest_namensvettern_auf():
    text = ("Ratsherr Dr. Sebastian Rohe erläutert, dass die Fraktion den Entwurf trage, "
            "weil er die Investitionen in Schulen und Sporthallen absichere. Die "
            "Sanierungen seien über Jahre aufgeschoben worden; jetzt sei der Zeitpunkt, "
            "die Mittel dafür verbindlich einzuplanen.")
    (b,) = hd.debatte(text, ANWESEND)
    assert b.name == "Dr. Sebastian Rohe"
    assert b.fraktion == "Grüne", "der Namensvetter sitzt für FDP/Volt"
    assert b.fraktion_unklar is False


def test_gruppe_bleibt_gruppe():
    """`normalize_party` zöge „FDP/Volt" auf „FDP" zusammen — Lükermann ist Volt."""
    text = ("Ratsherr Lükermann empfindet die Entwicklungen der Haushaltsberatungen als "
            "tragisch, weil den Organisationen bedeutende Mittel für ihre Arbeit fehlten. "
            "Die Vereine hätten über Monate keine Planungssicherheit gehabt und müssten "
            "nun Angebote zurückfahren.")
    (b,) = hd.debatte(text, ANWESEND)
    assert b.fraktion == "FDP/Volt"


def test_altfraktion_faellt_auf_das_protokoll_zurueck():
    """WFO-LKR (2016–2021) kennt `parties.py` nicht — die Fraktion trotzdem nennen."""
    text = ("Ratsherr Norrenbrock begrüßt insbesondere die ehrenamtliche Arbeit der Vereine "
            "und wirbt dafür, die Mittel für die Stadtteilarbeit nicht zu kürzen. Gerade "
            "in den Randlagen halte dieses Engagement das Gemeinwesen zusammen, und es "
            "koste die Stadt vergleichsweise wenig.")
    (b,) = hd.debatte(text, ANWESEND)
    assert b.fraktion == "WFO-LKR"


def test_sitzungsleitung_zaehlt_zu_keiner_fraktion():
    """Die Leitung ruft jeden Punkt auf; ihre Wortmeldungen ihrer Fraktion
    zuzurechnen, kippte die Bilanz (2020: 22 von 40 Wortmeldungen)."""
    text = ("Ratsvorsitzender Harms weist auf die fortgeschrittene Zeit hin und möchte die "
            "Beratung zügig fortsetzen, damit die Abstimmungen heute noch erfolgen können. "
            "Er bittet die Fraktionen, sich an die vereinbarten Redezeiten zu halten, und "
            "kündigt an, die Reihenfolge beizubehalten.")
    (b,) = hd.debatte(text, ANWESEND)
    assert b.role == "leadership"
    assert b.fraktion is None, "die Leitung spricht nicht für ihre Fraktion"


def test_rednerliste_in_einer_rede_wird_nicht_zerschnitten():
    """„… Ratsfrau Finke, Ratsherr Prange und dann Ratsherr Lükermann" ist eine
    Aufzählung INNERHALB einer Rede, kein Redewechsel."""
    text = ("Ratsvorsitzender Harms erinnert an die Redereihenfolge und schlägt vor, die "
            "Redezeit auf zehn Minuten je Fraktion zu begrenzen. Somit ergebe sich die "
            "Reihenfolge SPD, CDU, Ratsfrau Finke,\nRatsherr Prange und dann Ratsherr "
            "Lükermann. Dem vorgeschaltet werde die Verwaltung mit ihrer Einführung.")
    beitraege = hd.debatte(text, ANWESEND)
    assert len(beitraege) == 1
    assert beitraege[0].role == "leadership"


def test_kurzes_verfahren_ist_keine_rede():
    assert hd.debatte("Ratsvorsitzender Harms lässt abstimmen.", ANWESEND) == []


def test_genannte_person_bekommt_die_rede_nicht():
    """„Ratsherr Prange dankt Stadtkämmerin Dr. Figura" ist Pranges Rede."""
    text = ("Ratsherr Prange dankt Stadtkämmerin Dr. Figura für die Aufstellung des "
            "Haushaltes und für die Geduld in den vielen Sitzungen der letzten Wochen. "
            "Seine Fraktion trage den Entwurf mit, weil er die Daseinsvorsorge sichere "
            "und zugleich die Verschuldung begrenze.")
    (b,) = hd.debatte(text, ANWESEND)
    assert b.name == "Ulf Prange"
    assert b.fraktion == "SPD"


def test_layout_ohne_leerzeilen():
    """Die Protokolle bis 2020 setzen zwischen zwei Reden keine Leerzeile."""
    text = (
        "Ratsherr Prange erläutert die Schwerpunkte seiner Fraktion und wirbt um "
        "Zustimmung zu den vorgelegten Änderungen im Bereich der Schulen und der "
        "Kinderbetreuung, die seit Jahren überfällig seien.\n"
        "Ratsherr Lükermann entgegnet, dass die Gegenfinanzierung offenbleibe und "
        "die Rücklagen dadurch stärker beansprucht würden als dargestellt. Er "
        "fordert eine belastbare mittelfristige Planung ein."
    )
    beitraege = hd.debatte(text, ANWESEND)
    assert [b.fraktion for b in beitraege] == ["SPD", "FDP/Volt"]


# ---------------------------------------------------------------------- Anträge

@pytest.mark.parametrize("title, erwartet", [
    ("Änderungsliste der CDU-Fraktion", ["CDU"]),
    ("Änderungsliste der Fraktionen SPD, CDU und FDP zum Ergebnishaushalt", ["SPD", "CDU", "FDP"]),
    ("Änderungsliste der CDU-Fraktion und Gruppe FDP/Volt zum Ergebnishaushalt", ["CDU", "FDP/Volt"]),
    ("Änderungsliste der Gruppe DIE LINKE./Piratenpartei", ["Die Linke/Piraten"]),
    ("Änderungsliste der Gruppe Für Oldenburg zum Finanzhaushalt", ["Für Oldenburg"]),
    ("Änderungsliste der WFO-LKR-Fraktion", ["WFO-LKR"]),
    ("Änderungsliste der Fraktionen Bündnis 90/Die Grünen und SPD", ["Grüne", "SPD"]),
    ("Änderungsliste der BSW-Fraktion zum Erfolgsplan", ["BSW"]),
])
def test_urheber(title, erwartet):
    assert hd.author(title) == erwartet


def test_gruppe_schluckt_die_einzelparteien():
    """„Gruppe FDP/Volt" darf nicht zusätzlich als „FDP" und „Volt" zählen."""
    assert hd.author("Änderungsliste der Gruppe FDP/Volt") == ["FDP/Volt"]


def test_verwaltungsliste_ist_kein_fraktionsantrag():
    a = hd.antrag_aus_zeile({"title": "Änderungsliste Verwaltung I zum Ergebnishaushalt",
                             "outcome": "accepted", "vote": "unanimous",
                             "item_number": "6.5", "ksinr": 1})
    assert a.ist_verwaltung is True
    assert a.author is None


def test_sammelabstimmung_ist_kein_antrag():
    """„So geänderter Ergebnishaushalt einschließlich der Änderungslisten" ist
    die Schlussabstimmung über das Ganze, kein weiterer Antrag."""
    for title in ("So geänderter Erfolgsplan einschließlich der Änderungslisten",
                  "Abstimmung über den so geänderten Ergebnishaushalt"):
        assert hd.antrag_aus_zeile({"title": title, "outcome": "accepted", "vote": None,
                                    "item_number": "6.5", "ksinr": 1}) is None


# ------------------------------------------------------------ Store: Jahrgänge

def _runde_2026(store):
    """Ein Jahrgang, wie er im Bestand liegt: Ausschuss und Rat stimmen über
    dieselben Listen ab, der Rat führt die Debatte."""
    for ksinr, committee, date in ((10, "Ausschuss für Finanzen und Beteiligungen", "2026-02-04"),
                                  (11, "Rat", "2026-02-09")):
        store.save_session(CouncilSession(
            ksinr=ksinr, committee=committee, session_date=date, session_time="17:00",
            location="Rathaus",
            agenda_items=[AgendaItem(item_number="6", title="Haushalt 2026", kvonr=None)],
        ))

    # Teilabstimmungen hängen als ``sub_votes`` am Beschluss und tragen ihren
    # Text in ``description`` — so schreibt der Protokoll-Import sie.
    gemeinsam = [
        {"item_number": "6", "title": "Haushalt 2026", "outcome": "accepted",
         "vote": "majority"},
        {"item_number": "6.5", "title": "Haushaltssatzung und Haushaltsplan 2026 (Kernhaushalt)",
         "outcome": "accepted", "vote": "majority", "no_votes": 20,
         "raw_result": "- mehrheitlich bei 20 Gegenstimmen angenommen -",
         "sub_votes": [
             {"description": "Änderungsliste der CDU-Fraktion zum Ergebnishaushalt",
              "outcome": "rejected", "vote": "majority"},
             {"description": "Änderungsliste Verwaltung I zum Ergebnishaushalt",
              "outcome": "accepted", "vote": "unanimous"},
             {"description": "Abstimmung über den so geänderten Ergebnishaushalt",
              "outcome": "accepted", "vote": "majority"},
         ]},
        # Ein Punkt AUSSERHALB des Sammelpunkts darf nicht mitgezählt werden.
        {"item_number": "7.1", "title": "Stellenplan 2026", "outcome": "accepted",
         "vote": "majority",
         "sub_votes": [{"description": "Änderungsliste der SPD-Fraktion zum Stellenplan",
                        "outcome": "accepted", "vote": "majority"}]},
    ]
    for ksinr in (10, 11):
        store.save_protocol(
            ksinr, {"document_id": ksinr, "url": f"https://example.org/p{ksinr}.pdf"},
            {"protocol_nr": "01/26"},
            PROTOKOLL if ksinr == 11 else "zu 6 Haushalt 2026\nKurzbericht.\n",
            22, "test", gemeinsam, ANWESEND,
        )


def test_haushalt_streit_baut_jahrgang(store):
    _runde_2026(store)
    (runde,) = store.haushalt_streit()
    assert runde["year"] == 2026
    # Ausschuss vor Rat, auch wenn beide am selben Tag tagen.
    assert [s["committee"] for s in runde["stationen"]] == [
        "Ausschuss für Finanzen und Beteiligungen", "Rat"]

    rat = runde["stationen"][1]
    assert rat["top"] == "6", "der Sammelpunkt trägt die Debatte"
    assert rat["official_text"]["outcome"] == "accepted"
    assert rat["official_text"]["no_votes"] == 20
    assert rat["protokoll_url"] == "https://example.org/p11.pdf"


def test_nur_antraege_des_sammelpunkts(store):
    _runde_2026(store)
    rat = store.haushalt_streit()[0]["stationen"][1]
    title = [a["title"] for a in rat["antraege"]]
    assert any("CDU-Fraktion" in t for t in title)
    assert not any("Stellenplan" in t for t in title), (
        "TOP 7.1 gehört nicht zum Haushalts-Sammelpunkt 6"
    )
    verwaltung = [a for a in rat["antraege"] if a["ist_verwaltung"]]
    assert len(verwaltung) == 1 and verwaltung[0]["author"] is None


def test_debatte_haengt_an_der_station(store):
    _runde_2026(store)
    rat = store.haushalt_streit()[0]["stationen"][1]
    fraktionen = [b["fraktion"] for b in rat["debatte"]]
    assert "SPD" in fraktionen
    assert rat["debatte"][0]["role"] == "administration"


def test_jahr_grenzt_ein(store):
    _runde_2026(store)
    assert store.haushalt_streit(2026)
    assert store.haushalt_streit(2019) == []


# ------------------------------------------------- Das Gedächtnis der Zerlegung
#
# Die Seite rechnet bewusst beim Lesen und führt keinen eigenen Datenbestand —
# damit kann sie nicht veralten. Das Gedächtnis darf diese Zusage nicht
# aufweichen: Es ist über den INHALT geschlüsselt, also ist ein Treffer
# dasselbe wie ein Neuberechnen.

def test_gedaechtnis_rechnet_dasselbe_und_nur_einmal(store, monkeypatch):
    """Zweiter Aufruf: gleiches Ergebnis, ohne noch einmal zu zerlegen."""
    hd.gedaechtnis_leeren()
    _runde_2026(store)
    erste = store.haushalt_streit()

    laeufe = []
    echt = hd.debatte
    monkeypatch.setattr(hd, "debatte",
                        lambda *a, **k: (laeufe.append(1), echt(*a, **k))[1])
    zweite = store.haushalt_streit()

    assert zweite == erste
    assert laeufe == []          # nichts wurde noch einmal zerlegt


def test_geaendertes_protokoll_wird_neu_gerechnet(store):
    """Der Kern der Zusage: Ein nachgetragenes Protokoll erscheint sofort.

    Kein Backfill, kein Cron, kein Ungültigmachen — der Schlüssel deckt den
    Protokolltext ab, also findet ein geänderter Text seinen alten Eintrag
    gar nicht erst."""
    hd.gedaechtnis_leeren()
    _runde_2026(store)
    vorher = store.haushalt_streit()[0]["stationen"][-1]["debatte"]
    assert vorher

    # Dasselbe Protokoll, aber ohne die Reden — wie ein Kurzbericht, der
    # später durch die Langfassung ersetzt wird (hier andersherum).
    store.save_protocol(
        11, {"document_id": 11, "url": "https://example.org/p11.pdf"},
        {"protocol_nr": "01/26"}, "zu 6 Haushalt 2026\nKurzbericht.\n", 22, "test",
        [{"item_number": "6", "title": "Haushalt 2026", "outcome": "accepted",
          "vote": "majority"}], ANWESEND)

    nachher = store.haushalt_streit()[0]["stationen"][-1]["debatte"]
    assert nachher != vorher


def test_gedaechtnis_gibt_kopien_heraus(store):
    """Wer an der Antwort herumschreibt, verdirbt sie nicht für alle."""
    hd.gedaechtnis_leeren()
    _runde_2026(store)
    erste = store.haushalt_streit()[0]["stationen"][-1]["debatte"]
    erste[0]["name"] = "verbogen"

    zweite = store.haushalt_streit()[0]["stationen"][-1]["debatte"]
    assert zweite[0]["name"] != "verbogen"
