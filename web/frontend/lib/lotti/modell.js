/* Lotti, die Lotsenmöwe — 3D-Modell aus den Werten von components/mascot.tsx.
   baueLotti(THREE) liefert eine THREE.Group mit benannten Teilen und Materialien.
   Maße in Metern, y-up, Standfläche auf y = 0, Gesamthöhe 23,1 cm.

   QUELLE DER WAHRHEIT: diese Datei (seit 28.08.2026). Entstanden ist das
   Modell im Claude-Design-Projekt „Design-Analyse und Verbesserungen" und
   wurde von dort kopiert; seit die Hand hier dazukam, ist der Rückweg
   aufgegeben. Änderungen an Lotti also HIER machen.

   Was das verlangt, weil kein Zweitexemplar mehr gegenliest:
   - Nach jedem Eingriff `node studio/katalog.mjs` — das Modell trägt ALLE
     Szenen, und eine Nebenwirkung sieht man nur im Vergleich aller.
   - Neue Körperteile zuschaltbar bauen (wie `hand`), nicht als neue
     Grundform: Was in jedem Bild erscheint, ändert die Figur.

   AUFBAU SEIT DEM 28.08.2026: Die Figur hat ein SKELETT (`skelett.js`).
   Erst kommt der Bauplan `SKELETTE`, dann hängt jedes Teil an einem
   Knochen — starr über `teil(name, geo, material, 'knochenname')` oder
   verformbar über `haut(name, geo, material, kette)`. Alle Geometrie steht
   dabei in FIGURENKOORDINATEN; den Sitz des Knochens zieht `teil()` ab.
   Wer sich das Ergebnis ansehen will: `node studio/knochen.mjs`. */

import { baueSkelett, hauteAn, glied, huelle } from './skelett.js';

/**
 * Eine Schnabelhälfte als Rotationsprofil.
 *
 * Vorher waren beide Hälften abgeflachte KUGELN — zwei Ovale übereinander,
 * die nirgends spitz zuliefen (Tims Befund 20.08.26). Ein Schnabel
 * verjüngt sich zur Spitze.
 *
 * Das Profil läuft von 0 (Wurzel) bis 1 (Spitze); der Radius bleibt
 * zunächst voll und fällt dann immer schneller ab — das ergibt die leicht
 * gebauchte Form eines Möwenschnabels statt eines geraden Kegels. Danach
 * wird in der Höhe gestaucht (ein Schnabel ist breiter als hoch) und die
 * Längsachse nach vorn gedreht.
 *
 * Lotti und die Küken teilen sich die Form, damit die Familie einen
 * Schnabel hat und nicht zwei verschiedene.
 */
function schnabelForm(THREE, laenge, breite, dicke) {
  const g = new THREE.LatheGeometry([
    [0.00, 0.00], [0.97, 0.03], [1.00, 0.14], [0.97, 0.32],
    [0.88, 0.50], [0.73, 0.67], [0.54, 0.81], [0.32, 0.92],
    [0.13, 0.98], [0.00, 1.00],
  ].map(([r, t]) => new THREE.Vector2(r * breite, t * laenge)), 30);
  g.scale(1, 1, dicke / breite);         // vor dem Drehen: Höhe stauchen
  g.rotateX(Math.PI / 2);                // Längsachse zeigt nach vorn (+z)
  return g;
}

/**
 * Ein Schnabelprofil VON HINTEN NACH VORN AUFKEILEN.
 *
 * Der Rachen hatte zuerst die Verjüngung eines Schnabels — hinten dick,
 * vorn spitz. Die Lücke zwischen den Hälften ist aber genau andersherum:
 * am Drehpunkt null, nach vorn immer weiter. Dadurch stand er hinten über
 * der Kinnlade und las sich von der Seite als DRITTER Schnabel (Tims
 * Befund 20.08.26).
 *
 * Hier wird nur die HÖHE mit dem Abstand vom Gelenk skaliert; Breite und
 * Umriss bleiben die des Schnabels, damit der Rachen seitlich nie unter
 * ihm hervorschaut. Ergebnis: hinten flach auf der Kinnlade aufliegend,
 * nach vorn so weit öffnend wie der Schnabel selbst.
 */
function keilen(geo, laenge) {
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const z = pos.getZ(i);
    pos.setY(i, pos.getY(i) * Math.min(Math.max(z / laenge, 0), 1));
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
}

/**
 * Einen Körper zu EINEM Ende hin verjüngen.
 *
 * Für die Handfläche: Ohne Verjüngung endet sie als Klotz, an dem die
 * Finger zu kleben scheinen (Tims Befund 27.08.26). Verjüngt wächst der
 * Ballen in die Finger hinein, so wie EVEs Hand in Wall-E — dort ist der
 * Handrücken vorn schmaler als am Gelenk.
 *
 * ``anteil`` ist die Restbreite am schmalen Ende (0,55 = 55 %).
 */
function verjuengen(geo, anteil, nachUnten = true) {
  geo.computeBoundingBox();
  const { min, max } = geo.boundingBox;
  const spanne = max.y - min.y || 1;
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const t = (pos.getY(i) - min.y) / spanne;          // 0 unten … 1 oben
    const f = anteil + (1 - anteil) * (nachUnten ? t : 1 - t);
    pos.setX(i, pos.getX(i) * f);
    pos.setZ(i, pos.getZ(i) * f);
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
}

/**
 * MASSE — die Zahlen, die etwas BEDEUTEN.
 *
 * Diese Datei hat rund 220 Zahlenkonstanten; die meisten sind Kurvenpunkte
 * eines Profils und in ihrer Reihe besser aufgehoben als unter einem Namen
 * („der vierte Punkt der Schnabelkurve" heißt nichts). Hier stehen die
 * anderen: Maße, die
 *
 *   ① an mehr als einer Stelle gebraucht werden,
 *   ② von außen gebraucht werden (Anker, Inverse Kinematik, Prüfungen), oder
 *   ③ die Proportion tragen — wo ein Name aus einem Diff eine Aussage macht.
 *     „fingerLaenge: 0,0250 → 0,0300" liest sich; „0.0250 → 0.0300" nicht.
 *
 * Alles in Metern, y-up. Wer hier etwas ändert, lässt danach
 * `node studio/pruefen-modell.mjs` und `node studio/katalog.mjs` laufen.
 */
/**
 * Stand des Modells — wandert in die Metadaten jedes gerenderten PNG
 * (`render.mjs`), damit sich jedes Bild auf seinen Modellstand
 * zurückführen lässt. Bei einer Formänderung mitziehen.
 *
 * Der Fingerabdruck daneben rechnet sich selbst aus (siehe
 * `fingerabdruck()`) und verrät auch die Änderung, die jemand hier zu
 * stempeln vergisst.
 */
export const MODELL_VERSION = '2026-08-28';

export const MASSE = {
  /**
   * Gesamthöhe der stehenden Figur (Standfläche auf y = 0), GENAU gemessen.
   *
   * Hier stand bis zum 28.08.26 „0.24", und die Prüfung ließ 2 cm
   * Abweichung durchgehen — sie hätte also auch eine um anderthalb
   * Zentimeter gewachsene Figur nicht bemerkt. Der Wert kam aus der groben
   * Bounding-Box, die bei der schräg sitzenden Mütze 1 cm zu hoch ausfällt.
   * Genau gemessen sind es 23,1 cm; die Prüfung nimmt jetzt 2 mm.
   */
  hoehe: 0.2313,

  rumpf: {
    /** Grundradius der Ei-Silhouette vor dem Formen. */
    radius: 0.0630,
    /** Vorne–hinten minimal tiefer als breit. */
    tiefe: 1.02,
  },

  kopf: {
    /** Drehpunkt des Kopfgelenks: unter dem Schnabel, wo beim Vogel der
     * Hals ansitzt. Höher sähe Neigen aus wie ein rutschendes Gesicht. */
    drehpunkt: 0.095,
  },

  schulter: {
    /** Lage des Schultergelenks (x wird gespiegelt). 1,2 cm tiefer als in
     * der ersten Fassung: Bei y = 0,148 wuchsen die Arme optisch aus dem
     * Kopf, und gehobene Flügel stießen schon bei 55° an den Hut. */
    x: 0.0700, y: 0.1360, z: 0.0020,
  },

  arm: {
    /** Radius der Kugel, aus der der Federkörper skaliert wird. */
    radius: 0.0445,
    /** Skalierung dieser Kugel: schmal, lang, mitteltief. Die 1,13 in y
     * war 1,06 — auf einem kurzen Flügel hat ein Knick keinen Platz. */
    skala: [0.26, 1.13, 0.80],
    /** Mittelpunkt im Schulterrahmen. */
    mitte: [0.0842, 0.0863, 0.0015],
    /** Neigung der Armachse gegen die Senkrechte (rad). Dieselbe Zahl
     * steht in den Ellbogen-Kennwerten und muss dort mitwandern. */
    neigung: 0.15,
    /** Verdrehung nach vorn (rad). */
    drall: 0.12,
    /**
     * Reichweite ab Schultermitte bis zur Handmitte, am NEUTRAL gebauten
     * Modell gemessen. Nicht frei wählbar: Sie folgt aus Radius × Skala
     * und dem Sitz der Hand; `pruefen-modell.mjs` misst nach.
     *
     * Die 94 mm, die bis 28.08.26 im README standen, waren an einer
     * gebeugten Pose abgegriffen — ein gebeugter Arm reicht kürzer. Die
     * Prüfung hat den Irrtum beim ersten Lauf gefunden.
     */
    reichweite: 0.1027,
  },

  hand: {
    /** Ansatz der Fingerreihe im Schulterrahmen. z = 0,0015 ist die
     * MITTELEBENE des Armkörpers — die Reihe saß bis 27.08.26 auf
     * −0,0045 und damit sichtbar neben der Achse. */
    ansatz: { x: 0.0816, y: 0.0530, z: 0.0015 },
    /** Seitlicher Abstand der Finger voneinander. */
    abstand: 0.0086,
    /** Wie viel tiefer die äußeren Finger ansetzen (Rundung des Armendes). */
    absenkung: 0.0030,
    /** Unsichtbarer Kern, an dem Ellbogen und Anker hängen, wenn die Hand
     * gebaut ist — das Mesh `fluegelspitze-<seite>` muss existieren. */
    kernRadius: 0.006,
  },

  finger: {
    /** Länge des mittleren Fingers; die äußeren sind kürzer (Faktoren
     * unten in der Reihe). Rund die Hälfte steckt im Arm. */
    laenge: 0.0400,
    /** Radius am Fuß und an der Kuppe — der Kegel dazwischen. */
    fussRadius: 0.0082,
    kuppeRadius: 0.0046,
  },

  /** Die geschlossene Flügelspitze OHNE Hand (`hand`-Option aus). */
  spitze: {
    radius: 0.0205,
    skala: [0.30, 0.92, 1.05],
    mitte: [0.0818, 0.0419, -0.0135],
  },
};

