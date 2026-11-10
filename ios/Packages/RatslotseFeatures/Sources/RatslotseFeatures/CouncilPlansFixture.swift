#if DEBUG
/// Sichtprobe ohne Konto und ohne Backend (`RATSLOTSE_DEBUG_ANALYSIS_FIXTURE=1`,
/// dazu `RATSLOTSE_DEBUG_FEATURES=plaene`). Gekürzte ECHTE Antworten vom 10.11.2026 —
/// als JSON, damit die Sichtprobe denselben Decoder durchläuft wie der Server-Weg.
enum CouncilPlanFixture {
    static let overview = #"""
{
 "as_of_label": "10.11.2026",
 "count": 43,
 "groups": [
  {
   "key": "running",
   "label": "Laufend",
   "plans": [
    {
     "key": "klimaschutzplan_2035",
     "title": "Klimaschutzplan Oldenburg 2035",
     "kicker": "Klima & Umwelt · beschlossen 12/2022 · bis 2035",
     "status_label": "läuft",
     "report_note": null,
     "report_state": {
      "state": "reported",
      "label": "Berichtet",
      "hint": null
     },
     "status_brief": {
      "as_of": "2026",
      "as_of_label": "2026",
      "origin_label": "Klimaportal der Stadt",
      "total": 97,
      "complete": true,
      "counts": [
       {
        "status_raw": "Neu/Noch nicht begonnen",
        "status_norm": "open",
        "count": 0
       },
       {
        "status_raw": "Zuordnung Amt",
        "status_norm": "started",
        "count": 10
       },
       {
        "status_raw": "Planung",
        "status_norm": "started",
        "count": 15
       },
       {
        "status_raw": "Umsetzungsreif",
        "status_norm": "started",
        "count": 9
       },
       {
        "status_raw": "In Umsetzung",
        "status_norm": "in_progress",
        "count": 34
       },
       {
        "status_raw": "Realisiert",
        "status_norm": "done",
        "count": 20
       },
       {
        "status_raw": "Ein-/Zurückgestellt",
        "status_norm": "paused",
        "count": 9
       }
      ]
     },
     "measure_count": 90
    },
    {
     "key": "waermeplan",
     "title": "Oldenburger Wärmeplan",
     "kicker": "Klima & Umwelt · beschlossen 06/2026",
     "status_label": "läuft",
     "report_note": "Seit dem Beschluss 06/2026 noch kein Bericht im Rat.",
     "report_state": {
      "state": "not_yet_due",
      "label": "Noch kein Bericht fällig",
      "hint": "Überprüfung laut Plan 06/2031."
     },
     "status_brief": {
      "as_of": "2026-03",
      "as_of_label": "03/2026",
      "origin_label": "Nach Angaben der Verwaltung",
      "total": 18,
      "complete": false,
      "counts": [
       {
        "status_raw": "in Umsetzung",
        "status_norm": "in_progress",
        "count": 6
       }
      ]
     },
     "measure_count": 18
    },
    {
     "key": "agenda_2025_alter",
     "title": "Agenda 2025 „Selbstbestimmt und mittendrin!“ – altersgerechtes Oldenburg",
     "kicker": "Soziales · beschlossen 06/2025",
     "status_label": "läuft",
     "report_note": "Kein Umsetzungsbericht im Rat seit dem Beschluss.",
     "report_state": {
      "state": "not_yet_due",
      "label": "Noch kein Bericht fällig",
      "hint": "Überprüfung laut Plan 2028."
     },
     "status_brief": null,
     "measure_count": 26
    }
   ]
  },
  {
   "key": "ended",
   "label": "Abgelaufen oder abgelöst",
   "plans": [
    {
     "key": "smv2025",
     "title": "Strategieplan Mobilität und Verkehr smv2025",
     "kicker": "Verkehr · beschlossen 08/2018 · bis 2025",
     "status_label": "abgelöst",
     "report_note": null,
     "report_state": {
      "state": "continued",
      "label": "Fortgeschrieben",
      "hint": null
     },
     "status_brief": {
      "as_of": "2023-10",
      "as_of_label": "10/2023",
      "origin_label": "Nach Angaben der Verwaltung",
      "total": 112,
      "complete": true,
      "counts": [
       {
        "status_raw": "Umgesetzt",
        "status_norm": "done",
        "count": 40
       },
       {
        "status_raw": "in Umsetzung",
        "status_norm": "in_progress",
        "count": 35
       },
       {
        "status_raw": "in Planung",
        "status_norm": "started",
        "count": 11
       },
       {
        "status_raw": "Vorüberlegungen",
        "status_norm": "started",
        "count": 15
       },
       {
        "status_raw": "noch nicht begonnen",
        "status_norm": "open",
        "count": 2
       },
       {
        "status_raw": "nicht umgesetzt / aufgegeben",
        "status_norm": "paused",
        "count": 9
       }
      ]
     },
     "measure_count": 112
    }
   ]
  }
 ],
 "follow_ups": [
  {
   "key": "abfallwirtschaftskonzept",
   "title": "Abfallwirtschaftskonzept 2022–2027",
   "fact": "Kein Umsetzungsbericht im Rat seit dem Beschluss.",
   "question": "Was ist aus dem Plan „Abfallwirtschaftskonzept 2022–2027“ geworden? Gibt es einen Bericht zum Stand der Umsetzung?"
  },
  {
   "key": "gewerbeflaechenkonzept",
   "title": "Gewerbeflächenentwicklungskonzept 2018",
   "fact": "Kein Umsetzungsbericht im Rat seit dem Beschluss.",
   "question": "Was ist aus dem Plan „Gewerbeflächenentwicklungskonzept 2018“ geworden? Gibt es einen Bericht zum Stand der Umsetzung?"
  }
 ],
 "follow_up_caveat": "Nichtöffentliche Sitzungen, Mitteilungen ohne Vorlage und Berichte außerhalb des Ratsinformationssystems sieht Ratslotse nicht. „Nicht gefunden“ heißt nicht „gibt es nicht“."
}
"""#

    static let detail = #"""
{
 "key": "waermeplan",
 "title": "Oldenburger Wärmeplan",
 "office": "Amt für Klimaschutz und Mobilität",
 "kicker": "Klima & Umwelt · beschlossen 06/2026",
 "status_label": "läuft",
 "group": "running",
 "note": null,
 "horizon_note": "Überprüfung spätestens nach fünf Jahren (§ 25 WPG)",
 "review_label": "06/2031",
 "adoption": {
  "date": "2026-06-01",
  "committee": "Rat",
  "mode": "adopted",
  "label": null,
  "template_number": "26/0236",
  "kvonr": 29685,
  "url": "https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=29685",
  "decision_id": 8683,
  "outcome": "accepted",
  "vote": "majority"
 },
 "website": "https://klimaportal.oldenburg.de/kwp",
 "since": {
  "label": "Seit dem Beschluss",
  "value": "5 Monate"
 },
 "remaining": null,
 "report_state": {
  "state": "not_yet_due",
  "label": "Noch kein Bericht fällig",
  "hint": "Überprüfung laut Plan 06/2031."
 },
 "report_note": "Seit dem Beschluss 06/2026 noch kein Bericht im Rat.",
 "report_caveat": null,
 "report_count": 0,
 "measures": {
  "count": 18,
  "count_city": 18,
  "count_note": null,
  "status_count": 6,
  "status_as_of_label": "03/2026",
  "status_template": "26/0236",
  "status_by_model": false,
  "source": {
   "label": "Abschlussbericht Kommunale Wärmeplanung, Tabelle 7",
   "template_number": "26/0236",
   "document_id": 306748,
   "url": "https://buergerinfo.oldenburg.de/getfile.php?id=306748&type=do",
   "as_of": "2026-03-23",
   "as_of_label": "23.03.2026"
  },
  "groups": [
   {
    "field": "Kommunikation",
    "measures": [
     {
      "code": "K1",
      "title": "Kommunikation und Aktivierung Oldenburger Wärmewende",
      "package": null,
      "page": 122,
      "status_raw": "in Umsetzung",
      "status_norm": "in_progress",
      "status_quote": null,
      "decision_count": 0
     },
     {
      "code": "K2",
      "title": "Beratungsangebote Oldenburger Wärmewende",
      "package": null,
      "page": 122,
      "status_raw": "in Umsetzung",
      "status_norm": "in_progress",
      "status_quote": null,
      "decision_count": 0
     },
     {
      "code": "K3",
      "title": "Klimapakt als Katalysator für die Wärmewende in Gewerbegebieten",
      "package": null,
      "page": 122,
      "status_raw": "in Umsetzung",
      "status_norm": "in_progress",
      "status_quote": null,
      "decision_count": 0
     }
    ]
   },
   {
    "field": "Organisation",
    "measures": [
     {
      "code": "O1",
      "title": "Kriterien zur Abwägung von Nutzungskonflikten auf städtischen Flächen",
      "package": null,
      "page": 122,
      "status_raw": null,
      "status_norm": null,
      "status_quote": null,
      "decision_count": 0
     },
     {
      "code": "O2",
      "title": "Integration der KWP in die Bauleitplanung und Stadtentwicklung",
      "package": null,
      "page": 122,
      "status_raw": null,
      "status_norm": null,
      "status_quote": null,
      "decision_count": 0
     },
     {
      "code": "O3",
      "title": "Initiierung einer Gesellschaft zur Umsetzung der Wärmewende",
      "package": null,
      "page": 122,
      "status_raw": null,
      "status_norm": null,
      "status_quote": null,
      "decision_count": 0
     }
    ]
   }
  ]
 },
 "city_status": {
  "as_of": "2026-03",
  "as_of_label": "03/2026",
  "origin_label": "Nach Angaben der Verwaltung",
  "total": 18,
  "complete": false,
  "counts": [
   {
    "status_raw": "in Umsetzung",
    "status_norm": "in_progress",
    "count": 6
   }
  ],
  "source_label": "Beschlussvorlage Oldenburger Wärmeplan",
  "source_url": null,
  "template_number": "26/0236",
  "confirmed": false,
  "movement": null,
  "series": [
   {
    "as_of": "2026-03",
    "as_of_label": "03/2026",
    "total": 18,
    "counts": [
     {
      "status_raw": "in Umsetzung",
      "status_norm": "in_progress",
      "count": 6
     }
    ]
   }
  ],
  "notes": [
   {
    "text": "Für die übrigen 12 Maßnahmen beschreibt die Vorlage ein Vorhaben und nennt keinen Stand.",
    "url": null
   }
  ]
 },
 "indicators": [],
 "review": null,
 "timeline": {
  "span": "2023–2026",
  "count": 7,
  "stations": [
   {
    "label": null,
    "mode": null,
    "date": "2023-12-14",
    "date_end": null,
    "kind": "preparation",
    "title": "Kommunale Wärmeplanung: Ergebnis Vergabeprozess - mündlicher Bericht",
    "template_number": null,
    "oral": true,
    "committees": [
     "Ausschuss für Stadtgrün, Umwelt und Klima"
    ],
    "decision_id": 6282,
    "members": [
     {
      "date": "2023-12-14",
      "committee": "Ausschuss für Stadtgrün, Umwelt und Klima",
      "decision_id": 6282
     }
    ]
   },
   {
    "label": null,
    "mode": null,
    "date": "2024-06-13",
    "date_end": null,
    "kind": "preparation",
    "title": "Kommunale Wärmeplanung: Stand - mündlicher Bericht",
    "template_number": null,
    "oral": true,
    "committees": [
     "Ausschuss für Stadtgrün, Umwelt und Klima"
    ],
    "decision_id": 6800,
    "members": [
     {
      "date": "2024-06-13",
      "committee": "Ausschuss für Stadtgrün, Umwelt und Klima",
      "decision_id": 6800
     }
    ]
   },
   {
    "label": null,
    "mode": null,
    "date": "2024-09-12",
    "date_end": null,
    "kind": "preparation",
    "title": "Kommunale Wärmeplanung: Bedarfs- und Potenzialanalyse - mündlicher Bericht",
    "template_number": null,
    "oral": true,
    "committees": [
     "Ausschuss für Stadtgrün, Umwelt und Klima"
    ],
    "decision_id": 6964,
    "members": [
     {
      "date": "2024-09-12",
      "committee": "Ausschuss für Stadtgrün, Umwelt und Klima",
      "decision_id": 6964
     }
    ]
   }
  ]
 },
 "decision_groups": [
  {
   "key": "plan",
   "label": "Beschließt oder ändert den Plan",
   "entries": [
    {
     "title": "Kommunale Wärmeplanung (KWP): Oldenburger Wärmeplan - Beschluss",
     "date": "2026-06-01",
     "committee": "Rat",
     "decision_id": 8683,
     "outcome": "accepted",
     "template_number": "26/0236",
     "deliberations": 2,
     "measure_codes": [],
     "quote": null
    }
   ]
  },
  {
   "key": "motion",
   "label": "Antrag oder Anfrage dazu",
   "entries": [
    {
     "title": "Bericht zur kommunalen Wärmeplanung (Fraktion Bündnis 90/Die Grünen und SPD-Fraktion vom 25.08.2022)",
     "date": "2022-09-15",
     "committee": "Ausschuss für Stadtplanung und Bauen",
     "decision_id": 5051,
     "outcome": "noted",
     "template_number": null,
     "deliberations": 1,
     "measure_codes": [],
     "quote": null
    },
    {
     "title": "Bericht zur kommunalen Wärmeplanung (Fraktion Bündnis 90/Die Grünen und SPD-Fraktion vom 25.08.2022) - mündlicher Bericht",
     "date": "2022-09-08",
     "committee": "Ausschuss für Stadtgrün, Umwelt und Klima",
     "decision_id": 4947,
     "outcome": "noted",
     "template_number": null,
     "deliberations": 1,
     "measure_codes": [],
     "quote": null
    }
   ]
  }
 ],
 "predecessor": null,
 "successor": null
}
"""#
}
#endif
