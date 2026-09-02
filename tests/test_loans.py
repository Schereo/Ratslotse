"""Kredite und Zinsen — der Parser der Unterrichtungen (council/loans.py).

Die Fixtures sind echte Vorlagentexte aus dem Bestand (gekürzt auf den
Fließtext), je einer je Form: Monatsbericht mit Umschuldung und Ersparnis
(22/0056), Bericht ohne Vorgang (22/0701), Bericht mit drei Posten samt
Kreditaufnahme und Zinssatz (25/0527), Einzelbericht 2018 (18/0163),
Prolongation mit Zinsbindung (23/0907), Feldliste 2022 (22/0251)."""
import pytest

from council import herkunft as h, loans
from council.store import CouncilStore

FIXTURES = {
    "18/0163": ("Umschuldung von Kommunalkrediten in Höhe von insgesamt 95.480.807,12 EUR - Bericht -",
        " Ausdruck vom: 19.02.2018 Seite: 1/1 15.02.2018 Amt für Controlling und Finanzen Vorlagen-Nr: 18/0163 öffentlich Umschuldung von Kommunalkrediten in Höhe von insgesamt 95.480.807,12 EUR - Bericht - Beratungsfolge: Ausschuss für Finanzen und Beteiligungen am: 07.03.2018 Zu TOP: Verwaltungsausschuss am: 12.03.2018 Zu TOP: Rat am: 23.04.2018 Zu TOP: Bericht: Mit Entscheidung vom 14.02.2018 wurden die in der Anlage aufgeführten Darlehen zum 16.02.2018 zu den angegebenen Konditionen umgeschuldet. Die Angaben zu den dazugehörigen Zinssicherungsgeschäften sind nachrichtlich hinzug e- fügt. Die Unterrichtung erfolgt nach § 9 i. V. m. § 7 der vom Rat am 21.05.2012 beschlossenen Richtlinie der Stadt Oldenburg (Oldb) für die Aufnahme von Krediten und zur Umschuldung von Krediten. Um Kenntnisnahme wird gebeten. Finanzielle Auswirkungen: Durch die Umschuldungen konnte der Zinsaufwand gegenüber der vergleic hbaren he r- kömmlichen Kommunalkreditfinanzierung im Zeitraum 16.02.2018 bis 16.05.2018 um 112.142,95 EUR reduziert werden. K r o g m a n n "),
    "22/0056": ("Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie - Bericht",
        " Ausdruck vom: 21.02.2022 Seite: 1/1 15.02.2022 Amt für Controlling und Finanzen Vorlagen-Nr: 22/0056 öffentlich Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie - Bericht Beratungsfolge: Ausschuss für Finanzen und Beteiligungen am: 02.03.2022 Zu TOP: Verwaltungsausschuss am: 14.03.2022 Zu TOP: Rat am: 28.03.2022 Zu TOP: Bericht: In den Monaten Januar und Februar 2022 sind die folgenden Kredite für Investitionen und Investitionsfördermaßnahmen aufgenommen oder umgeschuldet worden: Umschuldung von Kommunalkrediten in Höhe von insgesamt 78.812.404,40 Euro Mit Entscheidung vom 10.02.2022 wurden die in der Anlage aufgeführten Darlehen zum 16.02.2022 zu den angegebenen Konditionen umgeschuldet. Die Angaben zu den dazugehörigen Zinssicherungsgeschäften sind nachrichtlich hinzuge- fügt. Um Kenntnisnahme wird gebeten. Finanzielle Auswirkungen: Bei den Umschuldungen zum 16.11.2021 wird der Zinsaufwand gegenüber der vergleichba- ren herkömmlichen Kommunalkreditfinanzierung für den Zeitraum 16.11.2021 bis 16.02.2022 um 75.604,35 Euro reduziert. Im Haushaltsplan waren für diesen Umschuldungsdurchga ng 97.420,89 Euro Zinsaufwand eingeplant (kalkulierte Marge 0,500%). Das Ausschreibungsergebnis ergab einen Zinsauf- wand von 14.807,98 Euro (erzielte Marge 0,076%). Das Haushalts ergebnis verbessert sich somit durch dieses Ausschreibungsergebnis um 82.612,91 Euro. In Vertretung D r . J u l i a F i g u r a "),
    "22/0251": ("Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie - Bericht",
        " Ausdruck vom: 22.04.2022 Seite: 1/2 29.03.2022 Amt für Controlling und Finanzen Vorlagen-Nr: 22/0251 öffentlich Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie - Bericht Beratungsfolge: Ausschuss für Finanzen und Beteiligungen am: 04.05.2022 Zu TOP: Verwaltungsausschuss am: 30.05.2022 Zu TOP: Rat am: 30.05.2022 Zu TOP: Bericht: In den Monaten März und April 2022 sind die folgenden Kredite für Investitionen und Inves- titionsfördermaßnahmen aufgenommen oder umgeschuldet worden: EGH – Kreditaufnahme für Investitionen aus den Wirtschaftsplänen 2020 und 2021 (Innenfinanzierung durch Kernverwaltung) Betrag: 10.000.000,00 Euro Wertstellung: 28.04.2022 Zinssatz: 0,00% Zinsbindung: 18.11.2052 Tilgung: Ratentilgung; vierteljährlich 82.500,00 Euro bei einer An- fangsrate in Höhe von 100.000,00 Euro Zahlungstermine: vierteljährlich zum 16.02., 16.05., 16.08. und 16.11.; erstmalig zum 16.11.2022 Restkapital zum 18.11.2052: 0,00 Euro Die Kreditneuaufnahme war durch eine restliche Kreditermächtigung aus 2020 in Höhe von 2.711.600 Euro und einer Kreditermächtigung 2021 in Höhe von 7.288.400 Euro genehmigt. Die restliche Kreditermächtigung 2020 in Höhe von 2.711.600 Euro wäre mit Inkrafttreten der Haushaltssatzung 2022 verfallen. Die Investitionen wurden über eine Ausleihung durch die Kernverwaltung finanziert. Die Mit- tel standen aus Überschüssen aus Verwaltungstätigkeit zur Verfügung. Der Ausleihungsvertrag wurde so gestaltet, dass eine jederzeitige Rückforderung der Kre- ditmittel durch die Kernverwaltung möglich ist, sollte dort zusätzlicher Liquiditätsbedarf ent- stehen. Der EGH könnte sich dann auf Grundlage der ursprünglichen Kreditermächtigung am Kapitalmarkt umschulden. Ausdruck vom: 22.04.2022 Seite: 2/2 Finanzielle Auswirkungen: Bei der Planung der Zinsaufwendungen für den Wirtschaftsplan 2022 des EGH wurde da- von ausgegangen, dass die jeweiligen Ausleihungen grundsätzlich dauerhaft zur Verfügung gestellt werden können. Sollte es wider Erwarten schon in 2022 zu ein er Rückforderung der Kreditmittel durch die Kernverwaltung kommen, wäre durch eine Umschuldung am Kapital- markt mit einem höheren Zinsaufwand zu rechnen. In Vertretung D r . J u l i a F i g u r a "),
    "22/0701": ("Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie - Bericht",
        " Ausdruck vom: 04.10.2022 Seite: 1/1 19.09.2022 Amt für Controlling und Finanzen Vorlagen-Nr: 22/0701 öffentlich Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie - Bericht Beratungsfolge: Ausschuss für Finanzen und Beteiligungen am: 12.10.2022 Zu TOP: Verwaltungsausschuss am: 07.11.2022 Zu TOP: Rat am: 07.11.2022 Zu TOP: Bericht: Im Monat September 2022 sind keine Kredite für Investitionen und Investitions- fördermaßnahmen aufgenommen oder umgeschuldet worden. Finanzielle Auswirkungen: ./. In Vertretung D r . J u l i a F i g u r a "),
    "23/0907": ("Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie",
        " Ausdruck vom: 28.11.2023 Seite: 1/3 Amt für Controlling und Finanzen Datum: 28.11.2023 Vorlagen-Nr.: 23/0907 Status: öffentlich Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie Beratungsfolge: Termin: Ausschuss für Finanzen und Beteiligungen 06.12.2023 Verwaltungsausschuss 18.12.2023 Rat 18.12.2023 Anlass: Nach § 8 Abs. 1 Satz 1 und § 10 Abs. 3 der Richtlinie für die Aufnahme von Krediten und zur Umschuldung von Krediten ist der Rat über aufgenommene Kredite für Investitionen und Investitionsfördermaßnahmen und über Umschuldungen zu unterrichten. Bericht: Im Monat November 2023 sind folgende Kredite für Investitionen und Investitionsfördermaß- nahmen umgeschuldet oder prolongiert worden: 1.) Prolongation zweier Förderkredite in Höhe von insgesamt 3.233.206,00 Euro für die Kernverwaltung Zum Umschuldungstermin 15.11.2023 war über die weitere Vorgehensweise zweier Förder- kredite der Kernverwaltung in Höhe von 3.233.206,00 Euro zu entscheiden, da die Zinsbin- dungen zum genannten Termin ausgelaufen sind. Einen Monat vor diesem Termin wurden der Stadt Oldenburg jeweils zwei identische Prolongationsangebote mit Zinsbindungen für weitere 10 Jahre, mit einem Zinssatz in Höhe von 3,70 % unterbreitet. Diesen Angeboten musste binnen einer Frist von zwei Wochen nach Erhalt widersprochen werden, da die Pro- longationen ansonsten als angenommen galten. Zur Entscheidung wurde eine Marktsondierung durchgeführt. Die Einholung eines indikati- ven Vergleichsangebot bei einer anderen Bank ergab für die gleiche Zinsbindungslaufzeit einen Zinssatz in Höhe von 3,76 %. Aufgrund dieser Umstände wurde sich für das günstigere Angebot und damit für die Prolon- gation zu einem Zinssatz in Höhe von 3,70 % entschieden. Ausdruck vom: 28.11.2023 Seite: 2/3 2.) Umschuldung eines Kommunalkredits in Höhe von 1.869.000,00 Euro für den Eigenbe- trieb Gebäudewirtschaft und Hochbau Zum Umschuldungstermin 16.11.2023 endete die Zinsabsicherung eines Grundgeschäftes mittels eines Festzins-Zahler-Swaps. Vor diesem Hintergrund musste über die weitere Vor- gehensweise in Bezug auf das Grundgeschäft entschieden werden. Das Darlehen wurde unter Berücksichtigung der folgenden Handlungsalternativen  Zwischenfinanzierung für drei Monate, um zur nächsten Neuaufnahme oder zum nächsten Umschuldungstermin mehrere Kredite zusammenlegen zu können  Finanzierung für sechs Jahre zur Vermeidung von Klumpenrisiken  Finanzierung für zehn Jahre zur Vermeidung von Klumpenrisiken  Finanzierung bis zur Restlaufzeit (22,25 Jahre) zum 09.11.2023 neu ausgeschrieben. Am Tag der Kreditentscheidung wurden die Bankenangebote aller Laufzeiten zusammenge- tragen und als Entscheidungsgrundlage diskutiert. Aufgrund der volatilen Marktsituation mit erheblichen Ungewissheiten insbesondere für die Zukunft, hat das günstigste Festzinsange- bot (Zinssatz 3,55 %) mit einer Laufzeit bis zum 16.11.2033 den Zuschlag erhalten. Zum Zeitpunkt der Ausschreibung wurde diese Laufzeit als Kompromiss zwischen Planungssi- cherheit und Flexibilität angesehen. Unter Beachtung vorheriger Kreditentscheidungen für Umschuldungen mit der gleichen Laufzeit war ein Zinssatz in Höhe von 3,55 % als günstig zu bewerten. Im Übrigen wird auf die Anlage Übersicht Ausschreibungsergebnis (zu 2.) verwiesen. 3.) Umschuldung von Kommunalkrediten in Höhe von insgesamt 68.454.678,21 Euro Mit Entscheidung vom 14.11.2023 wurden die in der Anlage (Ausschreibungsergebnis zu 3) aufgeführten Grundgeschäfte zum 16.11.2023 zu den angegebenen Konditionen umge- schuldet. Sowohl für die Ausschreibung der Kredite der Kernverwaltung und des Bäderbetriebs als auch für die Ausschreibung der Kredite des Eigenbetriebs Gebäudewirtschaft und Hochbau, konnte jeweils das wirtschaftlich günstigste Angebot angenommen werden, da diese Kredit- institute auch die geforderte Eigenerklärung zur Einhaltung der Vorgaben nach Artikel 5k der Verordnung (EU) Nr. 833/2014 in der Fassung des Art. 1 Ziff. 23 der Verordnung (EU) 2022/576 des Rates vom 8. April 2022 abgegeben hatten. Die Angaben zu den dazugehörigen Zinssicherungsgeschäften sind nachrichtlich hinzuge- fügt. Auswirkungen: a) Finanzen 1.) Prolongation zweier Kommunalkredite in Höhe von insgesamt 3.233.206,00 Euro Durch die Prolongation der beiden Kommunalkredite hat die Stadt Oldenburg jährlich Ausdruck vom: 28.11.2023 Seite: 3/3 einen Schuldendienst (Zinsen und Tilgung) in Höhe von ungefähr 281.390,00 Euro zu leisten. Aufgrund der vierteljährlichen Tilgungen wird sich dieser Betrag jährlich verringern. Die gestiegenen Zinsaufwendungen sind im Haushaltsplan 2024 sowie in der weite- ren Finanzplanung der Kernverwaltung berücksichtigt. 2.) Umschuldung eines Kommunalkredits in Höhe von 1.869.000,00 Euro Durch die Umschuldung des Kommunalkredits hat die Stadt Oldenburg jährlich einen Schuldendienst (Zinsen und Tilgung) in Höhe von ungefähr 149.230,00 Euro zu leis- ten. Aufgrund der vierteljährlichen Tilgungen wird sich dieser Betrag jährlich verrin- gern. Die gestiegenen Zinsaufwendungen sind im Haushaltsplan 2024 sowie in der weite- ren Finanzplanung des Eigenbetriebs Gebäudewirtschaft und Hochbau berücksich- tigt. 3.) Umschuldung von Kommunalkrediten in Höhe von insgesamt 68.454.678,21 Euro Bei den vierteljährlichen Umschuldungen zum 16.11.2023 wird der Zinsaufwand ge- genüber der vergleichbaren herkömmlichen Kommunalkreditfinanzierung für den Zeitraum 16.11.2023 bis 16.02.2024 um 87.650,63 Euro reduziert. Im Haushaltsplan waren für diesen Umschuldungsdurchgang 87.469,87 Euro Zins- aufwand eingeplant (kalkulierte Marge 0,500%). Das Ausschreibungsergebnis ergab einen Zinsaufwand von 5.947,95 Euro (erzielte durchschnittliche Marge 0,034%). Das Haushaltsergebnis verbessert sich somit durch dieses Ausschreibungsergebnis um 81.521,92 Euro. b) Klima ./. c) Weitere ./. In Vertretung Dr. Julia Figu ra Anlagen: Übersicht Ausschreibungsergebnis (zu 2.) Übersicht Ausschreibungsergebnis (zu 3.) "),
    "25/0527": ("Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie",
        "Ausdruck vom: 19.08.2025 Seite: 1/3 Amt für Controlling und Finanzen Datum: 19.08.2025 Vorlagen-Nr.: 25/0527 Status: öffentlich Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen nach § 8 der Kreditrichtlinie Beratungsfolge: Termin: Ausschuss für Finanzen und Beteiligungen 03.09.2025 Verwaltungsausschuss 29.09.2025 Rat 29.09.2025 Anlass: Nach § 8 Abs. 1 Satz 1 und § 10 Abs. 3 der Richtlinie für die Aufnahme von Krediten und zur Umschuldung von Krediten ist der Rat über aufgenommene Kredite für Investitionen und Investitionsfördermaßnahmen und über Umschuldungen zu unterrichten. Bericht: In den Monaten Juni, Juli und August 2025 sind folgende Kredite für Investitionen und Investitionsfördermaßnahmen aufgenommen und umgeschuldet worden: 1.) Kreditaufnahme des Bäderbetriebs Oldenburg am Kapitalmarkt in Höhe von 9.742.709,00 Euro Durch die Genehmigung des Wirtschaftsplans 2025 ist der Bäderbetrieb Oldenburg ermächtigt Kredite in Höhe von 19.485.418,00 Euro aufzunehmen. Mit Kreditentscheidung vom 05.06.2025 wurde ein Teil der Kreditermächtigung in Höhe von 9.742.709,00 Euro in Anspruch genommen. Hierbei konnte das günstigste Angebot mit einem Zinssatz in Höhe von 3,03 % ausgewählt werden, da das Kreditinstitut auch die geforderte Eigenerklärung zur Einhaltung der Vorgaben nach Artikel 5k der Verordnung (EU) Nr. 833/2014 in der Fassung des Art. 1 Ziff. 23 der Verordnung (EU) 2022/576 des Rates vom 8. April 2022 abgegeben hatte. Anlage 1 zeigt die zugrundeliegende Kreditentscheidung vom 05.06.2025. Ausdruck vom: 19.08.2025 Seite: 2/3 2.) Umschuldung von Investitionskrediten der Kernverwaltung in Höhe von insgesamt 10.976.653,00 Euro Aufgrund des Zinsbindungsendes eines Förderkredits mit einer Restschuld in Höhe von 3.291.653,00 Euro und dem Auslaufen eines Zinsderivates mit einem dazugehörigen Grundgeschäft in Höhe von 7.685.000,00 Euro werden zwei Kredite zur Mitte August 2025 umgeschuldet. Im zuletzt genannten Sachverhalt verliert das zugrundeliegende Grundgeschäft das Erfordernis zur Konnexität. Um Zahlungsstromänderungsrisiken aufgrund der variablen Konditionen des Grundgeschäfts zu minimieren, sollte der Kredit zukünftig mit einer festen Zinsbindung versehen werden. In beiden Fällen konnte das günstigste Angebot ausgewählt werden, da das jeweilige Kreditinstitut auch die geforderte Eigenerklärung zur Einhaltung der Vorgaben nach Artikel 5k der Verordnung (EU) Nr. 833/2014 in der Fassung des Art. 1 Ziff. 23 der Verordnung (EU) 2022/576 des Rates vom 8. April 2022 abgegeben hatte. Die Anlagen 2 und 3 zeigen die zugrundeliegenden Kreditentscheidungen vom 29.07.2025 und vom 05.08.2025. 3.) Umschuldung von Kommunalkrediten (Grundgeschäfte) in Höhe von insgesamt 52.427.952,02 Euro Mit Entscheidung vom 11.08.2025 wurden die in der Anlage 4 aufgeführten Grundge- schäfte zum 18.08.2025 zu den angegebenen Konditionen umgeschuldet. Sowohl für die Ausschreibung der Kredite der Kernverwaltung als auch für die Kredite der Eigenbetriebe Gebäudewirtschaft und Hochbau und den Bäderbetrieb Oldenburg konnte jeweils das wirtschaftlich günstigste Angebot angenommen werden, da diese Kreditinstitute auch die geforderte Eigenerklärung zur Einhaltung der Vorgaben nach Artikel 5k der Verordnung (EU) Nr. 833/2014 in der Fassung des Art. 1 Ziff. 23 der Verordnung (EU) 2022/576 des Rates vom 8. April 2022 abgegeben hatten. Die Angaben zu den dazugehörigen Zinssicherungsgeschäften sind nachrichtlich in Anlage 5 hinzugefügt. Auswirkungen: a) Finanzen 1.) Kreditaufnahme des Bäderbetriebs Oldenburg am Kapitalmarkt in Höhe von 9.742.709,00 Euro Der Kreditvertrag wurde mit einer zehnjährigen Zinsbindung abgeschlossen. Im verbleibenden Haushaltsjahr 2025 ist mit Zinsaufwendungen in Höhe von knapp 127.101,76 Euro zu rechnen. Aufgrund von unterjährigen Tilgungen wird sich der vierteljährlich zu zahlende Zinsaufwand in Höhe von ursprünglich 73.801,02 Euro schrittweise bis zum Ende der Zinsbindung verringern. Ausdruck vom: 19.08.2025 Seite: 3/3 2.) Umschuldung von Investitionskrediten der Kernverwaltung in Höhe von insgesamt 10.976.653,00 Euro Im Vergleich zur Planung konnten die Umschuldungen zu günstigeren Zinskonditionen vorgenommen werden. Hierdurch spart die Stadt Oldenburg für das restliche Haushaltsjahr 2025 insgesamt Zinsaufwand in Höhe von ca. 36.212,52 Euro ein. Die Haushaltsplanung 2025 sah für die Prolongationen Zinssätze in Höhe von 3,71 % vor. Stattdessen konnten die Kredite zu Zinssätzen in Höhe von 2,84 % und 3,03 % umgeschuldet werden. 3.) Umschuldung von Kommunalkrediten (Grundgeschäfte) in Höhe von insgesamt 52.427.952,02 Euro Bei den vierteljährlichen Umschuldungen zum 18.08.2025 wird der Zinsaufwand gegenüber der vergleichbaren herkömmlichen Kommunalkreditfinanzierung für den Zeitraum 18.08.2025 bis 17.11.2025 um 63.046,07 Euro reduziert. Im Haushaltsplan waren für diesen Umschuldungsdurchgang 39.757,86 Euro Zinsaufwand eingeplant (kalkulierte Marge 0,300 %). Das Ausschreibungsergebnis ergab einen Zinsaufwand von 2.120,42 Euro (erzielte durchschnittliche Marge 0,0160 %). Das Haushaltsergebnis verbessert sich somit durch dieses Ausschreibungsergebnis um 37.637,44 Euro. b) Klima ./. c) Weitere ./. In Vertretung D r . J u l i a F i g u r a Anlagen: Anlage 1: Kreditentscheidung 1200 730 006 vom 05.06.2025 Anlage 2: Kreditentscheidung 1000 730 005 vom 29.07.2025 Anlage 3: Kreditentscheidung 1000 730 006 vom 05.08.2025 Anlage 4: Kreditentscheidung Umschuldung der Grundgeschäfte zum 18.08.2025 Anlage 5: Nachrichtliche Angaben Zinssicherungsgeschäfte (Umschuldung von Grundgeschäften)"),
}