/**
 * DIE SKELETTE — je Figur `[name, elternteil, ruhelage]`.
 *
 * Seit 28.08.2026 haben Lotti und die Küken echte Knochen (`THREE.Bone`)
 * statt benannter Gruppen. Die NAMEN sind bewusst die alten: Wer
 * `schulter-links` dreht, dreht weiterhin den linken Arm — Posen, Gefühle,
 * Anker und die Inverse Kinematik haben davon nichts gemerkt. Neu ist,
 * was dabei mitgeht: das Armgeflecht biegt sich jetzt, statt nur seine
 * Aufhängung zu drehen.
 *
 * Die Ruhelage steht ABSOLUT in Figurenkoordinaten. So ist sie nachmessbar
 * („die Schulter sitzt auf 13,6 cm"); `baueSkelett` rechnet in relative
 * Positionen um.
 *
 * WAS NEU HINZUKAM, und warum:
 *
 *   becken / bauch / brust   Die Wirbelsäule, die es nie gab. Lotti konnte
 *                            sich nicht setzen, bücken oder lehnen — es gab
 *                            zwischen Fuß und Kopf kein einziges Gelenk.
 *                            Alle Posen waren Stehposen, weil es keine
 *                            andere geben KONNTE (Tims Frage 28.08.26 nach
 *                            der Sandkiste).
 *   finger-<seite>-<i>       Krümmbare Finger. Die Hand vom 27.08. war
 *                            starr; drei Kegel, die man nur als Ganzes
 *                            bewegen konnte.
 *   kueken-ellbogen-*        Küken hatten keinen. Ihre Flügel schwenkten
 *                            als Paddel, weshalb drei spielende Küken
 *                            aussahen wie dreimal dasselbe Küken.
 */
export const SKELETTE = {
  lotti: [
    /* Die Wurzel steht auf dem Boden — der Griff für die ganze Figur und
       der einzige Knochen, der nichts verformt. */
    ['wurzel',              null,      [0, 0, 0]],

    ['becken',              'wurzel',  [0, 0.030, 0]],
    ['bauch',               'becken',  [0, 0.072, 0]],
    ['brust',               'bauch',   [0, 0.110, 0]],

    /* DER HALS — nachgerüstet am 28.08.26, weil die Haut Falten warf.
       Vorher ging die ganze Kopfneigung auf EIN Gelenk, und die Eiform
       musste den vollen Winkel auf einem einzigen Übergang aufnehmen: Im
       Bild lief eine harte Kante quer über den Bauch (Tims Befund).
       Jetzt teilen sich `hals` und `kopf` die Neigung je zur Hälfte
       (`HALS_ANTEIL` in `szene.mjs`), und weil beide ihren eigenen
       Übergang haben, ist der Knick an jedem halb so groß.

       Der Hals dreht nur die HAUT mit; das Gesicht hängt weiter am
       `kopf`. Dessen Drehpunkt bleibt bei 9,5 cm — er ist der Wert, mit
       dem das Kopfneigen seit dem 19.08.26 gut aussieht, und er ist mit
       Absicht tief. */
    ['hals',                'brust',   [0, 0.145, 0]],
    ['kopf',                'hals',    [0, MASSE.kopf.drehpunkt, 0]],
    ['schnabel-gelenk',     'kopf',    [0, 0.1268, 0.0600]],
    ['auge-gelenk-links',   'kopf',    [0.0332, 0.1478, 0.0650]],
    ['auge-gelenk-rechts',  'kopf',    [-0.0332, 0.1478, 0.0650]],
    /* Die Mütze dreht um den FIGURENURSPRUNG, nicht um sich selbst — sie
       sitzt seit jeher mit `rotation.x = -0.085` auf einer Gruppe im
       Ursprung, und der lange Hebel bis zum Scheitel IST der schräge
       Sitz. Ein Knochen an ihrer eigenen Stelle würde sie aufrichten. */
    ['muetze',              'kopf',    [0, 0, 0]],

    ['schwanz-gelenk',      'bauch',   [0, 0.075, -0.030]],

    ['schulter-links',      'brust',   [MASSE.schulter.x, MASSE.schulter.y, MASSE.schulter.z]],
    ['ellbogen-links',      'schulter-links',  [0.0836, 0.0826, 0.0015]],
    /* DAS HANDGELENK, nachgerüstet am 29.08.26. Zwischen Ellbogen und
       Fingern gab es nichts — die Hand war Teil des Unterarms. Für alles,
       was aus dem Handgelenk kommt, fehlte damit das Gelenk: Winken ist
       eine Handbewegung, Jonglieren erst recht (Tims Beobachtung), und
       eine Requisite in der Hand ließ sich nur über den ganzen Arm
       ausrichten.

       Es sitzt dort, wo die Finger aus dem Flügel treten (6,2 cm), und
       trägt sie samt Flügelspitze. Damit die Haut mitgeht statt an der
       Naht aufzureißen, hat die Armkette jetzt ZWEI Übergänge — siehe
       `HAUT.armBeuge` und `HAUT.handBeuge`. */
    ['handgelenk-links',    'ellbogen-links',  [0.0820, 0.0620, 0.0015]],
    ['finger-links-0',      'handgelenk-links',  fingerSitz(1, -1)],
    ['finger-links-1',      'handgelenk-links',  fingerSitz(1, 0)],
    ['finger-links-2',      'handgelenk-links',  fingerSitz(1, 1)],
    ['schulter-rechts',     'brust',   [-MASSE.schulter.x, MASSE.schulter.y, MASSE.schulter.z]],
    ['ellbogen-rechts',     'schulter-rechts', [-0.0836, 0.0826, 0.0015]],
    ['handgelenk-rechts',   'ellbogen-rechts', [-0.0820, 0.0620, 0.0015]],
    ['finger-rechts-0',     'handgelenk-rechts', fingerSitz(-1, -1)],
    ['finger-rechts-1',     'handgelenk-rechts', fingerSitz(-1, 0)],
    ['finger-rechts-2',     'handgelenk-rechts', fingerSitz(-1, 1)],

    /* Die Füße hängen an der WURZEL, nicht am Becken: Wer sich bückt, hebt
       dabei nicht die Füße vom Boden. */
    ['fuss-gelenk-links',   'wurzel',  [0.0305, 0.0092, 0.0225]],
    ['fuss-gelenk-rechts',  'wurzel',  [-0.0305, 0.0092, 0.0225]],
  ],

  kueken: [
    ['wurzel',                    null,     [0, 0, 0]],
    /* Ein Küken ist eine Kugel von 6,8 cm; zwei Rumpfgelenke sind alles,
       was man daran sehen würde. */
    ['becken',                    'wurzel', [0, 0.018, 0]],
    ['brust',                     'becken', [0, 0.032, 0]],
    ['hals',                      'brust',  [0, 0.048, 0]],
    ['kopf',                      'hals',   [0, 0.030, 0]],
    ['kueken-auge-gelenk-links',  'kopf',   [0.0128, 0.0478, 0.0292]],
    ['kueken-auge-gelenk-rechts', 'kopf',   [-0.0128, 0.0478, 0.0292]],

    ['kueken-schulter-links',     'brust',  [0.0300, 0.0560, 0.0010]],
    ['kueken-ellbogen-links',     'kueken-schulter-links',  [0.0338, 0.0405, 0.0010]],
    ['kueken-schulter-rechts',    'brust',  [-0.0300, 0.0560, 0.0010]],
    ['kueken-ellbogen-rechts',    'kueken-schulter-rechts', [-0.0338, 0.0405, 0.0010]],

    ['fuss-gelenk-links',         'wurzel', [0.0128, 0.0032, 0.0053]],
    ['fuss-gelenk-rechts',        'wurzel', [-0.0128, 0.0032, 0.0053]],
  ],
};

/** Sitz eines Fingerknochens — dieselbe Rechnung, die die Fingergeometrie
 *  verschiebt. Beide aus einer Quelle, sonst laufen sie auseinander. */
function fingerSitz(v, fach) {
  return [v * MASSE.hand.ansatz.x,
          MASSE.hand.ansatz.y - Math.abs(fach) * MASSE.hand.absenkung,
          MASSE.hand.ansatz.z + fach * MASSE.hand.abstand];
}

/**
 * DIE HAUT — wo ein Teil sich VERFORMT statt getragen zu werden.
 *
 * Nur fünf Teile stehen hier: Lottis Rumpf und ihre beiden Arme, Körper
 * und Flügel des Kükens. Alles andere — Augen, Schnabel, Mütze, Füße,
 * Finger — ist ein starres Teil an einem Knochen. Das ist kein Sparen,
 * sondern die übliche Bauweise: Ein Auge verformt sich nicht, es wird
 * bewegt. Starre Teile behalten dadurch `visible` (der Hutwechsel in
 * `szene.mjs` schaltet die Mütze weiterhin einfach ab), ihr Material und
 * ihre einfache Bounding-Box.
 *
 * Die Zahlen sind Rampen ENTLANG einer Achse (siehe `hauteAn`): `bei` ist
 * der Anfang der Rampe, gemessen vom Ursprungsknochen, `breite` ihre
 * Länge. Für den Rumpf ist die Achse die Senkrechte.
 */
export const HAUT = {
  /* Rumpf: Becken → Bauch → Brust → Kopf. Der letzte Übergang ist der
     HALS, und er ist die folgenreichste Zahl dieser Datei. Bisher drehte
     ein geneigter Kopf nur Augen, Schnabel und Mütze; die Eiform darunter
     blieb stehen. Bei kleinen Winkeln fällt das nicht auf, bei großen
     rutscht das Gesicht über den Körper. Jetzt folgt die Eiform ab 12,5 cm
     zunehmend dem Kopf und ab 19 cm ganz. Wer den Effekt zurücknehmen
     will, schiebt `bei` nach oben — es ist genau eine Zahl. */
  lottiRumpf: {
    knochen: 'becken', ursprung: 'becken', achse: [0, 1, 0],
    /* GLEICH BREITE, SICH ÜBERLAPPENDE RAMPEN. Die erste Fassung hatte
       schmale, getrennte Rampen (3 cm, 2,8 cm) — und genau dort, wo eine
       endete, lief eine sichtbare Kante über den Körper. Bei linearer
       Mischhaut folgt die Normale dem Gewicht, nicht der wirklich
       gekrümmten Fläche; ein steiler Gewichtsverlauf wird deshalb als
       Falte gelesen, auch wenn die Fläche selbst stetig ist.

       Gleich breite, um je 3,5 cm versetzte Rampen ergeben eine glatte
       Zerlegung der Eins (wie eine B-Spline-Basis): An jeder Stelle
       teilen sich zwei bis drei Knochen den Punkt, und der Verlauf hat
       nirgends einen Knick. */
    uebergaenge: [
      { zu: 'bauch', bei: 0.015, breite: 0.055 },   // absolut  4,5 → 10,0 cm
      { zu: 'brust', bei: 0.050, breite: 0.055 },   // absolut  8,0 → 13,5 cm
      { zu: 'hals',  bei: 0.085, breite: 0.055 },   // absolut 11,5 → 17,0 cm
      { zu: 'kopf',  bei: 0.120, breite: 0.055 },   // absolut 15,0 → 20,5 cm
    ],
  },
  /* Küken: derselbe Aufbau, nur kürzer. Der Kopf greift bis ganz oben in
     die Kugel — bei dieser Figur IST die Kugel der Kopf. */
  kuekenRumpf: {
    knochen: 'becken', ursprung: 'becken', achse: [0, 1, 0],
    uebergaenge: [
      { zu: 'brust', bei: 0.008, breite: 0.024 },   // absolut 2,6 → 5,0 cm
      { zu: 'hals',  bei: 0.022, breite: 0.024 },   // absolut 4,0 → 6,4 cm
      { zu: 'kopf',  bei: 0.036, breite: 0.024 },   // absolut 5,4 → 7,8 cm
    ],
  },
  /** Übergangsbreite am Ellbogen. 2 cm ist die Zahl, die `armBeugen` in
   *  `szene.mjs` bis zum 28.08.26 von Hand gerechnet hat (`BEUGE_ZONE`) —
   *  sie war schon damals richtig, jetzt macht sie der Shader. */
  armBeuge: 0.020,
  /** Und am Handgelenk. Schmaler, weil zwischen Ellbogen und Hand nur
   *  zwei Zentimeter liegen — eine breitere Rampe griffe über den
   *  Ellbogen hinaus und weichte ihn auf. */
  handBeuge: 0.014,
  /** Dasselbe am kürzeren Kükenflügel. Nicht 1,2 cm: Das ergab auf einem
   *  4-cm-Flügel den steilsten Gewichtsverlauf der ganzen Figur (122 statt
   *  72 pro Meter beim Arm), und ein zugezogener Kükenellbogen hätte
   *  dieselbe Falte geworfen wie vorher der Bauch. */
  kuekenBeuge: 0.018,
};

