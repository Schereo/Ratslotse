"""Erzeugt die lokale Lesefassung aus der geprüften Markdown-Datei."""
from pathlib import Path
from html import escape
import json
import re
import shutil

from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
REPO = HERE.parents[2]
md = MarkdownIt("commonmark", {"html": False}).enable("table")
report = (SOURCE / "stichwahl-prueffassung.md").read_text()
parts = re.split(r"^## (.+)$", report, flags=re.M)
sections = {int(parts[i].split(".")[0]): parts[i + 1].strip() for i in range(1, len(parts), 2)}
short_parts = re.split(r"^## (.+)$", (HERE / "lesefassung.md").read_text(), flags=re.M)
short_sections = {int(short_parts[i].split(".")[0]): short_parts[i + 1].strip() for i in range(1, len(short_parts), 2)}
labels = {
    2: ("teilnahme", "Teilnahme", "49.522 Menschen haben nicht gewählt"),
    3: ("ergebnis", "Ergebnis", "2.225 Stimmen Abstand im ersten Wahlgang"),
    4: ("prozent", "Prozentangaben", "Gleiche Stimmenzahl, anderer Prozentwert"),
    5: ("ratswahl", "Ratswahl", "Stimmen sind keine Personenzahl"),
    6: ("historie", "Historie", "Die Beteiligung kann sinken oder steigen"),
    7: ("einordnung", "Einordnung", "Was Annahmen leisten – und was offenbleibt"),
    8: ("briefwahl", "Briefwahl", "Unterlagen für die Stichwahl"),
}
city_url = "https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/wahlen/rats-oberbuergermeisterwahl-kommunalwahl/oberbuergermeisterwahl-2026/ob-wahl-entscheidung-faellt-am-27-september.html"
results_url = "https://votemanager.kdo.de/20260913/03403000/praesentation/ergebnis.html?id=ebene_-6360_id_10357&stimmentyp=0&wahl_id=2552"
source_notes = {
    2: f"Quelle: [Amtliche Ergebnisdaten 2026]({results_url}); Nichtteilnahme aus den Stadtgesamtwerten berechnet.",
    3: f"Quelle: [Ergebnis der OB-Wahl 2026]({results_url}).",
    4: f"Quelle: [Amtliche Ergebnisdaten 2026]({results_url}); Anteile selbst berechnet.",
    5: "Quellen: [Ratswahlergebnisse 2026](https://votemanager.kdo.de/20260913/03403000/praesentation/opendata.html) und [Wahlverfahren in Niedersachsen](https://landeswahlleiter.niedersachsen.de/wahlen/kommunalwahlen/grundzuege_kommunalwahlsystem/grundzuge-des-niedersachsischen-kommunalwahlsystems-252504.html).",
    6: "Quellen: [Stichwahl 2014](https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterstichwahl_NDS_52_Gemeinde_Stadt_Oldenburg_Oldenburg.html), [amtliches Ergebnis 2021](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20211001-2021-09-30_Bekanntmachung_Stichwahl_OB.pdf) und [Bundestagswahltermin 2021](https://www.bundeswahlleiterin.de/mitteilungen/bundestagswahlen/2021/20201214-wahltermin.html). Weitere Quellen in der Erläuterung.",
    7: "Grundlage: Umfang der verwendeten Ergebnisdateien. Die Einordnung der Studien und die Grenzen des Vergleichs stehen in der Erläuterung.",
    8: f"Quelle: [Aktuelle Hinweise der Stadt Oldenburg]({city_url}), geprüft am 16. September 2026.",
}
detail_labels = {
    2: "Zahl nachvollziehen: Urne, Briefwahl und Nichtteilnahme",
    3: "Stimmenmengen und ihre Grenzen nachvollziehen",
    4: "Bezugsgröße umschalten und Rechnung ansehen",
    5: "Wahljahr, Stimmenarten und Doppelzählung verstehen",
    6: "Frühere Ergebnisse und Veränderungen im Detail",
    7: "Methodische Grenzen und Forschung einordnen",
    8: "Hinweise zum Verfahren nachlesen",
}


