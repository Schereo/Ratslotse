"""Die beschlossene Zusammensetzung der Gremien — Wahlperiode 2026–2031.

Das Ratsinformationssystem nennt, wer in einem Ausschuss sitzt. Für eine
Mehrheitsrechnung reicht das nicht, gemessen am 22.11.2026 gegen die
Beschlüsse der konstituierenden Ratssitzung vom 02.11.2026:

- Im **Jugendhilfeausschuss** führt es nur die sechs Ratsmitglieder. Stimm-
  berechtigt sind fünfzehn (Vorlage 26/0784): dazu drei in der Jugendhilfe
  erfahrene Personen und sechs auf Vorschlag der freien Träger.
- Im **Schulausschuss** fehlen die beiden Schülervertretungen und ein Sitz der
  Lehrkräfte; Arbeitgeber- und Arbeitnehmerverbände stimmen nur in
  Angelegenheiten der berufsbildenden Schulen mit (Vorlage 26/0789).
- In beiden **Betriebsausschüssen** fehlt die dritte Vertretung der
  Beschäftigten („sonstige“, § 110 NPersVG; Vorlagen 26/0783 und 26/0800).
- Im **Sportausschuss** stand ein Mitglied der alten Wahlperiode weiter als
  Ausschussmitglied da: zwölf statt der beschlossenen elf.

Ohne diese Datei rechnete der Mehrheitsrechner dort mit einer falschen
Schwelle — im Betriebsausschuss Gebäudewirtschaft mit 7 von 13 statt 8 von 14,
im Jugendhilfeausschuss mit 4 von 6 statt 8 von 15. Deshalb steht die
Zusammensetzung hier, mit ihrer Vorlage: Was der Rat beschlossen hat, ist die
Wahrheit über die GRÖSSE eines Gremiums; das Ratsinfo bleibt die Quelle dafür,
WER dort für welche Fraktion sitzt.

**Pflege:** Ändert der Rat Größe oder Zusammensetzung eines Ausschusses, wird
hier nachgezogen (und die Vorlage genannt). Ein Gremium ohne Eintrag rechnet
mit dem, was das Ratsinfo führt.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

#: Tag der Ratsbeschlüsse, auf die sich die Einträge stützen.
DECIDED = "02.11.2026"


@dataclass(frozen=True)
class Composition:
    #: Stimmberechtigte Ratsmitglieder laut Beschluss.
    council_seats: int
    #: Weitere Stimmberechtigte ohne Ratsmandat: (Bezeichnung für „N …“, Zahl).
    others: tuple[tuple[str, int], ...] = ()
    #: Nur in bestimmten Angelegenheiten zusätzlich stimmberechtigt — als
    #: ganzer Satzteil („eine Vertretung der Arbeitgeberverbände“).
    conditional: tuple[tuple[str, int], ...] = ()
    #: … und in welchen („In Angelegenheiten der berufsbildenden Schulen“).
    conditional_when: str = ""
    #: Ein sachlicher Zusatzsatz zu diesem Gremium.
    remark: str = ""
    #: Die Vorlage(n), aus denen der Eintrag stammt.
    source: str = ""


_ELEVEN = Composition(11, source="Vorlage 26/0795")

COMPOSITION: dict[str, Composition] = {
    "Rat": Composition(52),
    "Verwaltungsausschuss": Composition(10, source="Vorlage 26/0793"),
    "Ausschuss für Allgemeine Angelegenheiten": _ELEVEN,
    "Ausschuss für Finanzen und Beteiligungen": _ELEVEN,
    "Ausschuss für Gesundheit und Soziales": _ELEVEN,
    "Ausschuss für Integration und Migration": _ELEVEN,
    "Ausschuss für Stadtplanung und Bauen": _ELEVEN,
    "Ausschuss für Stadtgrün, Umwelt und Klima": _ELEVEN,
    "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit": _ELEVEN,
    "Kulturausschuss": _ELEVEN,
    "Sportausschuss": _ELEVEN,
    "Verkehrsausschuss": _ELEVEN,
    "Betriebsausschuss Abfallwirtschaftsbetrieb": Composition(
        6, (("Vertreterinnen und Vertreter der Beschäftigten", 3),),
        source="Vorlagen 26/0795 und 26/0783"),
    "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau": Composition(
        11, (("Vertreterinnen und Vertreter der Beschäftigten", 3),),
        source="Vorlagen 26/0795 und 26/0800"),
    "Jugendhilfeausschuss": Composition(
        6, (("in der Jugendhilfe erfahrene Personen", 3),
            ("Mitglieder auf Vorschlag der freien Träger der Jugendhilfe", 6)),
        remark="Die drei in der Jugendhilfe erfahrenen Personen benennen Grüne, SPD und Linke "
               "(je eine).",
        source="Vorlage 26/0784"),
    "Schulausschuss": Composition(
        11, (("Lehrkräfte", 2), ("Schülerinnen und Schüler", 2), ("Eltern", 2)),
        conditional=(("eine Vertretung der Arbeitgeberverbände", 1),
                     ("eine Vertretung der Arbeitnehmerverbände", 1)),
        conditional_when="In Angelegenheiten der berufsbildenden Schulen",
        source="Vorlage 26/0789"),
}


def _norm(name: str) -> str:
    return " ".join(name.split()).casefold()


_BY_NAME = {_norm(k): v for k, v in COMPOSITION.items()}


def composition_for(committee: str) -> Composition | None:
    """Die beschlossene Zusammensetzung eines Gremiums — oder ``None``."""
    return _BY_NAME.get(_norm(committee))


def sainte_lague(strengths: dict[str, int], seats: int) -> tuple[dict[str, int], tuple[str, ...], int]:
    """Sitzverteilung nach Sainte-Laguë/Schepers (§ 71 Abs. 2 NKomVG n. F.).

    Höchstzahlen = Mitgliederzahl geteilt durch 0,5; 1,5; 2,5 …; die ``seats``
    größten bekommen je einen Sitz. Rückgabe: ``(sichere Sitze, Gleichstand,
    offene Sitze)`` — treffen an der Grenze mehrere gleiche Höchstzahlen
    aufeinander, entscheidet das Los: ``offen`` Sitze gehen dann an ebenso
    viele aus ``Gleichstand``, und welche das sind, steht nicht fest.
    """
    if seats <= 0 or not strengths:
        return {}, (), 0
    numbers = sorted(((Fraction(2 * n, 2 * i + 1), key)
                      for key, n in strengths.items() if n > 0 for i in range(seats)),
                     key=lambda x: x[0], reverse=True)
    if len(numbers) <= seats:
        sure: dict[str, int] = {}
        for _, key in numbers:
            sure[key] = sure.get(key, 0) + 1
        return sure, (), 0
    edge = numbers[seats - 1][0]
    sure = {}
    for value, key in numbers:
        if value > edge:
            sure[key] = sure.get(key, 0) + 1
    tied = tuple(key for value, key in numbers if value == edge)
    open_ = seats - sum(sure.values())
    if len(tied) == open_:            # kein Los nötig: alle an der Grenze kommen zum Zug
        for key in tied:
            sure[key] = sure.get(key, 0) + 1
        return sure, (), 0
    return sure, tied, open_