/**
 * GRENZEN — was ein Gelenk darf, in Grad.
 *
 * Ohne sie ist jede Zahl erlaubt, und „hals: 90" dreht den Kopf um die
 * eigene Achse, während die Haut sich zu einem Trichter zieht. Die Grenzen
 * sind nicht geraten: Sie stehen mit Luft über dem, was alle vorhandenen
 * Posen, Gefühle und Szenen tatsächlich brauchen (nachgemessen am
 * 28.08.26 über alle 35 Szenen × 6 Posen × 8 Gefühle × 2 Figuren).
 * `pruefen-modell.mjs` misst das nach — wer eine Pose baut, die anstößt,
 * erfährt es, ohne das Bild anzusehen.
 *
 * Ein Eintrag gilt für BEIDE Seiten; `schulter-links` und
 * `schulter-rechts` teilen sich `schulter`, `finger-links-2` fällt unter
 * `finger`. Deshalb sind die Bereiche symmetrisch — ein Flügel hebt sich
 * links mit +150° und rechts mit −150°.
 *
 * `muetze` steht bewusst NICHT hier. Sie ist keine Anatomie, sondern eine
 * Aufhängung mit langem Hebel: Ihr Sitz entsteht gerade dadurch, dass sie
 * um den Figurenursprung kippt.
 */
export const GRENZEN = (() => {
  /* Was für beide Figuren gleich ist. */
  const gemeinsam = {
    becken:            { x: [-25, 45], y: [-30, 30], z: [-20, 20] },
    bauch:             { x: [-18, 30], y: [-24, 24], z: [-16, 16] },
    brust:             { x: [-25, 25], y: [-30, 30], z: [-20, 20] },
    hals:              { x: [-26, 26], y: [-32, 32], z: [-26, 26] },
    kopf:              { x: [-25, 25], y: [-38, 38], z: [-28, 28] },
    ellbogen:          { x: [-35, 35], y: [-50, 50], z: [-115, 115] },
    /* Ein Handgelenk kann weniger als ein Ellbogen und mehr als ein
       Finger. Die Werte sind die eines menschlichen Handgelenks, leicht
       gestutzt — mehr sähe an einem Flügel gebrochen aus. */
    handgelenk:        { x: [-40, 40], y: [-25, 25], z: [-70, 70] },
    finger:            { x: [-20, 85], y: [-14, 14], z: [-28, 28] },
    'fuss-gelenk':     { x: [-60, 35], y: [-35, 35], z: [-18, 18] },
    'schwanz-gelenk':  { x: [-35, 40], y: [-22, 22], z: [-22, 22] },
    'schnabel-gelenk': { x: [-4, 28], y: [-3, 3], z: [-3, 3] },
    'auge-gelenk':     { x: [-16, 16], y: [-18, 18], z: [-10, 10] },
  };
  return {
    /* Die Schulter ist NICHT symmetrisch und bei beiden Figuren anders —
       beides am 28.08.26 mit `gelenkprobe.mjs` nachgemessen. Der Anteil
       des Flügels, der im Rumpf steckt, über `schulter-links.z`:

         Lotti  −40°: 8 %   0°: 3 %   20…140°: 0–9 %   170°: 4 %
         Küken  −40°: 20 %  0°: 5 %   20…140°: 0–5 %   170°: 14 %

       Nach vorn und oben ist alles frei, nach HINTEN taucht der Flügel in
       den Rumpf — beim runden Küken doppelt so schnell wie bei Lotti.
       Schon bei −10° steckt ein Achtel des Flügels im Bauch, deshalb ist
       bei 0 Schluss: Der hängende Flügel ist die unterste Stellung, nach
       oben geht es fast ganz herum. */
    lotti: { ...gemeinsam,
      schulter: { x: [-55, 55], y: [-100, 100], z: [0, 170] } },
    kueken: { ...gemeinsam,
      /* Der Kükenflügel sitzt hoch an einer Kugel: Er stößt früher an. */
      schulter: { x: [-45, 45], y: [-60, 60], z: [0, 155] } },
  };
})();

/**
 * Grenzen eines Knochens — Figur und Seite eingerechnet.
 *
 * DIE SPIEGELUNG IST DER PUNKT. Die Tabelle notiert die LINKE Seite; für
 * die rechte werden die Bereiche um y und z umgeklappt (`[a, b]` wird
 * `[−b, −a]`), die um x bleiben. Das ist keine Konvention, sondern das,
 * was eine Spiegelung an der x-Achse mit Drehungen macht: Drehungen um
 * die Spiegelachse behalten ihr Vorzeichen, die anderen kehren es um.
 *
 * Vorher galt EIN symmetrischer Bereich für beide Seiten. Solange alle
 * Grenzen symmetrisch waren, fiel das nicht auf — bei der Schulter fällt
 * es sofort auf: Ein Flügel, der nach vorn 170° darf, darf nach hinten
 * eben nicht 170°, sondern 10°.
 */
export function grenzeFuer(figurName, knochenName) {
  const tabelle = GRENZEN[figurName] ?? GRENZEN.lotti;
  /* Reihenfolge zählt: erst die Nummer, dann die Seite. Andersherum
     bliebe aus „finger-links-2" ein „finger-links" übrig, für das es
     keinen Eintrag gibt — und die Finger wären stillschweigend
     unbegrenzt. */
  const stamm = knochenName
    .replace(/^kueken-/, '')
    .replace(/-\d+$/, '')
    .replace(/-(links|rechts)$/, '');
  const grenze = tabelle[stamm];
  if (!grenze) return null;
  if (!/-rechts(-\d+)?$/.test(knochenName)) return grenze;
  return {
    x: grenze.x,
    y: grenze.y && [-grenze.y[1], -grenze.y[0]],
    z: grenze.z && [-grenze.z[1], -grenze.z[0]],
  };
}

/**
 * ANKER — benannte Punkte AUF der Figur, an die Requisiten und Hüte hängen.
 *
 * Sie stehen hier und nicht mehr in `szene.mjs` (verschoben 28.08.2026):
 * Ein Anker beschreibt eine Stelle der Geometrie, und wer die Geometrie
 * ändert, muss den Anker im selben Blick haben. Getrennt konnte eine
 * Formänderung ihn still ungültig machen — `pruefen-modell.mjs` misst
 * jetzt zusätzlich nach, ob jeder Anker noch in seinem Teil liegt.
 *
 * `gelenk` heißt: Der Punkt hängt an diesem Gelenk und geht mit der Pose
 * mit; ohne `gelenk` sitzt er starr an der Figur.
 */
export const ANKER = {
  lotti: {
    kopf:              { offset: [0, 0.250, 0.010] },
    schnabel:          { offset: [0, 0.126, 0.098] },
    bauch:             { offset: [0, 0.068, 0.092] },
    scheitel:          { offset: [0, 0.176, 0.004] },
    'fluegel-links':   { gelenk: 'schulter-links',        offset: [0.082, -0.082, 0.010] },
    'fluegel-rechts':  { gelenk: 'schulter-rechts',       offset: [-0.082, -0.082, 0.010] },
  },
  kueken: {
    kopf:              { offset: [0, 0.102, 0.002] },
    schnabel:          { offset: [0, 0.036, 0.036] },
    scheitel:          { offset: [0, 0.074, 0.000] },
    'fluegel-links':   { gelenk: 'kueken-schulter-links',  offset: [0.008, -0.030, 0.004] },
    'fluegel-rechts':  { gelenk: 'kueken-schulter-rechts', offset: [-0.008, -0.030, 0.004] },
  },
  krabbe: {
    kopf:              { offset: [0, 0.075, 0.006] },
  },
};

/**
 * OPTIONEN — was `baueLotti(THREE, opt)` versteht.
 *
 * Vorher lagen die Abfragen (`opt.hand`, `opt.spreizung`, …) über die Datei
 * verstreut, und ein Tippfehler tat stillschweigend nichts: „spreizng: 20"
 * baute eine Hand mit geschlossenen Fingern, und man suchte den Fehler in
 * der Geometrie. Das Register prüft die Namen und dokumentiert sie an einer
 * Stelle.
 */
export const OPTIONEN = {
  augen: { werte: [undefined, 'zu', 'freude', 'weit', 'schmal'], vorgabe: undefined,
    was: 'zu = Lidbögen (Lidschlag), freude = Lachbögen nach oben, '
      + 'weit = aufgerissen, schmal = halb zugekniffen.' },
  /* DIE BRAUEN SIND DER GRÖSSTE HEBEL AM GESICHT. Ein Schnabel, der sich
     um einen Millimeter öffnet, ist auf 192 px unsichtbar; zwei schräge
     Striche über den Augen liest man sofort. Ohne sie kann kein Blick
     „traurig" heißen — er kann nur wegschauen (Tims Wunsch 29.08.26). */
  brauen: { werte: [undefined, 'traurig', 'boese', 'hoch', 'sorge', 'flach'],
    vorgabe: undefined,
    was: 'Form der Augenbrauen. Ohne Angabe hat Lotti keine — die neutrale '
      + 'Figur bleibt damit genau die, die sie war.' },
  traene: { werte: [undefined, 'links', 'rechts', 'beide'], vorgabe: undefined,
    was: 'Comic-Träne unter dem äußeren Augenwinkel.' },
  schweiss: { werte: [undefined, 'links', 'rechts'], vorgabe: undefined,
    was: 'Schweißtropfen an der Schläfe — Verlegenheit, Anstrengung.' },
  schnabel: { bereich: [0, 40], vorgabe: 0,
    was: 'Öffnung des Schnabels in Grad; ab etwa 8 wird der Rachen sichtbar.' },
  pose: { werte: [undefined, 'winkt'], vorgabe: undefined,
    was: 'Kürzel für eine gebaute Grundhaltung. Für Posen sonst posen.mjs.' },
  hand: { werte: [undefined, 'links', 'rechts', 'beide'], vorgabe: undefined,
    was: 'Teilt die Flügelspitze dieser Seite in Handfläche und drei Finger.' },
  spreizung: { bereich: [0, 40], vorgabe: 0,
    was: 'Fächerung der Finger in Grad, 0 = geschlossen (braucht hand).' },
  ton: { werte: [undefined, 'hell', 'dunkel'], vorgabe: undefined,
    was: 'Nur beim Küken: Gefieder-Abstufung.' },
};

