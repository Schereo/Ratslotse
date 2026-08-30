/* Echte Skelette für Lotti und die Küken — Knochen statt Gruppen.
 *
 * WARUM DAS SEIN MUSSTE (Tims Frage am 28.08.26: „was bräuchtest du, um
 * Lotti mit ihren Küken in einer Sandkiste spielend zu zeichnen?"). Die
 * ehrliche Antwort war: den Rumpf. Die Figur konnte sich nicht setzen,
 * nicht bücken, nicht lehnen — sie hatte kein Gelenk zwischen Fuß und
 * Kopf. Alle sechs Posen waren Stehposen, weil es gar keine andere geben
 * konnte. Jede neue Haltung war eine GEOMETRIEOPERATION (`armBeugen`
 * drehte Punkte von Hand um den Ellbogen) statt eines Winkels.
 *
 * WAS EIN SKELETT HIER HEISST — und was nicht:
 *
 *   Knochen tragen die Hierarchie.   Jedes Gelenk ist ein `THREE.Bone` mit
 *                                    demselben NAMEN wie die Gruppe vorher.
 *                                    `schulter-links` bleibt `schulter-links`;
 *                                    Posen, Anker und die Inverse Kinematik
 *                                    merken davon nichts.
 *
 *   Haut gibt es nur, wo verformt     Fünf Teile sind `SkinnedMesh`: Lottis
 *   wird.                             Rumpf und ihre beiden Arme, der Körper
 *                                     und die Flügel des Kükens. Alles andere
 *                                     — Augen, Schnabel, Mütze, Füße, Finger —
 *                                     ist ein starres Teil AN einem Knochen.
 *
 * Das zweite ist kein Sparen, sondern die übliche Bauweise: Ein Auge
 * verformt sich nicht, es wird getragen. Starre Teile behalten damit
 * `visible`, ihr Material und ihre einfache Bounding-Box — der Hutwechsel
 * in `szene.mjs` (`muetze.visible = false`) funktioniert unverändert,
 * `teil.mjs` löst weiter einzelne Teile heraus.
 *
 * DIE EINE FALLE, die man kennen muss: `Box3.setFromObject(x)` misst bei
 * einem `SkinnedMesh` die RUHELAGE, nicht die Pose — die Verformung
 * passiert im Shader. Mit `setFromObject(x, true)` misst three jeden
 * Eckpunkt einzeln und wendet dabei die Knochen an. Überall, wo das Maß
 * einer posierten Figur gebraucht wird (Bodenkontakt, Kamerarahmung,
 * Prüfungen), steht deshalb `huelle()` aus dieser Datei statt eines
 * blanken `Box3`.
 */

/** Weiche Rampe von 0 auf 1 (Smoothstep), außerhalb geklemmt. */
function glatt(t) {
  const x = Math.min(Math.max(t, 0), 1);
  return x * x * (3 - 2 * x);
}

/**
 * ZWEI BOXEN, und der Unterschied ist wichtig.
 *
 * `huelle` MISST: jeder Eckpunkt einzeln, durch seine Knochen gerechnet.
 * Das ist die wahre Ausdehnung — und die Zahl, die auf ein Maßblatt
 * gehört.
 *
 * `rahmen` PLATZIERT: für starre Teile die grobe, mitgedrehte Box der
 * Geometrie (genau das, was `Box3.setFromObject` seit jeher lieferte),
 * für geskinnte Teile die genaue. Sie ist etwas zu groß, und das ist
 * ihre Aufgabe: Wer eine Kamera darauf rahmt, will lieber einen Hauch
 * Luft als einen angeschnittenen Hut.
 *
 * DASS ES ZWEI SIND, ist am 28.08.26 teuer gelernt worden. Beim Umstieg
 * aufs Skelett stand überall die genaue Box — und plötzlich waren ALLE
 * 31 Szenen um 8 bis 18 % der Fläche anders. Nicht weil die Figur sich
 * geändert hätte (Teil für Teil war sie deckungsgleich), sondern weil
 * die genaue Box 10 mm niedriger ausfällt als die grobe: Die Mütze sitzt
 * schräg, ihre mitgedrehte Box ist entsprechend zu hoch. Die Kamera
 * rahmt auf diese Box, rückte also 4 % näher — und jedes gerenderte PNG
 * hätte nicht mehr zu den Marken-Dateien in `assets/marke/` gepasst.
 *
 * Faustregel: Wer etwas HINSTELLT oder ins Bild bringt, nimmt `rahmen`.
 * Wer eine Zahl über die Form aussagt, nimmt `huelle`.
 */