def _rows(*nrs):
    return [{"template_number": nr, "title": FIXTURES[nr][0], "raw_text": FIXTURES[nr][1],
             "document_id": 1000 + i, "document_url": f"https://example.org/{i}"}
            for i, nr in enumerate(nrs)]


def _nach(result, nr):
    n = next(x for x in result["notices"] if x["template_number"] == nr)
    return n, [i for i in result["items"] if i["template_number"] == nr]


def test_erkennung_am_titel():
    assert loans.erkenne("Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen")
    assert loans.erkenne("Umschuldung von Kommunalkrediten in Höhe von insgesamt 95.480.807,12 EUR - Bericht -")
    assert not loans.erkenne("Richtlinie der Stadt Oldenburg für die Aufnahme von Krediten")
    assert not loans.erkenne("Annahme von Zuwendungen durch den Rat")


def test_monatsbericht_mit_umschuldung_und_ersparnis():
    r = loans.lies(_rows("22/0056"))
    n, items = _nach(r, "22/0056")
    assert (n["period_from"], n["period_to"], n["year"]) == ("2022-01", "2022-02", 2022)
    assert n["interest_saving"] == pytest.approx(75_604.35)
    assert (n["saving_from"], n["saving_to"]) == ("2021-11-16", "2022-02-16")
    assert n["document_date"] and n["document_date"].startswith("2022-")
    assert len(items) == 1 and items[0]["kind"] == "refinancing"
    assert items[0]["amount"] == pytest.approx(78_812_404.40)
    assert items[0]["decided_at"] == "2022-02-10"
    assert n["probes"] == [loans.ZEITRAUM, loans.POSTEN_BETRAG]