/**
 * Unbekannte oder unzulässige Optionen sofort melden.
 *
 * Bewusst ein Fehler und keine Warnung: Eine stillschweigend ignorierte
 * Option ist genau der Fall, den man später in der Geometrie sucht.
 */
export function optionenPruefen(opt = {}, erlaubt = OPTIONEN) {
  for (const [name, wert] of Object.entries(opt)) {
    const regel = erlaubt[name];
    if (!regel) {
      const nah = Object.keys(erlaubt)
        .filter((k) => k.startsWith(name.slice(0, 3)))
        .join(', ');
      throw new Error(`Unbekannte Option „${name}"`
        + (nah ? ` — meintest du ${nah}?` : '')
        + ` (bekannt: ${Object.keys(erlaubt).join(', ')})`);
    }
    if (regel.werte && !regel.werte.includes(wert)) {
      throw new Error(`Option „${name}": ${JSON.stringify(wert)} ist nicht erlaubt `
        + `(${regel.werte.map((w) => JSON.stringify(w)).join(', ')})`);
    }
    if (regel.bereich && wert !== undefined) {
      const [von, bis] = regel.bereich;
      if (typeof wert !== 'number' || wert < von || wert > bis) {
        throw new Error(`Option „${name}": ${JSON.stringify(wert)} liegt außerhalb `
          + `von ${von}…${bis}`);
      }
    }
  }
  return opt;
}

const GRAD_HAND = Math.PI / 180;