/**
 * Weltmatrizen auffrischen — MIT den Bindematrizen der Haut.
 *
 * DIE FALLE, die einen halben Nachmittag gekostet hat (28.08.26): Ein
 * `SkinnedMesh` merkt sich in `bindMatrixInverse`, wo es zur Bindezeit
 * stand, und three frischt das ausschließlich in `updateMatrixWorld()`
 * auf. `updateWorldMatrix()` — die Fassung, die auch die VORFAHREN
 * nachzieht und die deshalb überall im Studio steht — überschreibt die
 * Methode nicht. Beim Rendern fällt das nie auf, weil der Renderer selbst
 * `scene.updateMatrixWorld()` ruft. Wer aber auf der CPU misst, bekommt
 * für jede verschobene oder gedrehte Figur die Verformung DOPPELT: Lottis
 * Rumpf lag in einer Flugszene 94 mm daneben, das Küken 154 mm, und die
 * Kamera rahmte entsprechend auf ein Gespenst.
 *
 * Beides zusammen ist die richtige Reihenfolge: erst die Vorfahren, dann
 * mit `updateMatrixWorld(true)` alles darunter — das trifft die
 * überschriebene Fassung und damit die Bindematrizen.
 */
function frisch(objekt) {
  objekt.updateWorldMatrix(true, false);
  objekt.updateMatrixWorld(true);
  /* UND die Knochen — die sind keine Vorfahren der Haut, sondern ihre
     GESCHWISTER. Ein `SkinnedMesh` hängt direkt an der Figur, das Skelett
     daneben; wer nur nach oben aktualisiert, misst deshalb eine Haut in
     alter Pose. Die Prüfung hat das sofort gefunden: „30° am Becken
     bewegen den Rumpf nur um 0,0 mm" (28.08.26). */
  objekt.traverse((o) => {
    if (!o.isSkinnedMesh || !o.skeleton) return;
    for (const b of o.skeleton.bones) b.updateWorldMatrix(true, false);
  });
}

export function huelle(THREE, objekt, ziel = null) {
  frisch(objekt);
  const box = ziel ?? new THREE.Box3();
  return box.setFromObject(objekt, true);
}

export function rahmen(THREE, objekt, ziel = null) {
  const box = (ziel ?? new THREE.Box3()).makeEmpty();
  const hilf = new THREE.Box3();
  frisch(objekt);
  /* Unsichtbare Teile zählen mit — `Box3.setFromObject` macht das auch,
     und der Hutwechsel in `szene.mjs` verlässt sich darauf: Er schaltet
     die Mütze nur ab, statt sie zu entfernen, und die Rahmung soll davon
     nicht springen. */
  objekt.traverse((o) => {
    const geo = o.geometry;
    if (!geo) return;
    if (o.isSkinnedMesh) {
      hilf.setFromObject(o, true);
    } else {
      if (!geo.boundingBox) geo.computeBoundingBox();
      if (!geo.boundingBox) return;
      hilf.copy(geo.boundingBox).applyMatrix4(o.matrixWorld);
    }
    box.union(hilf);
  });
  return box;
}

/**
 * DIE BAUPLÄNE — je Figur eine Liste `[name, elternteil, ruhelage]`.
 *
 * Die Ruhelage steht ABSOLUT in Figurenkoordinaten, nicht relativ zum
 * Elternteil. Das ist die Schreibweise, in der man sie nachmessen kann:
 * „die Schulter sitzt auf 13,6 cm" ist prüfbar, „die Schulter sitzt
 * 4,1 cm über der Brust" ist es erst nach einer Rechnung. `baueSkelett`
 * rechnet in relative Positionen um.
 *
 * Die Namen sind mit Bedacht die der alten Gruppen. Wer `schulter-links`
 * dreht, dreht weiterhin den linken Arm — nur dass jetzt auch das
 * Armgeflecht mitgeht statt nur seiner Aufhängung.
 */