def test_bericht_ohne_vorgang_belegt_den_monat():
    r = loans.lies(_rows("22/0701"))
    n, items = _nach(r, "22/0701")
    assert n["none_reported"] and n["items"] == 0 and items == []
    assert (n["period_from"], n["period_to"]) == ("2022-09", "2022-09")


def test_drei_posten_mit_kreditaufnahme_und_zinssatz():
    r = loans.lies(_rows("25/0527"))
    n, items = _nach(r, "25/0527")
    assert (n["period_from"], n["period_to"]) == ("2025-06", "2025-08")
    assert n["document_date"] == "2025-08-19"
    assert [i["kind"] for i in items] == ["loan", "refinancing", "refinancing"]
    assert items[0]["borrower"] == "Bäderbetrieb Oldenburg"
    assert items[0]["amount"] == pytest.approx(9_742_709.0)
    assert items[0]["rate_pct"] == pytest.approx(3.03)
    assert items[0]["decided_at"] == "2025-06-05"
    assert items[1]["borrower"] == "Kernverwaltung"
    assert items[1]["amount"] == pytest.approx(10_976_653.0)
    # Die Grundgeschäfte tragen keinen Schuldner in der Überschrift — NULL, nicht geraten.
    assert items[2]["borrower"] is None and items[2]["amount"] == pytest.approx(52_427_952.02)
    # Die Zusammenfassung am Ende wiederholt die Nummern — kein vierter Posten.
    assert len(items) == 3