export function baueLotti(THREE, opt = {}) {
  optionenPruefen(opt);
  const augenArt = opt.augen;                   // zu | freude | weit | schmal
  const augenZu = augenArt === 'zu' || augenArt === 'freude';
  const winkt   = opt.pose === 'winkt';         // rechter Flügel erhoben
  const schnabelAuf = opt.schnabel ?? 0;        // Öffnung, siehe Rachen unten
  const S = 0.0018;                       // SVG-Einheit (200×200) → Meter
  // Höhe des Kopf-Drehpunkts: unter dem Schnabel (y ≈ 0.123), wo bei einem
  // Vogel der Hals ansitzt. Weiter oben sähe die Neigung aus, als rutschte
  // das Gesicht; weiter unten kippt wieder der halbe Körper mit.
  const KOPF_DREHPUNKT = MASSE.kopf.drehpunkt;
  const TIEFE = MASSE.rumpf.tiefe;        // Rumpf vorne–hinten minimal tiefer als breit
  const V2 = (r, y) => new THREE.Vector2(r, y);

  const M = {
    koerper:   new THREE.MeshStandardMaterial({ name:'koerper-weiss',   color:'#FBFDFF', roughness:0.62, metalness:0.02 }),
    gefieder:  new THREE.MeshStandardMaterial({ name:'gefieder',        color:'#C7D6E4', roughness:0.72, metalness:0.02 }),
    spitze:    new THREE.MeshStandardMaterial({ name:'gefieder-spitze', color:'#8CA6BC', roughness:0.72, metalness:0.02 }),
    navy:      new THREE.MeshStandardMaterial({ name:'muetze-navy',     color:'#143A5C', roughness:0.55, metalness:0.05 }),
    navyTief:  new THREE.MeshStandardMaterial({ name:'muetze-dunkel',   color:'#0A1F33', roughness:0.32, metalness:0.10 }),
    /* Das Auge war EINFARBIG dunkel — eine glänzende Kugel mit weißem
       Reflex, ohne Pupille. Dadurch wirkte der Blick leblos und, schwerer
       wiegend, RICHTUNGSLOS: Wohin Lotti schaut, war nicht zu erkennen,
       weil sich nur der Glanzpunkt mitdrehte (Tims Befund 20.08.26).
       Jetzt ist `auge` die Iris und `pupille` der dunkle Kern darin.

       Die Iris war zuerst tiefblau (#27618F). Heller gelesen sie sich
       lebendiger, weil der Kontrast zur Pupille steigt — aber sie darf
       nicht ins Weiß des Rumpfs kippen, sonst verschwindet das Auge im
       Gesicht. #9FC4DC ist der Kompromiss; #D9E6F0 war zu nah am Körper. */
    auge:      new THREE.MeshStandardMaterial({ name:'iris',            color:'#9FC4DC', roughness:0.16, metalness:0.05 }),
    pupille:   new THREE.MeshStandardMaterial({ name:'pupille',         color:'#0A1520', roughness:0.14, metalness:0.05 }),
    /* Der Lidbogen des geschlossenen Auges braucht ein EIGENES Material.
       Er teilte es sich mit `auge` — und als die Iris hell wurde, waren
       die geschlossenen Augen plötzlich hellblau und im weißen Gesicht
       fast unsichtbar. Ein geschlossenes Auge ist eine dunkle Linie; der
       Ton ist deshalb der alte Augen-Farbwert von vor der Iris. */
    lid:       new THREE.MeshStandardMaterial({ name:'augenlid',        color:'#122A40', roughness:0.16, metalness:0.05 }),
    glanz:     new THREE.MeshStandardMaterial({ name:'auge-glanz',      color:'#FFFFFF', roughness:0.10, metalness:0.00, emissive:'#FFFFFF', emissiveIntensity:0.30 }),
    schnabel:  new THREE.MeshStandardMaterial({ name:'schnabel',        color:'#F66623', roughness:0.42, metalness:0.03 }),
    schnabelD: new THREE.MeshStandardMaterial({ name:'schnabel-dunkel', color:'#D9531E', roughness:0.46, metalness:0.03 }),
    gold:      new THREE.MeshStandardMaterial({ name:'gold',            color:'#F7CB63', roughness:0.28, metalness:0.38 }),
    wange:     new THREE.MeshStandardMaterial({ name:'wange',           color:'#FFAD85', roughness:0.85, metalness:0.00 }),
    rachen:    new THREE.MeshStandardMaterial({ name:'rachen',          color:'#873A2A', roughness:0.72, metalness:0.00 }),
    /* BRAUEN sind derselbe Ton wie ein geschlossenes Lid: eine dunkle
       Linie im weißen Gesicht. Heller gingen sie darin unter, und eine
       Braue, die man nicht sieht, ist keine. */
    braue:     new THREE.MeshStandardMaterial({ name:'braue',           color:'#122A40', roughness:0.30, metalness:0.04 }),
    /* Träne und Schweißtropfen teilen sich das Material — es ist derselbe
       Comic-Tropfen, nur an anderer Stelle. Leicht durchsichtig und ein
       wenig selbstleuchtend, sonst liest er sich als blauer Klecks statt
       als Wasser. */
    traene:    new THREE.MeshStandardMaterial({ name:'traene',          color:'#6FBEE6', roughness:0.06, metalness:0.00,
      transparent:true, opacity:0.90, emissive:'#4FA8DC', emissiveIntensity:0.28 }),
  };

  const lotti = new THREE.Group();
  lotti.name = 'lotti';

  /* Das Skelett zuerst — jedes Teil braucht seinen Knochen. */
  const { wurzel, skelett, knochen } = baueSkelett(THREE, SKELETTE.lotti);
  lotti.add(wurzel);
  lotti.userData.skelett = skelett;
  const gehaeutet = [];

  /* ALLE Geometrie steht ab hier in FIGURENKOORDINATEN — ein Punkt bei
     y = 0,148 liegt auf 14,8 cm über dem Boden, egal an welchem Knochen
     das Teil später hängt. Vorher trugen die Teile ihre Lage teils in der
     Geometrie und teils in `position`, und wer sie umhängte, verschob sie
     um den ganzen Drehpunkt (die Falle, die `gelenkUm` dreimal gestellt
     hat: beim Kopf fuhr das komplette Gesicht über die Mütze). Jetzt
     zieht `teil()` den Knochensitz genau einmal ab, an einer Stelle. */
  const teil = (name, geo, material, an = 'wurzel') => {
    const k = knochen.get(an);
    if (!k) throw new Error(`Teil „${name}": Knochen „${an}" gibt es nicht`);
    const m = new THREE.Mesh(geo, material);
    m.name = name;
    m.castShadow = true;
    m.receiveShadow = true;
    m.position.copy(k.absolut).negate();
    k.bone.add(m);
    return m;
  };

  /* Ein VERFORMBARES Teil: Es hängt an der Figur, nicht an einem Knochen,
     und jeder seiner Punkte folgt anteilig mehreren Knochen.
     `frustumCulled = false`, weil three die Sichtbarkeit an der Ruhelage
     misst — ein weit ausgestreckter Arm verschwände sonst am Bildrand. */
  const haut = (name, geo, material, kette) => {
    hauteAn(THREE, geo, kette, knochen);
    const m = new THREE.SkinnedMesh(geo, material);
    m.name = name;
    m.castShadow = true;
    m.receiveShadow = true;
    m.frustumCulled = false;
    lotti.add(m);
    gehaeutet.push(m);
    return m;
  };

  /* ── Rumpf: Ei-Silhouette aus der Zeichnung, unten für sicheren Stand abgeflacht ── */
  const koerperGeo = new THREE.LatheGeometry([
    V2(0, 0), V2(0.026, 0), V2(0.042, 0.005), V2(0.056, 0.012), V2(0.0684, 0.027),
    V2(0.0782, 0.045), V2(0.0855, 0.072), V2(0.0880, 0.1008), V2(0.0847, 0.126),
    V2(0.0774, 0.1512), V2(0.0652, 0.1764), V2(0.0456, 0.198), V2(0.0277, 0.2106),
    V2(0.0136, 0.2178), V2(0, 0.2196),
  ], 64);
  koerperGeo.scale(1, 1, TIEFE);
  haut('koerper', koerperGeo, M.koerper, HAUT.lottiRumpf);

  /* ── Schwanzfedern ── */
  const schwanz = new THREE.SphereGeometry(0.037, 28, 18);
  schwanz.scale(0.92, 0.26, 1.80);
  schwanz.rotateX(0.24);
  schwanz.translate(0, 0.0615, -0.0705);
  teil('schwanz', schwanz, M.gefieder, 'schwanz-gelenk');

  /* ── Flügel an einem Schultergelenk, damit sie sich heben und winken lassen ── */
  [['links', 1], ['rechts', -1]].forEach(([seite, v]) => {
    /* Die Schulter saß bei y = 0,148 — auf einer 0,22 m hohen Figur sind
     * das 67 % der Höhe, also direkt unter der Mützenkrempe. Die Arme
     * wuchsen dadurch optisch aus dem Kopf, und gehobene Flügel stießen
     * schon bei 55° an den Hut (Tims Befund 20.08.26). 1,2 cm tiefer.
     *
     * Der ganze Arm wandert mit: Weil die Geometrie unten mit `- py`
     * verschoben wird, bleibt jede relative Lage erhalten — es genügt,
     * dieselben 0,012 auch von den y-Werten der Teile abzuziehen. */
    const schulter = knochen.get('schulter-' + seite).bone;

    /* EIN Federkörper, der sich BIEGT — kein zweiter Körper daran.
     *
     * Zwei Anläufe waren falsch: Erst saß das Gelenk an der dunklen Spitze
     * (ein Handgelenk, kein Ellbogen), dann teilte ich den weißen Arm in
     * zwei Ellipsoide — und die sahen aus wie zwei Arme aneinander (Tims
     * Befund 20.08.26). Ein Ellipsoid läuft an beiden Enden spitz zu, jede
     * Überlappung zeigt deshalb eine Taille; eine Füllung dagegenzusetzen
     * erzeugte nur einen Knubbel wie an einer Actionfigur.
     *
     * Der Arm ist EIN Mesh und wird GEBOGEN. Bis zum 28.08.26 tat das
     * `armBeugen()` in `szene.mjs` von Hand — es drehte die Punkte
     * unterhalb des Ellbogens um ihn herum, mit weichem Übergang über zwei
     * Zentimeter. Seit die Figur ein Skelett hat, macht das die Haut:
     * derselbe Verlauf, aber als Gewicht am Ellbogenknochen (`HAUT.armBeuge`)
     * statt als Schleife über alle Punkte bei jeder Pose.
     *
     * Länge 1.20 statt 1.06: Auf einem kurzen Flügel hat ein Knick keinen
     * Platz. Die Mitte rutscht um den halben Zuwachs nach unten, damit die
     * Schulter bleibt, wo sie war. */
    const feder = new THREE.SphereGeometry(MASSE.arm.radius, 34, 26);
    feder.scale(...MASSE.arm.skala);
    feder.rotateZ(v * -MASSE.arm.neigung);
    feder.rotateY(v * MASSE.arm.drall);
    feder.translate(v * MASSE.arm.mitte[0], MASSE.arm.mitte[1], MASSE.arm.mitte[2]);
    haut('fluegel-' + seite, feder, M.gefieder,
         glied(knochen, ['schulter-' + seite, 'ellbogen-' + seite,
                         'handgelenk-' + seite],
               [HAUT.armBeuge, HAUT.handBeuge]));

    /* Die dunkle Spitze IST die Hand (siehe Ellbogen unten) — als
       geschlossenes Paddel kann sie aber nichts greifen: Eine Requisite
       daran liegt bestenfalls auf, und auf einem Standbild sieht Auflegen
       aus wie Schweben (Tims Befund 27.08.26).

       Mit `hand` wird sie zur Drei-Finger-Hand nach dem Vorbild von EVE
       aus Wall-E (Tims Verweis). Was daran nach mehreren Fehlversuchen
       zählt, in einem Satz: **eine Hand ist ein Körper, aus dem Finger
       wachsen — nicht ein Körper, an dem Finger kleben.** Konkret:

       - ALLES in der Armfarbe. Die dunkle Spitzenfarbe entfällt an einer
         Hand; hell/dunkel zeichnete genau die Fuge nach, die nicht da
         sein soll (Tims Befund: „losgelöst", „Ballen sitzt nicht am Arm").
       - Kaum eigene Handfläche: ein flacher Keil, der den Arm fortsetzt
         und in dem die Fingerwurzeln VERSCHWINDEN. Ein sichtbarer eigener
         Ballen las sich als Bohne unter den Fingern.
       - Finger als Kapseln (rund an beiden Enden), zur Kuppe verjüngt.
         Ellipsoide waren an den Enden spitz — Mandeln, keine Finger.
         Gleich dicke Kapseln wiederum lasen sich als Gabel; die
         Verjüngung macht den Unterschied.

       Zuschaltbar und nicht als neue Grundform, weil dieses Modell alle
       Szenen trägt: Wer keine Requisite hält, bekommt weiter das glatte
       Gefieder mit dunkler Spitze — eine Möwe mit Fingern in JEDEM Bild
       wäre eine andere Figur. */
    const greift = opt.hand === 'beide' || opt.hand === seite;
    const handTeile = ['fluegelspitze-' + seite];
    // Spreizung in Grad, gemessen vom Mittelfinger: 0 = geschlossen,
    // ~18 = gespreizte Hand. Sie dreht jeden Finger um SEINEN Fuß.
    const spreizung = (opt.spreizung ?? 0) * GRAD_HAND;

    if (!greift) {
      const spitze = new THREE.SphereGeometry(MASSE.spitze.radius, 26, 20);
      spitze.scale(...MASSE.spitze.skala);
      spitze.rotateZ(v * -0.30);
      spitze.rotateY(v * MASSE.arm.drall);
      spitze.translate(v * MASSE.spitze.mitte[0], MASSE.spitze.mitte[1],
                       MASSE.spitze.mitte[2]);
      teil('fluegelspitze-' + seite, spitze, M.spitze, 'handgelenk-' + seite);
    } else {
      /* KEIN eigener Handteller. Jeder Versuch — dunkel, hell, flach,
         verjüngt — endete als eigene Silhouette am Armende: eine Bohne,
         ein Sack, eine Knolle (Tims Befunde). Der Arm endet ohnehin
         rund; genau diese Rundung IST der Handrücken, und die Finger
         wurzeln direkt darin.

         Das Mesh `fluegelspitze` muss trotzdem existieren (Ellbogen und
         Anker greifen über den Namen darauf zu) — es steckt als winziger
         Kern unsichtbar im Armende. */
      const kern = new THREE.SphereGeometry(MASSE.hand.kernRadius, 10, 8);
      kern.translate(v * 0.0830, 0.0480, -0.0100);
      teil('fluegelspitze-' + seite, kern, M.gefieder, 'handgelenk-' + seite);

      /* Drei Finger aus der Vorderkante des Tellers, in seiner Ebene
         gespreizt. Mittelfinger am längsten; die äußeren folgen der
         Rundung der Kante — kürzer und einen Hauch tiefer. */
      /* Zur Hälfte im Arm: Nur die vordere Hälfte jedes Fingers steht
         heraus (Tims Vorgabe 27.08.26). Kurz und ganz draußen sahen sie
         aus wie aufgesteckt; halb versenkt liest sich der Übergang als
         Knöchel. Deshalb sind sie zugleich länger — von einer kurzen
         Kapsel bliebe sonst ein Stummel übrig. */
      [[-1, 0.84], [0, 1.0], [1, 0.78]].forEach(([fach, laenge], i) => {
        /* Kegel mit runder Kuppe: am Ansatz dick, nach vorn schlank,
           die Spitze abgerundet — Kapseln waren zu rund („Würste"), ein
           glatter Kegelstumpf zu eckig (Tims Befunde 27.08.26).

           Der Fuß muss IM Arm bleiben. Der Arm ist ein Ellipsoid und
           wird nach vorn dünn; ein zu dicker oder zu weit vorn gesetzter
           Fuß stach seitlich heraus. Deshalb sitzt der Ansatz weit
           hinten, wo der Arm noch Fleisch hat, und der Fuß ist schmaler
           als die dickste Stelle des Fingers wirken lässt. */
        const lg = MASSE.finger.laenge * laenge;
        const R = MASSE.finger.fussRadius, RK = MASSE.finger.kuppeRadius;
        // Die Verjüngung passiert überwiegend im verdeckten Drittel; was
        // herausschaut, soll kräftig sein und nicht als Dorn enden.
        const profil = [
          new THREE.Vector2(0, 0),
          new THREE.Vector2(R, 0),
          new THREE.Vector2(R * 0.97, lg * 0.38),
          new THREE.Vector2(R * 0.86, lg * 0.66),
          new THREE.Vector2(RK * 1.18, lg - RK * 1.5),
          new THREE.Vector2(RK, lg - RK * 0.7),
          new THREE.Vector2(RK * 0.64, lg - RK * 0.16),
          new THREE.Vector2(0, lg),
        ];
        const finger = new THREE.LatheGeometry(profil, 20);
        // Ursprung liegt am Fuß — die Spreizung dreht dort, sonst
        // rutscht der ganze Finger seitlich aus der Hand. Der Körper
        // zeigt in -y, also erst umdrehen.
        finger.rotateX(Math.PI);
        // Vorzeichen gegen den Reihen-Versatz: Positiv drehte die Spitzen
        // zur Mitte, die Finger verschmolzen (Tims Befund 27.08.26).
        finger.rotateX(-fach * spreizung);
        // Dieselbe Neigung wie der Unterarm (die Ellbogen-Achse notiert
        // sie als [0,1494·v / 0,9888 / 0], also 0,15 rad). Die Finger
        // erbten die 0,30 der alten Flügelspitze und standen dadurch
        // schräg zum Arm, statt ihn fortzusetzen (Tims Befund 27.08.26).
        finger.rotateZ(v * -MASSE.arm.neigung);
        finger.rotateY(v * MASSE.arm.drall);
        // Die Reihe sitzt MITTIG auf dem Armende: z 0,0015 ist die
        // Mittelebene des Federkörpers (nachgemessen an dessen Box,
        // −0,0338 … 0,0368). Sie erbte zuerst den Versatz der alten
        // Flügelspitze (−0,0135), die bewusst an der Hinterkante saß wie
        // eine Handschwinge — an einer Hand sah dasselbe aus, als wüchsen
        // die Finger aus dem Rand und zeigten woandershin (Tims Befund
        // 27.08.26).
        finger.translate(...fingerSitz(v, fach));
        /* Jeder Finger an seinem EIGENEN Knochen (seit 28.08.26). Er sitzt
           am Fuß, also dort, wo auch die Spreizung dreht — `rotation.x`
           krümmt den Finger von da an nach vorn. Die Spreizung bleibt
           gebaute Geometrie: Sie ändert die Ruheform der Hand, nicht ihre
           Haltung. */
        teil('fluegelfinger-' + seite + '-' + i, finger, M.gefieder,
             'finger-' + seite + '-' + i);
        handTeile.push('fluegelfinger-' + seite + '-' + i);
      });
    }

    /* ── Ellbogen ──────────────────────────────────────────────────────
       Der Drehpunkt liegt MITTIG im weißen Arm (y ≈ 0,095), nicht an der
       dunklen Spitze. Die Spitze ist die Hand: Sie hängt am Gelenk und
       dreht als Ganzes mit. Der weiße Arm dreht NICHT mit — seine Punkte
       werden gebogen, siehe oben.

       Die Kennwerte gehen an die Schulter, damit `szene.mjs` sie nicht
       nachrechnen muss. Die Achse ist die Längsrichtung des Arms: Die
       Geometrie ist um `v * -0.15` gekippt, ihr +y zeigt deshalb
       (0,1494·v / 0,9888 / 0). */
    void handTeile;                       // hängen jetzt am Ellbogenknochen
    /* Hier standen bis zum 28.08.26 Kennwerte für `armBeugen()` in
       `szene.mjs`: Drehpunkt, Achse und der Name des zu biegenden Meshes.
       Die Funktion drehte die Armpunkte bei jeder Pose von Hand um den
       Ellbogen. Das macht jetzt die Haut, und die Kennwerte hat niemand
       mehr gelesen. */

    if (winkt && v === -1) schulter.rotation.z = -1.58;
  });

  /* ── Schwimmfüße: geschlossener Fächer statt aufgeschnittenem Zylinder ── */
  const fussForm = new THREE.Shape();
  fussForm.moveTo(-0.0085, -0.0125);
  fussForm.quadraticCurveTo(0, -0.0205, 0.0085, -0.0125);
  fussForm.quadraticCurveTo(0.0262, 0.0045, 0.0238, 0.0280);
  fussForm.quadraticCurveTo(0, 0.0362, -0.0238, 0.0280);
  fussForm.quadraticCurveTo(-0.0262, 0.0045, -0.0085, -0.0125);
  [['links', 1], ['rechts', -1]].forEach(([seite, v]) => {
    const fuss = new THREE.ExtrudeGeometry(fussForm, {
      depth: 0.0062, curveSegments: 22, bevelEnabled: true,
      bevelThickness: 0.0024, bevelSize: 0.0026, bevelSegments: 3,
    });
    fuss.rotateX(Math.PI / 2);
    fuss.rotateY(v * 0.30);
    fuss.translate(v * 0.0305, 0.0092, 0.0405);
    teil('fuss-' + seite, fuss, M.schnabelD, 'fuss-gelenk-' + seite);
  });

  /* ── Augen mit zwei Glanzpunkten ── */
  [['links', 1], ['rechts', -1]].forEach(([seite, v]) => {
    const ax = v * 0.0332, ay = 0.1478, az = 0.0650;
    const gelenk = 'auge-gelenk-' + seite;

    if (augenZu) {
      const lid = new THREE.TorusGeometry(0.0132, 0.0026, 10, 22, Math.PI * 0.86);
      /* ZU und FREUDE sind DERSELBE Bogen, nur andersherum gedreht.
         Geschlossene Lider hängen nach unten durch, ein Lachauge wölbt
         sich nach oben — das ist der ganze Unterschied zwischen „schläft"
         und „lacht", und er kostet eine halbe Umdrehung. */
      lid.rotateZ(augenArt === 'freude' ? Math.PI * 0.07 : Math.PI + Math.PI * 0.07);
      lid.translate(ax, ay + (augenArt === 'freude' ? -0.0016 : 0.0042), az + 0.0128);
      teil('auge-' + seite, lid, M.lid, gelenk);
      return;
    }
    /* WEIT reißt das Auge auf — die Iris wächst, die PUPILLE BLEIBT.
       Der erste Versuch verkleinerte sie zusätzlich auf 82 %, weil ein
       aufgerissenes Auge viel Weiß zeigt. Bei 192 px kippte das Auge
       damit ins Blasse: Ohne dunklen Kern liest es sich als heller Fleck,
       nicht als Schreck. Der Kontrast ist wichtiger als die Anatomie.
       Und 1,09 statt 1,16: Auch mit dunklem Kern wurde das Auge bei 16 %
       mehr heller Iris auf 192 px blass. Was „aufgerissen" wirklich
       trägt, sind die Brauen und der offene Schnabel — die Iris hilft
       nur mit. */
    const weit = augenArt === 'weit' ? 1.09 : 1;
    const aug = new THREE.SphereGeometry(0.0178 * weit, 34, 26);
    aug.scale(1, 1.06, 0.88);
    aug.translate(ax, ay, az);
    teil('auge-' + seite, aug, M.auge, gelenk);

    // Die Pupille sitzt VORN auf der Iris und hängt im selben Gelenk —
    // deshalb zeigt sie die Blickrichtung.
    //
    // Sie ragt bewusst nur um Haaresbreite heraus (0,0006). Stand sie
    // weiter vor, verschob sie sich bei schrägem Blickwinkel optisch
    // gegen die Iris und lag scheinbar NEBEN ihr statt darin — die Optik
    // eines aufgesetzten Knopfes statt eines Auges.
    const pup = new THREE.SphereGeometry(0.0104, 26, 20);
    pup.scale(1, 1.02, 0.62);
    pup.translate(ax, ay, az + 0.0099 * weit);
    teil('pupille-' + seite, pup, M.pupille, gelenk);

    /* SCHMAL: ein Lidbalken über der oberen Hälfte. Das Auge selbst bleibt
       eine Kugel — es zu stauchen machte daraus eine hervorquellende
       Linse (siehe `emotionen.mjs`). Ein Lid davorzulegen ist, was ein
       Lid tut. */
    if (augenArt === 'schmal') {
      const lid = new THREE.SphereGeometry(0.0186, 24, 18);
      lid.scale(1, 0.58, 0.92);
      lid.translate(ax, ay + 0.0148, az + 0.0006);
      teil('auge-lid-' + seite, lid, M.lid, gelenk);
    }

    /* GRÖSSENVERHÄLTNIS, das ein Auge lesbar macht:
         Iris  = ganzer Augapfel            (Radius 0,0178)
         Pupille ≈ 65 % davon               (0,0116)
         Glanzpunkt ≈ 25 % DER PUPILLE      (0,0030)
       Die Glanzpunkte waren für ein einfarbiges Auge gebaut: groß und weit
       außen. Neben dem neuen dunklen Kern waren sie fast so groß wie er
       und lagen an seinem Rand — das Auge las sich als „halb schwarz, halb
       weiß" statt als Pupille mit Funkeln (Tims Befund 20.08.26). Ein
       Glanzlicht ist ein Reflex, kein zweites Auge. */
    const gross = new THREE.SphereGeometry(0.0030, 22, 16);
    gross.translate(ax - 0.0038, ay + 0.0042, az + 0.0150);
    teil('augenglanz-' + seite, gross, M.glanz, gelenk);

    const klein = new THREE.SphereGeometry(0.0014, 14, 10);
    klein.translate(ax + 0.0042, ay - 0.0044, az + 0.0146);
    teil('augenglanz-klein-' + seite, klein, M.glanz, gelenk);
  });

  /* ── Brauen, Träne, Schweißtropfen ────────────────────────────────────
     Das Comic-Vokabular. Alle drei hängen am AUGENGELENK der jeweiligen
     Seite und gehen deshalb mit dem Blick mit — eine Braue, die stehen
     bleibt, während das Auge wandert, sieht aufgeklebt aus.

     Die Winkel sind aus Sicht der LINKEN Seite notiert und werden für
     rechts gespiegelt. `hoch` verschiebt zusätzlich nach oben: Eine
     hochgezogene Braue ist nicht nur schräg, sie steht auch höher. */
  /* DIE HÖHE IST FAST FEST, DER WINKEL MACHT DIE ARBEIT.
     Zwischen der Augenoberkante (165,6 mm) und der Mützenkrempe (169 mm)
     liegen 3,4 mm. Der erste Versuch setzte die Brauen 24 mm über die
     Augenmitte — also mitten in die Krempe, und im Bild war keine einzige
     zu sehen. Sie sitzen jetzt DIREKT auf dem oberen Augenrand, wie bei
     einer Comic-Figur, und unterscheiden sich fast nur im Winkel. Die
     `hoch`-Angaben bewegen sich deshalb im Bereich von ein bis zwei
     Millimetern; mehr gibt der Hut nicht her. */
  const BRAUEN = {
    // Innen hoch, außen tief — das eindeutigste Zeichen für Kummer.
    traurig: { winkel: -23, hoch: 0.0012, laenge: 1.00 },
    sorge:   { winkel: -13, hoch: 0.0008, laenge: 0.95 },
    // Innen tief, außen hoch — Ärger. Stärker als traurig, weil ein
    // zorniger Blick sonst nur skeptisch wirkt.
    boese:   { winkel:  28, hoch: -0.0010, laenge: 1.00 },
    // Hoch und fast waagerecht: Überraschung, Nachfrage.
    hoch:    { winkel:  -6, hoch: 0.0019, laenge: 0.92 },
    flach:   { winkel:   0, hoch: 0.0006, laenge: 1.00 },
  };

  const brauenArt = BRAUEN[opt.brauen];
  /* Ein TROPFEN als Rotationsprofil: unten rund, oben spitz. Eine
     gestauchte Kugel wäre einfacher und sähe aus wie eine Perle — die
     Spitze IST das Zeichen. */
  const tropfen = (groesse) => {
    const profil = [
      V2(0.0000, 0.0125), V2(0.0012, 0.0072), V2(0.0028, 0.0028),
      V2(0.0040, -0.0010), V2(0.0036, -0.0042), V2(0.0018, -0.0058),
      V2(0.0000, -0.0062),
    ].map((v) => new THREE.Vector2(v.x * groesse, v.y * groesse));
    return new THREE.LatheGeometry(profil, 20);
  };

  [['links', 1], ['rechts', -1]].forEach(([seite, v]) => {
    const ax = v * 0.0332, ay = 0.1478, az = 0.0650;
    const gelenk = 'auge-gelenk-' + seite;

    if (brauenArt) {
      const b = new THREE.CapsuleGeometry(0.0027, 0.0232 * brauenArt.laenge, 6, 12);
      b.rotateZ(Math.PI / 2);                       // liegend statt stehend
      b.scale(1, 1, 0.55);                          // flach auf dem Gesicht
      b.rotateZ(v * brauenArt.winkel * Math.PI / 180);
      b.translate(ax, ay + 0.0186 + brauenArt.hoch, az + 0.0092);
      teil('braue-' + seite, b, M.braue, gelenk);
    }

    if (opt.traene === seite || opt.traene === 'beide') {
      /* AM ÄUSSEREN AUGENWINKEL, auf der Wange, und GROSS. Der erste
         Versuch saß mit 8 mm zwischen Auge und Wange und war im Bild
         nicht zu finden — ein hellblauer Tropfen auf einem weißen Gesicht
         braucht Größe, sonst ist er ein Lichtfleck. Die Wange reicht bis
         y = 136 mm, der Tropfen hängt von dort nach unten. */
      const t = tropfen(3.0);
      /* VOR der Wange, nicht darin: Die Wange reicht von x 44 bis 68 mm
         und bis z = 72 mm — ein Tropfen dahinter wird von ihr verdeckt.
         Bei z = 78 liegt er davor und hängt sichtbar am Augenwinkel. */
      t.translate(ax + v * 0.0182, ay - 0.0268, az + 0.0128);
      teil('traene-' + seite, t, M.traene, gelenk);
    }

    if (opt.schweiss === seite) {
      /* Am Kopf, nicht am Augengelenk: Der Schweißtropfen sitzt an der
         Schläfe und gehört nicht zum Blick. */
      const t = tropfen(2.3);
      t.rotateZ(v * -0.38);
      /* NEBEN dem Kopf, nicht darin. Bei y = 170 mm endet der Kopf bei
         x = 62 mm (gemessen); der erste Versuch saß mit x = 60 innen drin
         und war unsichtbar. Ein Comic-Schweißtropfen schwebt ohnehin
         neben der Schläfe — das ist die Konvention, nicht der Kompromiss. */
      t.translate(v * 0.0662, 0.1730, 0.0330);
      teil('schweiss-' + seite, t, M.traene, 'kopf');
    }
  });

  /* ── Schnabel ─────────────────────────────────────────────────────────
     Zwei abgeflachte Kugeln übereinander — so war es, und so sah es aus:
     Der Schnabel lief nirgends spitz zu (Tims Befund 20.08.26). Jetzt ist
     jede Hälfte ein ROTATIONSPROFIL, das von der Wurzel zur Spitze schmal
     wird.

     Das Profil läuft von 0 (Wurzel) bis 1 (Spitze); der Radius bleibt
     zunächst voll und fällt dann immer schneller ab — das ergibt die
     leicht gebauchte Form eines Möwenschnabels statt eines geraden Kegels.
     Danach wird das Profil in der Höhe gestaucht (ein Schnabel ist breiter
     als hoch) und nach vorn gedreht. */
  // Oberschnabel, an der Spitze leicht nach unten geneigt — der Haken, den
  // jede Möwe hat. Die Drehung läuft um die Schnabelwurzel, weil die
  // Geometrie hier noch im Ursprung sitzt.
  const oben = schnabelForm(THREE, 0.0720, 0.0238, 0.0118);
  oben.rotateX(0.13);
  oben.translate(0, 0.1332, 0.0488);
  teil('schnabel-oben', oben, M.schnabel, 'kopf');

  // Unterschnabel: kürzer, schmaler und flacher, damit der Oberschnabel
  // vorn überhängt. Vorher stand er als dunkler Lappen darunter hervor und
  // las sich als herausgestreckte Zunge.
  const unten = schnabelForm(THREE, 0.0620, 0.0196, 0.0076);
  unten.rotateX(0.15);
  unten.translate(0, 0.1246, 0.0494);
  teil('schnabel-unten', unten, M.schnabelD, 'schnabel-gelenk');

  /* ── Schnabel-Scharnier ───────────────────────────────────────────────
     Ein Schnabel klappt, er rutscht nicht. Vorher wurde die Unterhälfte
     beim Öffnen schlicht nach unten VERSCHOBEN — bei weit offenem Schnabel
     löste sie sich dadurch komplett vom Rest und schwebte frei unter dem
     Gesicht (Tims Befund 20.08.26).

     Der Drehpunkt liegt an der WURZEL, dort wo beide Hälften am Kopf
     sitzen. Damit bleiben sie hinten verbunden und öffnen sich nur vorn.

     Dass eine Drehung früher nicht ging, lag an der Geometrie: Sie ist zum
     Kopf hin verschoben, eine Drehung am Mesh liefe um den Modell-Ursprung
     und risse den Schnabel aus dem Gesicht. Eine Gelenkgruppe löst das. */
  /* Der RACHEN — und warum er MITWÄCHST.
     Zwischen den Hälften war nichts, beim offenen Schnabel schien die
     weiße Gesichtsfläche hindurch. Zwei Sackgassen davor:

     1. Ein Rachen fester Größe ließ sich geschlossen nicht verstecken.
        Beide Hälften laufen zur Spitze hin dünn aus — dazwischen ist kein
        Platz für einen dritten Körper, der dort verschwinden könnte.
     2. Die Unterhälfte dick zu machen füllte die Lücke zwar, aber im
        Profil hing dann ein fetter zweiter Kegel am Kopf statt einer
        flachen Kinnlade (Tims Befund 20.08.26). Eine Kinnlade IST flach.

     Deshalb wird der Rachen für jede Öffnung neu gebaut und ist bei
     geschlossenem Schnabel GAR NICHT DA. Seine Dicke entspricht der
     halben Lücke, die sich bei diesem Winkel auftut: Der Drehpunkt liegt
     bei z = 0,060, in Höhe der Spitze sind das rund 5 cm Hebel, und
     `sin(Winkel) · Hebel / 2` ergibt den Faktor unten. Er hängt im
     Schnabelgelenk und fährt mit der Unterhälfte nach unten.

     Das ist der Grund, warum `baueLotti` die Öffnung überhaupt kennen muss
     — wie bei `augen: 'zu'` ist es eigene Geometrie, keine Verformung. */
  if (schnabelAuf > 0) {
    /* Der RACHEN — ein Keil, der die Lücke füllt.
       Ohne ihn schien im offenen Schnabel die weiße Gesichtsfläche
       hindurch. Er ist nur vorhanden, wenn der Schnabel auch aufgeht, und
       seine Dicke wächst mit der Öffnung.

       ER IST VON HINTEN NACH VORN AUFGEKEILT (`keilen`). Zuerst hatte er
       die Verjüngung eines Schnabels — hinten dick, vorn spitz — und stand
       dadurch hinten über der Kinnlade; von der Seite las er sich als
       DRITTER Schnabel. Die Lücke ist genau andersherum: am Drehpunkt
       null, nach vorn immer weiter.

       Ein zusätzlicher flacher Fleck auf der Haut (`mundfleck`) war eine
       Zwischenstufe und ist wieder raus: Er stand bei geneigtem Kopf
       seitlich am Schnabel vorbei — als dunkler Splitter neben der Spitze.
       Der Keil allein deckt alles, wenn er hoch genug liegt (0,1275 statt
       0,1246) und die Oberhälfte wirklich erreicht. Lag er zu tief, blieb
       ein abgesetzter dunkler Klecks in der Unterschale stehen, der wie
       eine Wunde aussah (Tims Befund 20.08.26) — daher auch die dunklere,
       entsättigte Farbe: Ein mittleres Rot liest sich als Blut, ein
       gedämpfter Rotton als Mundhöhle. Ganz ins Schwarzbraune darf er
       aber auch nicht (#43201A war zu dunkel) — #873A2A liegt dazwischen:
       klar dunkler als der Schnabel, aber noch erkennbar rot. */
    const rachen = schnabelForm(THREE, 0.0560, 0.0168, schnabelAuf * 0.00075);
    keilen(rachen, 0.0560);
    rachen.rotateX(0.15);
    rachen.translate(0, 0.1275, 0.0500);
    teil('rachen', rachen, M.rachen, 'schnabel-gelenk');
  }

  /* Der Drehpunkt liegt VORN an der Schnabelwurzel, wo die Hälften aus dem
     Gefieder treten. Zuerst saß er weiter hinten, tief im Kopf — dadurch
     klaffte die Öffnung schon dort auseinander, wo noch Kopf ist. */

  /* ── Wangen ── */
  [['links', 1], ['rechts', -1]].forEach(([seite, v]) => {
    const w = new THREE.SphereGeometry(0.0155, 26, 18);
    w.scale(1, 0.66, 0.30);
    w.rotateY(v * 0.72);
    w.translate(v * 0.0556, 0.1262, 0.0612);
    teil('wange-' + seite, w, M.wange, 'kopf');
  });

  /* ── Kapitänsmütze ── */
  const muetze = knochen.get('muetze').bone;
  const muetzenTeil = (name, geo, material) => {
    geo.scale(1, 1, 1.04);
    return teil(name, geo, material, 'muetze');
  };

  muetzenTeil('muetzen-krone', new THREE.LatheGeometry([
    V2(0, 0.1795), V2(0.0745, 0.1800), V2(0.0768, 0.1880), V2(0.0755, 0.1962),
    V2(0.0702, 0.2062), V2(0.0602, 0.2158), V2(0.0432, 0.2248), V2(0.0242, 0.2300), V2(0, 0.2322),
  ], 64), M.navy);

  // geschlossener Zylinder: ein offener hätte von unten und an den Kanten Löcher gezeigt
  muetzenTeil('muetzen-bund', new THREE.CylinderGeometry(0.0772, 0.0764, 0.0145, 64)
    .translate(0, 0.1855, 0), M.navyTief);

  muetzenTeil('muetzen-litze', new THREE.TorusGeometry(0.0776, 0.0021, 12, 72)
    .rotateX(Math.PI / 2).translate(0, 0.1938, 0), M.gold);

  // Schirm als geschlossener Halbring-Körper statt als aufgeschnittener Rotationskörper
  const schirmForm = new THREE.Shape();
  schirmForm.absarc(0, 0, 0.107, 0.15, Math.PI - 0.15, false);
  schirmForm.absarc(0, 0, 0.048, Math.PI - 0.15, 0.15, true);
  const schirm = new THREE.ExtrudeGeometry(schirmForm, {
    depth: 0.0075, curveSegments: 44, bevelEnabled: true,
    bevelThickness: 0.0026, bevelSize: 0.0030, bevelSegments: 3,
  });
  schirm.rotateX(Math.PI / 2 + 0.14);
  schirm.translate(0, 0.1878, 0.0025);
  muetzenTeil('muetzen-schirm', schirm, M.navyTief);

  const emblem = new THREE.CylinderGeometry(0.0152, 0.0152, 0.0052, 40);
  emblem.rotateX(Math.PI / 2 - 0.34);
  emblem.translate(0, 0.2046, 0.0710);
  muetzenTeil('muetzen-emblem', emblem, M.gold);

  const sternForm = new THREE.Shape();
  const ZACKEN = 4, RA = 0.0091, RI = 0.0045;
  for (let i = 0; i < ZACKEN * 2; i++) {
    const r = i % 2 === 0 ? RA : RI;
    const a = (i / (ZACKEN * 2)) * Math.PI * 2 + Math.PI / 2;
    const px = Math.cos(a) * r, py = Math.sin(a) * r;
    i === 0 ? sternForm.moveTo(px, py) : sternForm.lineTo(px, py);
  }
  sternForm.closePath();
  const stern = new THREE.ExtrudeGeometry(sternForm, { depth: 0.0022, bevelEnabled: false });
  stern.rotateX(-0.34);
  stern.translate(0, 0.2046, 0.0731);
  muetzenTeil('muetzen-stern', stern, M.navyTief);

  muetze.rotation.x = -0.085;               // leicht in den Nacken gekippt
  muetze.rotation.z = 0.045;

  /* ── Kopf-Gelenk ──────────────────────────────────────────────────────
     Augen, Schnabel, Wangen und Mütze hängen ab hier in einer eigenen
     Gruppe. Vorher saßen sie direkt am Rumpf, und eine Neigung kippte
     zwangsläufig die ganze Figur — „Kopf schief legen" sah dadurch aus wie
     Umfallen (Tims Befund 19.08.26).

     Der Drehpunkt liegt unter dem Schnabel, wo bei einem Vogel der Hals
     ansetzt. Weil die Teile ihre Lage teils in der GEOMETRIE tragen und
     teils in `position`, wird der Versatz beim Umhängen abgezogen —
     sonst führe der ganze Kopf um den Drehpunkt nach oben.

     ACHTUNG: Diese Datei ist sonst 1:1 aus dem Claude-Design-Projekt
     kopiert, das die Quelle der Wahrheit ist. Dieses Gelenk ist die eine
     bewusste Abweichung und gehört dort nachgezogen. */
  // Wer einen Hut an den Scheitel setzt, muss denselben Versatz abziehen.
  lotti.userData.kopfDrehpunkt = KOPF_DREHPUNKT;

  /* ── Fuß-Gelenke ──────────────────────────────────────────────────────
     Die Füße saßen ohne Gelenk am Rumpf: In jeder Pose standen beide exakt
     parallel und flach — der Grund, warum die Figur auch mit lebendigem
     Kopf noch aufgestellt statt stehend wirkte. Standbein und Spielbein
     sind der älteste Trick der Figurenzeichnung.

     Der Drehpunkt liegt an der Ferse, hinten am Fuß, nicht in seiner Mitte:
     Um die Mitte gedreht sähe ein gehobener Fuß aus, als schwebte er. */
  anbinden(THREE, lotti, skelett, gehaeutet);
  return lotti;
}