export const SKELETTE = {
  lotti: [
    /* Die Wurzel steht auf dem Boden. Sie ist der Griff für die ganze
       Figur und der einzige Knochen, der NICHTS verformt — Füße hängen an
       ihr, damit ein gebeugter Rumpf sie stehen lässt. */
    ['wurzel',              null,      [0, 0, 0]],

    /* Die Wirbelsäule, die es vorher nicht gab. Drei Gelenke reichen für
       eine Eiform: unten kippt der ganze Körper (setzen), in der Mitte
       entsteht der Bauch-Rücken-Bogen (bücken), oben trägt die Brust
       Kopf und Schultern (lehnen, sich abwenden). */
    ['becken',              'wurzel',  [0, 0.030, 0]],
    ['bauch',               'becken',  [0, 0.072, 0]],
    ['brust',               'bauch',   [0, 0.095, 0]],

    /* Der Kopf sitzt auf DERSELBEN Höhe wie die Brust. Kein Versehen:
       Lottis Kopfdrehpunkt liegt bei 9,5 cm (unter dem Schnabel, wo beim
       Vogel der Hals ansetzt), und genau dort endet der Oberkörper. Die
       beiden Knochen unterscheiden sich nicht im Ort, sondern in dem, was
       sie tragen: `brust` dreht den Oberkörper SAMT Kopf und Armen,
       `kopf` dreht nur den Kopf. */
    ['kopf',                'brust',   [0, 0.095, 0]],
    ['schnabel-gelenk',     'kopf',    [0, 0.1268, 0.0600]],
    ['auge-gelenk-links',   'kopf',    [0.0332, 0.1478, 0.0650]],
    ['auge-gelenk-rechts',  'kopf',    [-0.0332, 0.1478, 0.0650]],
    ['muetze',              'kopf',    [0, 0, 0]],

    ['schwanz-gelenk',      'bauch',   [0, 0.075, -0.030]],

    ['schulter-links',      'brust',   [0.0700, 0.1360, 0.0020]],
    ['ellbogen-links',      'schulter-links',  [0.0836, 0.0826, 0.0015]],
    ['schulter-rechts',     'brust',   [-0.0700, 0.1360, 0.0020]],
    ['ellbogen-rechts',     'schulter-rechts', [-0.0836, 0.0826, 0.0015]],

    /* Die Füße hängen an der WURZEL, nicht am Becken. Wer sich bückt,
       hebt dabei nicht die Füße vom Boden. */
    ['fuss-gelenk-links',   'wurzel',  [0.0305, 0.0092, 0.0225]],
    ['fuss-gelenk-rechts',  'wurzel',  [-0.0305, 0.0092, 0.0225]],
  ],

  kueken: [
    ['wurzel',                    null,     [0, 0, 0]],
    /* Ein Küken ist eine Kugel; zwei Rumpfgelenke genügen. Mehr wäre
       nicht zu sehen — der Körper ist 6,8 cm hoch. */
    ['becken',                    'wurzel', [0, 0.018, 0]],
    ['brust',                     'becken', [0, 0.030, 0]],
    ['kopf',                      'brust',  [0, 0.030, 0]],
    ['kueken-auge-gelenk-links',  'kopf',   [0.0128, 0.0478, 0.0292]],
    ['kueken-auge-gelenk-rechts', 'kopf',   [-0.0128, 0.0478, 0.0292]],

    ['kueken-schulter-links',     'brust',  [0.0300, 0.0560, 0.0010]],
    /* NEU am 28.08.26: Küken haben einen Ellbogen. Vorher stand in
       `szene.mjs` die Zeile „Küken haben keinen" — ihre Flügel schwenkten
       als starre Paddel, was der Grund war, warum drei spielende Küken
       aussahen wie dreimal dasselbe Küken. */
    ['kueken-ellbogen-links',     'kueken-schulter-links',  [0.0338, 0.0405, 0.0010]],
    ['kueken-schulter-rechts',    'brust',  [-0.0300, 0.0560, 0.0010]],
    ['kueken-ellbogen-rechts',    'kueken-schulter-rechts', [-0.0338, 0.0405, 0.0010]],

    ['fuss-gelenk-links',         'wurzel', [0.0128, 0.0032, 0.0053]],
    ['fuss-gelenk-rechts',        'wurzel', [-0.0128, 0.0032, 0.0053]],
  ],
};