def render(value):
    result = md.render(value)
    result = result.replace('<table>', '<div class="table-scroll" tabindex="0" role="region" aria-label="Tabelle, bei Bedarf seitlich scrollen"><table>')
    result = result.replace('</table>', '</table></div>')
    result = re.sub(r'<a href="(https?://[^"]+)"', r'<a target="_blank" rel="noopener noreferrer" href="\1"', result)
    return result


interactive = '''<div class="denominator">
  <fieldset><legend>Prozentangaben selbst nachvollziehen</legend>
    <div class="choices"><label><input type="radio" name="basis" value="alle" checked> Alle gültigen Stimmen</label>
    <label><input type="radio" name="basis" value="zwei"> Nur Prange und Rohr</label></div>
  </fieldset>
  <p class="hint" id="basis-hinweis">100 Prozent entsprechen allen gültigen Stimmen der jeweiligen Wahlart.</p>
  <div id="quoten" class="methods" aria-live="polite"></div>
</div>'''

articles = []
for number, (key, short, title) in labels.items():
    text = sections[number]
    # Die Abschnittsüberschrift ersetzt die redaktionelle Bausteinbezeichnung.
    text = re.sub(r'^\*\*[^\n]+\*\*\s*', '', text, count=1)
    text = text.replace('### Textbaustein für 2014', '### 2014: weniger Wählende')
    text = text.replace('### Textbaustein für 2021', '### 2021: mehr Wählende')
    text = text.replace(' Die zugehörigen CSVs stammen aus dem oben genannten Commit von PR #1385.', '')
    if number == 6:
        text = re.sub(r'(### [^\n]+\n\n)\*\*[^\n]+\*\*\n\n', r'\1', text)
    text = text.replace('Die gleiche Erklärung gehört an historische Zweieranteile. Ein Anteil im ersten Wahlgang, der andere Kandidaturen ausblendet, ist ausdrücklich als Anteil **unter den Stimmen für die beiden späteren Finalisten** zu kennzeichnen.', 'Auch historische Zweieranteile beziehen sich nur auf die Stimmen für die beiden späteren Finalisten. Andere Kandidaturen werden dabei ausgeblendet.')
    text = text.replace('Er ist nicht der reguläre Anteil an allen gültigen Stimmen.', 'Solche Zweieranteile unterscheiden sich von den Anteilen an allen gültigen Stimmen.')
    explanation = render(text)
    if number == 4:
        explanation = interactive + explanation
    body = render(short_sections[number])
    articles.append(f'''<section id="{key}" aria-labelledby="{key}-titel">
      <div class="section-label">{number-1:02d} · {escape(short)}</div>
      <h2 id="{key}-titel">{escape(title)}</h2>
      <div class="reading summary-copy">{body}</div>
      <div class="source-note">{render(source_notes[number])}</div>
      <details class="methodology"><summary>{escape(detail_labels[number])}</summary><div class="reading">{explanation}</div></details>
      <button class="copy" data-copy="{key}" type="button">Kernaussage kopieren</button>
    </section>''')