/**
 * Die Haut ans Skelett binden — der letzte Schritt jeder Figur.
 *
 * DIE REIHENFOLGE IST DER GANZE WITZ. `bind()` ohne eigene Bindematrix
 * würde three dazu bringen, die Umkehrmatrizen JETZT aus den
 * Weltmatrizen zu rechnen — und die stimmen nur, wenn vorher jemand
 * `updateMatrixWorld` gerufen hat. `baueSkelett` erledigt das für die
 * Knochen; hier kommt die Einheitsmatrix dazu, weil Geometrie und
 * Knochen im selben Raum stehen (Figurenkoordinaten). Damit gilt in
 * Ruhelage `Punkt = Punkt`, und die Figur sieht aus wie vorher.
 */
function anbinden(THREE, figur, skelett, gehaeutet) {
  figur.updateMatrixWorld(true);
  const eins = new THREE.Matrix4();
  for (const m of gehaeutet) m.bind(skelett, eins);
}

/* ── Küken: kleiner, runder, ohne Mütze — nach dem Chick aus mascot.tsx ── */
export function baueKueken(THREE, opt = {}) {
  const gold = opt.ton === 'gold';
  const K = 0.00105;                       // SVG-Einheit (120×120) → Meter, Küken ca. 9 cm
  const kx = X => (X - 60) * K;
  const ky = Y => (116 - Y) * K;

  const M = {
    koerper:  new THREE.MeshStandardMaterial({ name:'kueken-weiss',   color:'#FBFDFF', roughness:0.66, metalness:0.02 }),
    gefieder: new THREE.MeshStandardMaterial({ name:'kueken-gefieder',color:'#C7D6E4', roughness:0.74, metalness:0.02 }),
    auge:     new THREE.MeshStandardMaterial({ name:'kueken-iris',    color:'#9FC4DC', roughness:0.16, metalness:0.05 }),
    pupille:  new THREE.MeshStandardMaterial({ name:'kueken-pupille', color:'#0A1520', roughness:0.14, metalness:0.05 }),
    glanz:    new THREE.MeshStandardMaterial({ name:'kueken-glanz',   color:'#FFFFFF', roughness:0.10, metalness:0.00, emissive:'#FFFFFF', emissiveIntensity:0.30 }),
    schnabel: new THREE.MeshStandardMaterial({ name:'kueken-schnabel',color: gold ? '#F2B441' : '#F66623', roughness:0.44, metalness:0.03 }),
    fuss:     new THREE.MeshStandardMaterial({ name:'kueken-fuss',    color: gold ? '#D99A1F' : '#D9531E', roughness:0.48, metalness:0.03 }),
    wange:    new THREE.MeshStandardMaterial({ name:'kueken-wange',   color:'#FFAD85', roughness:0.85, metalness:0.00 }),
  };

  const kueken = new THREE.Group();
  kueken.name = 'kueken';
  const { wurzel, skelett, knochen } = baueSkelett(THREE, SKELETTE.kueken);
  kueken.add(wurzel);
  kueken.userData.skelett = skelett;
  const gehaeutet = [];

  const teil = (name, geo, material, an = 'wurzel') => {
    const k = knochen.get(an);
    if (!k) throw new Error(`Teil „${name}": Knochen „${an}" gibt es nicht`);
    const m = new THREE.Mesh(geo, material);
    m.name = name;
    m.castShadow = true;
    m.receiveShadow = true;
    m.position.copy(k.absolut).negate();
    k.bone.add(m);
    return m;
  };
  const haut = (name, geo, material, kette) => {
    hauteAn(THREE, geo, kette, knochen);
    const m = new THREE.SkinnedMesh(geo, material);
    m.name = name;
    m.castShadow = true;
    m.receiveShadow = true;
    m.frustumCulled = false;
    kueken.add(m);
    gehaeutet.push(m);
    return m;
  };

  const koerper = new THREE.SphereGeometry(0.0357, 40, 30);
  koerper.scale(1, 0.95, 0.97);
  koerper.translate(0, 0.0424, 0);
  haut('kueken-koerper', koerper, M.koerper, HAUT.kuekenRumpf);

  [['links', 1], ['rechts', -1]].forEach(([seite, v]) => {
    /* Der Flügel biegt sich jetzt (28.08.26). Vorher war er ein starres
       Paddel an einer Schultergruppe — der Grund, warum mehrere Küken in
       einem Bild immer wie dasselbe Küken aussahen. */
    const fl = new THREE.SphereGeometry(0.0192, 26, 20);
    fl.scale(0.28, 1.02, 0.82);
    fl.rotateZ(v * -0.16);
    fl.translate(v * 0.0338, 0.0405, 0.0010);
    haut('kueken-fluegel-' + seite, fl, M.gefieder,
         glied(knochen, ['kueken-schulter-' + seite, 'kueken-ellbogen-' + seite],
               [HAUT.kuekenBeuge]));

    const gelenk = 'kueken-auge-gelenk-' + seite;
    const ax = v * 0.0128, ay = 0.0478, az = 0.0292;

    const aug = new THREE.SphereGeometry(0.0084, 26, 20);
    aug.scale(1, 1.05, 0.90);
    aug.translate(ax, ay, az);
    teil('kueken-auge-' + seite, aug, M.auge, gelenk);

    const pup = new THREE.SphereGeometry(0.0050, 20, 16);
    pup.scale(1, 1.02, 0.62);
    pup.translate(ax, ay, az + 0.0046);
    teil('kueken-pupille-' + seite, pup, M.pupille, gelenk);

    const gl = new THREE.SphereGeometry(0.0015, 16, 12);
    gl.translate(ax - 0.0018, ay + 0.0020, az + 0.0074);
    teil('kueken-glanz-' + seite, gl, M.glanz, gelenk);

    const w = new THREE.SphereGeometry(0.0072, 20, 14);
    w.scale(1, 0.66, 0.30);
    w.rotateY(v * 0.74);
    w.translate(v * 0.0236, 0.0348, 0.0250);
    teil('kueken-wange-' + seite, w, M.wange, 'kopf');

    const f = new THREE.SphereGeometry(0.0088, 18, 12);
    f.scale(0.86, 0.34, 1.30);
    f.translate(v * 0.0128, 0.0032, 0.0128);
    teil('kueken-fuss-' + seite, f, M.fuss, 'fuss-gelenk-' + seite);
  });

  const schnabel = schnabelForm(THREE, 0.0300, 0.0100, 0.0052);
  schnabel.rotateX(0.14);
  schnabel.translate(0, 0.0370, 0.0206);
  teil('kueken-schnabel', schnabel, M.schnabel, 'kopf');

  const bueschel = new THREE.SphereGeometry(0.0062, 18, 14);
  bueschel.scale(0.55, 1.75, 0.55);
  bueschel.rotateZ(-0.34);
  bueschel.translate(0.0028, 0.0855, -0.0016);
  teil('kueken-bueschel', bueschel, M.gefieder, 'kopf');

  const bueschel2 = new THREE.SphereGeometry(0.0052, 18, 14);
  bueschel2.scale(0.55, 1.45, 0.55);
  bueschel2.rotateZ(0.30);
  bueschel2.translate(-0.0044, 0.0822, -0.0022);
  teil('kueken-bueschel-2', bueschel2, M.gefieder, 'kopf');

  /* ── Kopf und Füße wie bei Lotti ──────────────────────────────────────
     Ein Küken ist im Grunde eine Kugel; einen Hals hat es nicht. Der
     Drehpunkt liegt deshalb tief, knapp über der Körpermitte — dreht man
     weiter oben, wandert das Gesicht sichtbar über die Kugel statt sich zu
     neigen. Die Federbüschel gehören mit an den Kopf: Sie sind das, was die
     Neigung bei dieser Figur überhaupt lesbar macht. */
  kueken.userData.kopfDrehpunkt = 0.0300;
  anbinden(THREE, kueken, skelett, gehaeutet);
  return kueken;
}