/**
 * Skelett aus einem Bauplan bauen.
 *
 * Rückgabe: `{ wurzel, skelett, knochen }` — `knochen` ist eine Map von
 * Namen auf `{ bone, index, absolut }`. Die absolute Ruhelage wird
 * mitgeführt, weil starre Teile sie brauchen: Ihre Geometrie steht in
 * FIGURENkoordinaten, und wer sie an einen Knochen hängt, muss dessen
 * Ort abziehen (sonst wandert das Teil um den ganzen Betrag davon —
 * dieselbe Falle, die `gelenkUm` beim Kopf dreimal gestellt hat).
 */
export function baueSkelett(THREE, plan) {
  const knochen = new Map();
  const reihe = [];
  for (const [name, elternteil, absolut] of plan) {
    if (knochen.has(name)) throw new Error(`Knochen doppelt: ${name}`);
    const bone = new THREE.Bone();
    bone.name = name;
    const eltern = elternteil ? knochen.get(elternteil) : null;
    if (elternteil && !eltern) {
      throw new Error(`Knochen „${name}": Elternteil „${elternteil}" gibt es nicht `
        + '(oder er steht weiter unten im Bauplan — die Liste muss von der '
        + 'Wurzel aus geordnet sein)');
    }
    const p = new THREE.Vector3(...absolut);
    bone.position.copy(eltern ? p.clone().sub(eltern.absolut) : p);
    if (eltern) eltern.bone.add(bone);
    const eintrag = { bone, index: reihe.length, absolut: p };
    knochen.set(name, eintrag);
    reihe.push(bone);
  }
  /* ERST die Weltmatrizen, DANN das Skelett.
     `new Skeleton(bones)` rechnet im Konstruktor die Umkehrmatrizen der
     Ruhelage aus — aus `bone.matrixWorld`. Die steht direkt nach dem
     Aufbau noch auf der Einheitsmatrix, weil three sie erst beim Rendern
     füllt. Ohne diese Zeile bekommt jeder Knochen die Einheitsmatrix als
     Ruhelage, und beim ersten Bild fährt jedes Teil um seinen eigenen
     Sitz davon: Lotti wurde 31 statt 24 cm hoch und 35 cm breit, weil
     beide Arme aus ihr herausflogen (gemessen 28.08.26). */
  reihe[0].updateMatrixWorld(true);
  const skelett = new THREE.Skeleton(reihe);
  return { wurzel: reihe[0], skelett, knochen };
}

/**
 * HAUT AUFZIEHEN — Gewichte für ein Teil ausrechnen.
 *
 * Das Verfahren ist bewusst eindimensional: Ein Vertex wird auf eine
 * ACHSE projiziert, und entlang dieser Achse wird das Gewicht von einem
 * Knochen an den nächsten übergeben. Für diese Figur ist das genau
 * richtig und nicht etwa eine Vereinfachung — Rumpf, Arm und
 * Kükenkörper sind Rotationskörper um eine Achse. Automatische
 * Verfahren (Abstand zum Knochensegment, Wärmeleitung) raten dasselbe,
 * nur unvorhersehbar: Ein Flügel, der neben dem Bauch hängt, bekäme
 * Bauchgewicht, und dann zieht ein Schulterschwenk am Rumpf.
 *
 * Ein Übergang ist eine Smoothstep-Rampe `bei … bei + breite` entlang
 * der Achse. Das ist derselbe Verlauf, den `armBeugen` in `szene.mjs`
 * von Hand gerechnet hat (`BEUGE_ZONE = 2 cm`) — nur jetzt einmal für
 * alle Gelenke, und im Shader statt in einer Schleife über die Punkte.
 *
 * Gewicht des j-ten Knochens = f(j−1) − f(j), mit f(−1) = 1 und f(n) = 0.
 * Weil die Rampen aufsteigend geordnet sind, ist das nie negativ und
 * summiert sich auf genau 1. `pruefen-modell.mjs` misst nach.
 */