corrections = render(sections[1].split('Die Fundstellen')[0])
navigation = ''.join(f'<a href="#{k}">{escape(short)}</a>' for k, short, _ in labels.values())
html = f'''<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="color-scheme" content="light dark">
<title>Stichwahl · Zahlen verständlich erklärt</title>
<link rel="icon" href="logo-mark.png"><link rel="stylesheet" href="style.css?v=2"><script src="app.js?v=2" defer></script></head>
<body><a class="skip" href="#inhalt">Zum Inhalt</a>
<header class="topbar"><a href="#" class="brand"><img src="logo-mark.png" width="28" height="28" alt="">Ratslotse <span>· lokale Prüfansicht</span></a>
<div class="tools"><button id="theme" type="button" aria-pressed="false">Dunkelmodus</button><button id="print" type="button">Drucken</button></div></header>
<div class="shell"><aside><nav aria-label="Abschnitte"><p class="section-label">Die Analyse lesen</p>{navigation}<a href="#korrekturen">Korrekturen prüfen</a></nav></aside>
<main id="inhalt"><div class="hero"><p class="section-label">Oldenburg · OB-Wahl vom 13. September 2026</p>
<h1>Die Zahlen zur Stichwahl.<br><span>Verständlich eingeordnet.</span></h1>
<p class="intro">Was der erste Wahlgang zeigt und was frühere Stichwahlen erklären. Die wichtigsten Aussagen stehen direkt auf der Seite; Zahlen und Rechenwege lassen sich darunter aufklappen.</p>
<p class="hint">Vorläufiger, eingefrorener Ergebnisstand · Prüfung vom 16. September 2026</p>
<div class="summary"><div><strong>85.991</strong><span>Menschen haben gewählt</span><p>63,46 % der 135.513 Wahlberechtigten, einschließlich Briefwahl.</p></div>
<div><strong>49.522</strong><span>haben nicht teilgenommen</span><p>Wahlberechtigte abzüglich aller Wählenden der Stadt.</p></div></div></div>
<div class="overview" aria-label="Die wichtigsten Erkenntnisse"><p><strong>Der erste Wahlgang bleibt eine Momentaufnahme.</strong> Er zeigt den Stimmenabstand, aber keine späteren Wechselentscheidungen.</p><p><strong>Prozentwerte brauchen eine Bezugsgröße.</strong> 51,1 Prozent unter zwei Kandidaten sind etwas anderes als 51,1 Prozent aller gültigen Stimmen.</p><p><strong>Frühere Stichwahlen zeigen unterschiedliche Verläufe.</strong> Ein Rückgang der Beteiligung ist ebenso wenig vorgegeben wie ein Anstieg.</p></div>
{''.join(articles)}
<section id="korrekturen"><div class="section-label">Redaktionelle Prüfung</div><h2>Was gegenüber der bisherigen Fassung präziser wird</h2>
<details><summary>Die acht wichtigsten Korrekturen anzeigen</summary><div class="reading">{corrections}</div></details>
<p class="hint">Diese Ansicht setzt die unabhängige Prüffassung um. Sie ist eine separate lokale Vorschau.</p></section>
<footer><h2>Quellen und Nachrechnung</h2><p>Die Quellen stehen direkt bei den Erläuterungen. Prozentwerte sind gerundet; Stimmenzahlen stammen aus den eingefrorenen amtlichen Ergebnissen.</p>
<div class="downloads"><a href="lesefassung.md" download>Lesefassung als Markdown</a><a href="../stichwahl-prueffassung.md" download>Ausführliche Prüfung</a><a href="../stichwahl-faktencheck.json" download>Nachrechnung als JSON</a><a href="../stichwahl-faktencheck.py" download>Nachrechnung als Python</a></div>
<p class="hint">Auswertung öffentlicher Wahlergebnisse. Keine Umfrage und keine Prognose.</p></footer>
</main></div><div id="status" class="status" role="status" aria-live="polite"></div></body></html>'''
(HERE / 'index.html').write_text(html)
shutil.copyfile(REPO / 'web/frontend/public/logo-mark.png', HERE / 'logo-mark.png')
data = json.loads((SOURCE / 'stichwahl-faktencheck.json').read_text())
(HERE / 'data.js').write_text('window.wahlarten = ' + json.dumps(data['wahlarten_2026'], ensure_ascii=False) + ';\n')
index = (HERE / 'index.html').read_text().replace('<script src="app.js?v=2"', '<script src="data.js?v=2" defer></script><script src="app.js?v=2"')
(HERE / 'index.html').write_text(index)
print(HERE / 'index.html')