def test_einzelbericht_2018_liest_titel_und_ersparnis():
    r = loans.lies(_rows("18/0163"))
    n, items = _nach(r, "18/0163")
    assert (n["period_from"], n["period_to"]) == ("2018-02", "2018-05")
    assert n["interest_saving"] == pytest.approx(112_142.95)
    assert items[0]["kind"] == "refinancing" and items[0]["amount"] == pytest.approx(95_480_807.12)
    assert items[0]["decided_at"] == "2018-02-14"


def test_prolongation_mit_zinsbindung():
    r = loans.lies(_rows("23/0907"))
    _, items = _nach(r, "23/0907")
    assert items[0]["kind"] == "prolongation"
    assert items[0]["rate_pct"] == pytest.approx(3.70) and items[0]["fixed_years"] == 10


def test_feldliste_2022_innenfinanzierung():
    r = loans.lies(_rows("22/0251"))
    _, items = _nach(r, "22/0251")
    assert len(items) == 1
    assert items[0]["kind"] == "loan"
    assert items[0]["borrower"] == "Eigenbetrieb Gebäudewirtschaft und Hochbau"
    assert items[0]["amount"] == pytest.approx(10_000_000.0)
    assert items[0]["rate_pct"] == 0.0 and items[0]["fixed_until"] == "2052-11-18"