/**
 * Fingerabdruck der GEOMETRIE — Teilezahl, Eckpunkte und gerundete
 * Ausmaße, zu einer kurzen Zeichenkette verrechnet.
 *
 * Wozu neben `MODELL_VERSION`: Die Version ist von Hand gepflegt und wird
 * vergessen. Der Fingerabdruck ändert sich, sobald sich die Form ändert —
 * er beantwortet „ist das PNG mit DIESEM Modell entstanden?" auch dann,
 * wenn niemand die Version hochgezählt hat.
 */
export function fingerabdruck(THREE, opt = {}) {
  const figur = baueLotti(THREE, opt);
  let teile = 0; let ecken = 0;
  figur.traverse((o) => {
    if (!o.isMesh) return;
    teile++;
    ecken += o.geometry?.attributes?.position?.count ?? 0;
  });
  figur.updateWorldMatrix(true, true);
  const box = huelle(THREE, figur);
  const g = box.getSize(new THREE.Vector3());
  /* DAS SKELETT GEHÖRT MIT HINEIN. Beim Umstieg am 28.08.26 blieb der
     Fingerabdruck unverändert, obwohl die halbe Datei neu war: Teilezahl,
     Eckpunkte und Ausmaße waren dieselben, nur hing alles woanders. Ein
     Erkennungszeichen, das eine Skelettänderung nicht bemerkt, erkennt
     genau die Änderungen nicht, bei denen sich die Ruhelage NICHT ändert —
     und das sind die gefährlichen. */
  const knochen = [];
  figur.traverse((o) => {
    if (!o.isBone) return;
    const p = o.getWorldPosition(new THREE.Vector3());
    knochen.push(o.name + ':' + p.toArray().map((n) => Math.round(n * 10000)).join(','));
  });
  const zahl = [teile, ecken, ...g.toArray().map((n) => Math.round(n * 10000)),
    ...knochen].join('-');
  // Kurze, stabile Prüfsumme — kein Kryptohash nötig, es geht um
  // Wiedererkennung, nicht um Fälschungssicherheit.
  let h = 2166136261;
  for (let i = 0; i < zahl.length; i++) {
    h ^= zahl.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(36).padStart(7, '0');
}