export function hauteAn(THREE, geo, kette, knochen) {
  const finde = (name) => {
    const k = knochen.get(name);
    if (!k) throw new Error(`Haut verweist auf unbekannten Knochen „${name}"`);
    return k;
  };
  const achse = new THREE.Vector3(...kette.achse).normalize();
  const ursprung = typeof kette.ursprung === 'string'
    ? finde(kette.ursprung).absolut.clone()
    : new THREE.Vector3(...kette.ursprung);

  const folge = [finde(kette.knochen), ...kette.uebergaenge.map((u) => finde(u.zu))];
  const rampen = kette.uebergaenge;
  for (let i = 1; i < rampen.length; i++) {
    if (rampen[i].bei < rampen[i - 1].bei) {
      throw new Error('Übergänge müssen entlang der Achse aufsteigend geordnet sein');
    }
  }

  const pos = geo.attributes.position;
  const idx = new Uint16Array(pos.count * 4);
  const gew = new Float32Array(pos.count * 4);
  const v = new THREE.Vector3();
  const f = new Array(rampen.length);
  const anteile = new Array(folge.length);

  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).sub(ursprung);
    const s = v.dot(achse);
    for (let j = 0; j < rampen.length; j++) {
      f[j] = glatt((s - rampen[j].bei) / rampen[j].breite);
    }
    let summe = 0;
    for (let j = 0; j < folge.length; j++) {
      const vor = j === 0 ? 1 : f[j - 1];
      const nach = j < f.length ? f[j] : 0;
      anteile[j] = Math.max(0, vor - nach);
      summe += anteile[j];
    }
    /* Die vier stärksten Knochen — mehr kann ein Vertex in three nicht
       tragen. Bei geordneten Rampen sind es ohnehin nie mehr als zwei;
       die Auswahl ist die Versicherung gegen einen späteren Bauplan mit
       überlappenden Übergängen. */
    const rang = anteile.map((w, j) => [w, j])
      .sort((a, b) => b[0] - a[0]).slice(0, 4);
    const rest = rang.reduce((n, [w]) => n + w, 0) || 1;
    for (let k = 0; k < 4; k++) {
      const [w, j] = rang[k] ?? [0, 0];
      idx[i * 4 + k] = folge[j].index;
      gew[i * 4 + k] = (summe > 0 ? w / rest : (k === 0 ? 1 : 0));
    }
  }
  geo.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(idx, 4));
  geo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(gew, 4));
  return geo;
}

/**
 * Eine Kette entlang zweier Knochen — der häufige Fall (Arm, Flügel).
 *
 * Achse und Umschaltpunkt ergeben sich aus den Knochen SELBST: Wer den
 * Ellbogen verschiebt, verschiebt damit die Gewichtsgrenze. Vorher stand
 * dieselbe Zahl doppelt da (einmal als Gelenkposition, einmal als
 * Drehpunkt in `userData.arm`) und musste von Hand nachgezogen werden.
 */
export function glied(knochen, kette, breiten) {
  if (kette.length < 2) throw new Error('Glied braucht mindestens zwei Knochen');
  if (breiten.length !== kette.length - 1) {
    throw new Error(`Glied ${kette.join(' → ')}: ${kette.length - 1} Übergänge, `
      + `aber ${breiten.length} Breiten`);
  }
  const teile = kette.map((name) => {
    const k = knochen.get(name);
    if (!k) throw new Error(`Glied ${kette.join(' → ')}: Knochen „${name}" fehlt`);
    return k;
  });
  /* Die Achse ist die Richtung vom ersten zum LETZTEN Knochen. Bei einem
     Arm mit Ellbogen UND Handgelenk liegen die Zwischenstationen nicht
     exakt darauf; sie werden deshalb auf die Achse projiziert. Das ist
     richtig so: Gemessen wird, wie weit ein Punkt das Glied hinunter
     liegt, nicht sein Abstand zum Knochen. */
  const achse = teile[teile.length - 1].absolut.clone().sub(teile[0].absolut);
  const laenge = achse.length();
  if (laenge < 1e-6) throw new Error(`Glied ${kette.join(' → ')}: gleiche Lage`);
  achse.normalize();
  return {
    knochen: kette[0],
    ursprung: kette[0],
    achse: achse.toArray(),
    uebergaenge: teile.slice(1).map((k, i) => ({
      zu: kette[i + 1],
      bei: k.absolut.clone().sub(teile[0].absolut).dot(achse),
      breite: breiten[i],
    })),
  };
}