def test_ohne_volltext_verworfen():
    r = loans.lies([{"template_number": "99/0001", "title": "Unterrichtung des Rates über Kreditaufnahmen",
                     "raw_text": "", "document_id": None, "document_url": None}])
    assert r["notices"] == [] and r["rejected"][0]["reason"] == "kein Volltext"


def test_store_rundlauf(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    r = loans.lies(_rows("25/0527", "22/0701"))
    lauf = h.Herkunft(kind="ris", url="https://example.org", label="Lauf",
                      probe=[loans.ZEITRAUM], probe_result="x")
    for n in r["notices"]:
        n["herkunft"] = h.Herkunft(kind="ris", document_id=n["document_id"], url=n["document_url"],
                                   label=f"Vorlage {n['template_number']}", citation=loans.FUNDSTELLE,
                                   probe=n["probes"], probe_result="ok")
    assert store.save_loan_notices(r["notices"], r["items"], lauf) == 2
    notices = store.get_loan_notices()
    assert [n["template_number"] for n in notices] == ["22/0701", "25/0527"]
    assert notices[0]["probes"] == [loans.ZEITRAUM]
    items = store.get_loan_items()
    assert len(items) == 3 and items[0]["period_from"] == "2025-06"
    assert all(i["herkunft_id"] for i in items)
    # Ein zweiter Lauf ersetzt, verdoppelt nicht.
    store.save_loan_notices(r["notices"], r["items"], lauf)
    assert len(store.get_loan_items()) == 3
    assert not {t: k for t, k in store.herkunft_luecken().items() if t.startswith("council_loan")}
    store.close()


# --------------------------------------------------------------------------
# Die alte Form (2018–2021): „Unterrichtung nach § 8 der Kreditrichtlinie"
# --------------------------------------------------------------------------

import json
from pathlib import Path

ALT = json.loads((Path(__file__).parent / "fixtures" / "kredite_alte_form.json").read_text())


def _alt(*nrs):
    return [{"template_number": nr, "title": ALT[nr]["title"], "raw_text": ALT[nr]["raw_text"],
             "document_id": 2000 + i, "document_url": f"https://example.org/alt/{i}", "kvonr": 100 + i}
            for i, nr in enumerate(nrs)]


def test_erkennung_der_alten_unterrichtung():
    """2018–2022 heißen die Berichte „Unterrichtung nach § 8 der Kreditrichtlinie
    über aufgenommene Kredite …" — ohne das Wort Kreditaufnahme. Vier Jahrgänge
    fehlten, weil weder Titel-Regex noch SQL sie kannten."""
    assert loans.erkenne(ALT["19/0016"]["title"])
    assert "Unterrichtung nach § 8" in loans.TITEL_SQL


def test_feldliste_2018_mit_abruf_und_zinsfestsetzung():
    """19/0016: zwei Abrufe des EGH im Dezember 2018 — „Abruf:" statt „Betrag:",
    „Zinsfestsetzung:" statt „Zinsbindung:", EONIA-Zins ohne Zahl."""
    n, items = _nach(loans.lies(_alt("19/0016")), "19/0016")
    assert (n["period_from"], n["period_to"], n["year"]) == ("2018-12", "2019-01", 2018)
    assert [i["amount"] for i in items][:2] == [2_330_900.0, 9_000_000.0]
    assert all(i["borrower"] == "Eigenbetrieb Gebäudewirtschaft und Hochbau" for i in items[:2])
    assert all(i["kind"] == "loan" for i in items[:2])
    assert items[0]["rate_pct"] is None and items[0]["fixed_until"] is None
    assert items[1]["rate_pct"] == 0.0 and items[1]["fixed_until"] == "2048-11-16"
    assert items[0]["decided_at"] == "2018-12-28"
    assert loans.POSTEN_BETRAG in n["probes"]


def test_feldliste_2019_zwei_betriebe_und_leerer_monat():
    """20/0028: EGH und EB Hafen im Dezember 2019, der Januar 2020 steht als „./."."""
    n, items = _nach(loans.lies(_alt("20/0028")), "20/0028")
    assert (n["period_from"], n["period_to"]) == ("2019-12", "2020-01")
    assert [(i["borrower"], i["amount"], i["fixed_until"]) for i in items] == [
        ("Eigenbetrieb Gebäudewirtschaft und Hochbau", 10_000_000.0, "2049-11-16"),
        ("Eigenbetrieb Hafen", 804_000.0, "2044-11-16")]
    assert not n["none_reported"]


def test_zeitraum_ohne_jahr_kommt_vom_dokumentdatum():
    """21/0144: „Innerhalb der Monate Januar und Februar sind …" — kein Jahr im
    Satz; das Dokument ist vom 15.02.2021."""
    n, items = _nach(loans.lies(_alt("21/0144")), "21/0144")
    assert (n["period_from"], n["period_to"], n["year"]) == ("2021-01", "2021-02", 2021)
    assert len(items) == 1 and items[0]["kind"] == "refinancing"
    assert items[0]["amount"] == 83_663_105.08
    assert n["interest_saving"] == 76_474.0


def test_zeitraum_ueber_den_jahreswechsel_ohne_jahr():
    assert loans.zeitraum("Bericht: Innerhalb der Monate Dezember und Januar sind", 2021) == (
        "2020-12", "2021-01")
    assert loans.zeitraum("Bericht: Innerhalb der Monate Januar und Februar sind", None) == (None, None)


def test_aufzaehlungsglyph_vor_der_umschuldung():
    """18/0910: „\uf0b7 Umschuldung von Kommunalkrediten …" — der Glyph machte
    daraus einen „Sonstigen Vorgang"."""
    assert loans.art("\uf0b7 Umschuldung von Kommunalkrediten in Höhe von 94.577.181,61 EUR") == "refinancing"
    # Die Klammer ist keine Aufzählung — „(Teil-) Auszahlung" bleibt eine Auszahlung.
    assert loans.art("(Teil-) Auszahlung der Kernverwaltung an den Eigenbetrieb BBO") == "disbursement"
