/* Lotti, die Lotsenmöwe — 3D-Modell aus den Werten von components/mascot.tsx.
   baueLotti(THREE) liefert eine THREE.Group mit benannten Teilen und Materialien.
   Maße in Metern, y-up, Standfläche auf y = 0, Gesamthöhe ca. 24 cm.

   HERKUNFT: 1:1 aus dem Claude-Design-Projekt „Design-Analyse und
   Verbesserungen" (lotti-modell.js, Projekt 2e1e6508-…), auf dem Weg über
   `studio/lotti-modell.js` im Repo ratslotse-social — dort liegt die
   jeweils aktuelle Kopie samt Render-Werkzeug. Das Design-Projekt ist die
   Quelle der Wahrheit für die Figur: Änderungen an Lotti dort machen und
   über das Studio hierher zurückkopieren, nicht andersherum.

   Stand: studio/lotti-modell.js vom 20.08.2026 (spitzer Schnabel, Iris mit
   Pupille, Kopf-Gelenk, Schultern 1,2 cm tiefer). Nur TypeScript-Typen
   sind hiesige Zutat. */
import type * as THREE_NS from "three";

type TH = typeof THREE_NS;
type Grp = THREE_NS.Group;

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
function schnabelForm(THREE: TH, laenge: number, breite: number, dicke: number) {
  const g = new THREE.LatheGeometry(([
    [0.00, 0.00], [0.97, 0.03], [1.00, 0.14], [0.97, 0.32],
    [0.88, 0.50], [0.73, 0.67], [0.54, 0.81], [0.32, 0.92],
    [0.13, 0.98], [0.00, 1.00],
  ] as [number, number][]).map(([r, t]) => new THREE.Vector2(r * breite, t * laenge)), 30);
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
function keilen(geo: THREE_NS.BufferGeometry, laenge: number) {
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const z = pos.getZ(i);
    pos.setY(i, pos.getY(i) * Math.min(Math.max(z / laenge, 0), 1));
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
}

export function baueLotti(THREE: TH, opt: { augen?: string; pose?: string; schnabel?: number } = {}): Grp {
  const augenZu = opt.augen === 'zu';           // Lidschlag-Variante für die Hero-Animation
  const winkt   = opt.pose === 'winkt';         // rechter Flügel erhoben
  const schnabelAuf = opt.schnabel ?? 0;        // Öffnung, siehe Rachen unten
  const S = 0.0018;                       // SVG-Einheit (200×200) → Meter
  // Höhe des Kopf-Drehpunkts: unter dem Schnabel (y ≈ 0.123), wo bei einem
  // Vogel der Hals ansitzt. Weiter oben sähe die Neigung aus, als rutschte
  // das Gesicht; weiter unten kippt wieder der halbe Körper mit.
  const KOPF_DREHPUNKT = 0.095;
  const TIEFE = 1.02;                     // Rumpf vorne–hinten minimal tiefer als breit
  const V2 = (r: number, y: number) => new THREE.Vector2(r, y);

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
  };

  const lotti = new THREE.Group();
  lotti.name = 'lotti';
  const teil = (name: string, geo: THREE_NS.BufferGeometry, material: THREE_NS.Material, ziel: THREE_NS.Object3D = lotti) => {
    const m = new THREE.Mesh(geo, material);
    m.name = name;
    m.castShadow = true;
    m.receiveShadow = true;
    ziel.add(m);
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
  teil('koerper', koerperGeo, M.koerper);

  /* ── Schwanzfedern ── */
  const schwanzGelenk = new THREE.Group();
  schwanzGelenk.name = 'schwanz-gelenk';
  schwanzGelenk.position.set(0, 0.075, -0.030);
  lotti.add(schwanzGelenk);
  const schwanz = new THREE.SphereGeometry(0.037, 28, 18);
  schwanz.scale(0.92, 0.26, 1.80);
  schwanz.rotateX(0.24);
  schwanz.translate(0, 0.0615 - 0.075, -0.0705 + 0.030);
  teil('schwanz', schwanz, M.gefieder, schwanzGelenk);

  /* ── Flügel an einem Schultergelenk, damit sie sich heben und winken lassen ── */
  ([['links', 1], ['rechts', -1]] as [string, number][]).forEach(([seite, v]) => {
    /* Die Schulter saß bei y = 0,148 — auf einer 0,22 m hohen Figur sind
     * das 67 % der Höhe, also direkt unter der Mützenkrempe. Die Arme
     * wuchsen dadurch optisch aus dem Kopf, und gehobene Flügel stießen
     * schon bei 55° an den Hut (Tims Befund 20.08.26). 1,2 cm tiefer.
     *
     * Der ganze Arm wandert mit: Weil die Geometrie unten mit `- py`
     * verschoben wird, bleibt jede relative Lage erhalten — es genügt,
     * dieselben 0,012 auch von den y-Werten der Teile abzuziehen. */
    const px = v * 0.0700, py = 0.1360, pz = 0.0020;
    const schulter = new THREE.Group();
    schulter.name = 'schulter-' + seite;
    schulter.position.set(px, py, pz);
    lotti.add(schulter);

    /* EIN Federkörper, der sich BIEGT — kein zweiter Körper daran.
     *
     * Zwei Anläufe waren falsch: Erst saß das Gelenk an der dunklen Spitze
     * (ein Handgelenk, kein Ellbogen), dann teilte ich den weißen Arm in
     * zwei Ellipsoide — und die sahen aus wie zwei Arme aneinander (Tims
     * Befund 20.08.26). Ein Ellipsoid läuft an beiden Enden spitz zu, jede
     * Überlappung zeigt deshalb eine Taille; eine Füllung dagegenzusetzen
     * erzeugte nur einen Knubbel wie an einer Actionfigur.
     *
     * Der Arm ist wieder EIN Mesh. Gebeugt wird die GEOMETRIE:
     * `armBeugen()` in `szene.mjs` dreht die Punkte unterhalb des Ellbogens
     * um ihn herum, mit weichem Übergang über zwei Zentimeter. Das geht
     * hier, weil die Figur für jedes Bild neu gebaut wird — die Geometrie
     * gehört genau dieser einen Lotti.
     *
     * Länge 1.20 statt 1.06: Auf einem kurzen Flügel hat ein Knick keinen
     * Platz. Die Mitte rutscht um den halben Zuwachs nach unten, damit die
     * Schulter bleibt, wo sie war. */
    const feder = new THREE.SphereGeometry(0.0445, 34, 26);
    feder.scale(0.26, 1.13, 0.80);
    feder.rotateZ(v * -0.15);
    feder.rotateY(v * 0.12);
    feder.translate(v * 0.0842 - px, 0.0863 - py, 0.0015 - pz);
    teil('fluegel-' + seite, feder, M.gefieder, schulter);

    const spitze = new THREE.SphereGeometry(0.0205, 26, 20);
    spitze.scale(0.30, 0.92, 1.05);
    spitze.rotateZ(v * -0.30);
    spitze.rotateY(v * 0.12);
    spitze.translate(v * 0.0818 - px, 0.0419 - py, -0.0135 - pz);
    teil('fluegelspitze-' + seite, spitze, M.spitze, schulter);

    /* ── Ellbogen ──────────────────────────────────────────────────────
       Der Drehpunkt liegt MITTIG im weißen Arm (y ≈ 0,095), nicht an der
       dunklen Spitze. Die Spitze ist die Hand: Sie hängt am Gelenk und
       dreht als Ganzes mit. Der weiße Arm dreht NICHT mit — seine Punkte
       werden gebogen, siehe oben.

       Die Kennwerte gehen an die Schulter, damit `szene.mjs` sie nicht
       nachrechnen muss. Die Achse ist die Längsrichtung des Arms: Die
       Geometrie ist um `v * -0.15` gekippt, ihr +y zeigt deshalb
       (0,1494·v / 0,9888 / 0). */
    const ellbogen = gelenkUm(THREE, schulter, 'ellbogen-' + seite,
                              [v * 0.0836 - px, 0.0826 - py, 0.0015 - pz],
                              ['fluegelspitze-' + seite]);
    schulter.userData.arm = {
      drehpunkt: ellbogen.position.toArray(),
      achse: [0.1494 * v, 0.9888, 0],
      mesh: 'fluegel-' + seite,
    };

    if (winkt && v === -1) schulter.rotation.z = -1.58;
  });

  /* ── Schwimmfüße: geschlossener Fächer statt aufgeschnittenem Zylinder ── */
  const fussForm = new THREE.Shape();
  fussForm.moveTo(-0.0085, -0.0125);
  fussForm.quadraticCurveTo(0, -0.0205, 0.0085, -0.0125);
  fussForm.quadraticCurveTo(0.0262, 0.0045, 0.0238, 0.0280);
  fussForm.quadraticCurveTo(0, 0.0362, -0.0238, 0.0280);
  fussForm.quadraticCurveTo(-0.0262, 0.0045, -0.0085, -0.0125);
  ([['links', 1], ['rechts', -1]] as [string, number][]).forEach(([seite, v]) => {
    const fuss = new THREE.ExtrudeGeometry(fussForm, {
      depth: 0.0062, curveSegments: 22, bevelEnabled: true,
      bevelThickness: 0.0024, bevelSize: 0.0026, bevelSegments: 3,
    });
    fuss.rotateX(Math.PI / 2);
    fuss.rotateY(v * 0.30);
    fuss.translate(v * 0.0305, 0.0092, 0.0405);
    teil('fuss-' + seite, fuss, M.schnabelD);
  });

  /* ── Augen mit zwei Glanzpunkten ── */
  ([['links', 1], ['rechts', -1]] as [string, number][]).forEach(([seite, v]) => {
    const ax = v * 0.0332, ay = 0.1478, az = 0.0650;
    const gelenk = new THREE.Group();
    gelenk.name = 'auge-gelenk-' + seite;
    gelenk.position.set(ax, ay, az);
    lotti.add(gelenk);

    if (augenZu) {
      const lid = new THREE.TorusGeometry(0.0132, 0.0026, 10, 22, Math.PI * 0.86);
      lid.rotateZ(Math.PI + Math.PI * 0.07);
      lid.translate(0, 0.0042, 0.0128);
      teil('auge-' + seite, lid, M.lid, gelenk);
      return;
    }
    const aug = new THREE.SphereGeometry(0.0178, 34, 26);
    aug.scale(1, 1.06, 0.88);
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
    pup.translate(0, 0, 0.0099);
    teil('pupille-' + seite, pup, M.pupille, gelenk);

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
    gross.translate(-0.0038, 0.0042, 0.0150);
    teil('augenglanz-' + seite, gross, M.glanz, gelenk);

    const klein = new THREE.SphereGeometry(0.0014, 14, 10);
    klein.translate(0.0042, -0.0044, 0.0146);
    teil('augenglanz-klein-' + seite, klein, M.glanz, gelenk);
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
  teil('schnabel-oben', oben, M.schnabel);

  // Unterschnabel: kürzer, schmaler und flacher, damit der Oberschnabel
  // vorn überhängt. Vorher stand er als dunkler Lappen darunter hervor und
  // las sich als herausgestreckte Zunge.
  const unten = schnabelForm(THREE, 0.0620, 0.0196, 0.0076);
  unten.rotateX(0.15);
  unten.translate(0, 0.1246, 0.0494);
  teil('schnabel-unten', unten, M.schnabelD);

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
    teil('rachen', rachen, M.rachen);
  }

  /* Der Drehpunkt liegt VORN an der Schnabelwurzel, wo die Hälften aus dem
     Gefieder treten. Zuerst saß er weiter hinten, tief im Kopf — dadurch
     klaffte die Öffnung schon dort auseinander, wo noch Kopf ist. */
  gelenkUm(THREE, lotti, 'schnabel-gelenk', [0, 0.1268, 0.0600],
           ['schnabel-unten', 'rachen']);

  /* ── Wangen ── */
  ([['links', 1], ['rechts', -1]] as [string, number][]).forEach(([seite, v]) => {
    const w = new THREE.SphereGeometry(0.0155, 26, 18);
    w.scale(1, 0.66, 0.30);
    w.rotateY(v * 0.72);
    w.translate(v * 0.0556, 0.1262, 0.0612);
    teil('wange-' + seite, w, M.wange);
  });

  /* ── Kapitänsmütze ── */
  const muetze = new THREE.Group();
  muetze.name = 'muetze';
  const muetzenTeil = (name: string, geo: THREE_NS.BufferGeometry, material: THREE_NS.Material) => {
    geo.scale(1, 1, 1.04);
    return teil(name, geo, material, muetze);
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
  lotti.add(muetze);

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
  const kopf = gelenkUm(THREE, lotti, 'kopf', [0, KOPF_DREHPUNKT, 0],
    ['auge-gelenk-links', 'auge-gelenk-rechts',
     'schnabel-oben', 'schnabel-gelenk',
     'wange-links', 'wange-rechts', 'muetze']);
  // Wer einen Hut an den Scheitel setzt, muss denselben Versatz abziehen.
  lotti.userData.kopfDrehpunkt = KOPF_DREHPUNKT;
  void kopf;

  /* ── Fuß-Gelenke ──────────────────────────────────────────────────────
     Die Füße saßen ohne Gelenk am Rumpf: In jeder Pose standen beide exakt
     parallel und flach — der Grund, warum die Figur auch mit lebendigem
     Kopf noch aufgestellt statt stehend wirkte. Standbein und Spielbein
     sind der älteste Trick der Figurenzeichnung.

     Der Drehpunkt liegt an der Ferse, hinten am Fuß, nicht in seiner Mitte:
     Um die Mitte gedreht sähe ein gehobener Fuß aus, als schwebte er. */
  for (const [seite, v] of [['links', 1], ['rechts', -1]] as [string, number][]) {
    gelenkUm(THREE, lotti, 'fuss-gelenk-' + seite,
             [v * 0.0305, 0.0092, 0.0405 - 0.0180], ['fuss-' + seite]);
  }

  return lotti;
}

/**
 * Teile unter einer neuen Gruppe zusammenfassen, die sich drehen lässt.
 *
 * DIE FALLE, dreimal zugeschlagen: Die Teile tragen ihre Lage teils in der
 * GEOMETRIE (`geo.translate(...)`, Objekt sitzt bei 0,0,0), teils in
 * `position`. Wer sie schlicht umhängt, verschiebt sie um den ganzen
 * Drehpunkt — beim Kopf fuhr das komplette Gesicht über die Mütze. Deshalb
 * wird der Drehpunkt beim Umhängen abgezogen.
 *
 * Namen, die es nicht gibt oder die schon woanders hängen, werden
 * übersprungen: Die Figur wird je nach Optionen unterschiedlich gebaut
 * (`augenZu` etwa ersetzt die Augen durch Lidbögen).
 */
function gelenkUm(THREE: TH, figur: Grp, name: string, [px, py, pz]: [number, number, number], namen: string[]) {
  const gelenk = new THREE.Group();
  gelenk.name = name;
  gelenk.position.set(px, py, pz);
  figur.add(gelenk);
  for (const n of namen) {
    const t = figur.getObjectByName(n);
    if (!t || t.parent !== figur) continue;
    t.position.set(t.position.x - px, t.position.y - py, t.position.z - pz);
    gelenk.add(t);                  // add() hängt automatisch vom Rumpf ab
  }
  return gelenk;
}

/* ── Küken: kleiner, runder, ohne Mütze — nach dem Chick aus mascot.tsx ── */
export function baueKueken(THREE: TH, opt: { ton?: string } = {}): Grp {
  const gold = opt.ton === 'gold';
  const K = 0.00105;                       // SVG-Einheit (120×120) → Meter, Küken ca. 9 cm
  const kx = (X: number) => (X - 60) * K;
  const ky = (Y: number) => (116 - Y) * K;

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
  const teil = (name: string, geo: THREE_NS.BufferGeometry, material: THREE_NS.Material, ziel: THREE_NS.Object3D = kueken) => {
    const m = new THREE.Mesh(geo, material);
    m.name = name;
    m.castShadow = true;
    m.receiveShadow = true;
    ziel.add(m);
    return m;
  };

  const koerper = new THREE.SphereGeometry(0.0357, 40, 30);
  koerper.scale(1, 0.95, 0.97);
  koerper.translate(0, 0.0424, 0);
  teil('kueken-koerper', koerper, M.koerper);

  ([['links', 1], ['rechts', -1]] as [string, number][]).forEach(([seite, v]) => {
    const schulter = new THREE.Group();
    schulter.name = 'kueken-schulter-' + seite;
    schulter.position.set(v * 0.0300, 0.0560, 0.0010);
    kueken.add(schulter);
    const fl = new THREE.SphereGeometry(0.0192, 26, 20);
    fl.scale(0.28, 1.02, 0.82);
    fl.rotateZ(v * -0.16);
    fl.translate(v * 0.0038, -0.0155, 0);
    teil('kueken-fluegel-' + seite, fl, M.gefieder, schulter);

    const gelenk = new THREE.Group();
    gelenk.name = 'kueken-auge-gelenk-' + seite;
    gelenk.position.set(v * 0.0128, 0.0478, 0.0292);
    kueken.add(gelenk);

    const aug = new THREE.SphereGeometry(0.0084, 26, 20);
    aug.scale(1, 1.05, 0.90);
    teil('kueken-auge-' + seite, aug, M.auge, gelenk);

    const pup = new THREE.SphereGeometry(0.0050, 20, 16);
    pup.scale(1, 1.02, 0.62);
    pup.translate(0, 0, 0.0046);
    teil('kueken-pupille-' + seite, pup, M.pupille, gelenk);

    const gl = new THREE.SphereGeometry(0.0015, 16, 12);
    gl.translate(-0.0018, 0.0020, 0.0074);
    teil('kueken-glanz-' + seite, gl, M.glanz, gelenk);

    const w = new THREE.SphereGeometry(0.0072, 20, 14);
    w.scale(1, 0.66, 0.30);
    w.rotateY(v * 0.74);
    w.translate(v * 0.0236, 0.0348, 0.0250);
    teil('kueken-wange-' + seite, w, M.wange);

    const f = new THREE.SphereGeometry(0.0088, 18, 12);
    f.scale(0.86, 0.34, 1.30);
    f.translate(v * 0.0128, 0.0032, 0.0128);
    teil('kueken-fuss-' + seite, f, M.fuss);
  });

  const schnabel = schnabelForm(THREE, 0.0300, 0.0100, 0.0052);
  schnabel.rotateX(0.14);
  schnabel.translate(0, 0.0370, 0.0206);
  teil('kueken-schnabel', schnabel, M.schnabel);

  const bueschel = new THREE.SphereGeometry(0.0062, 18, 14);
  bueschel.scale(0.55, 1.75, 0.55);
  bueschel.rotateZ(-0.34);
  bueschel.translate(0.0028, 0.0855, -0.0016);
  teil('kueken-bueschel', bueschel, M.gefieder);

  const bueschel2 = new THREE.SphereGeometry(0.0052, 18, 14);
  bueschel2.scale(0.55, 1.45, 0.55);
  bueschel2.rotateZ(0.30);
  bueschel2.translate(-0.0044, 0.0822, -0.0022);
  teil('kueken-bueschel-2', bueschel2, M.gefieder);

  /* ── Kopf und Füße wie bei Lotti ──────────────────────────────────────
     Ein Küken ist im Grunde eine Kugel; einen Hals hat es nicht. Der
     Drehpunkt liegt deshalb tief, knapp über der Körpermitte — dreht man
     weiter oben, wandert das Gesicht sichtbar über die Kugel statt sich zu
     neigen. Die Federbüschel gehören mit an den Kopf: Sie sind das, was die
     Neigung bei dieser Figur überhaupt lesbar macht. */
  gelenkUm(THREE, kueken, 'kopf', [0, 0.0300, 0],
    ['kueken-auge-gelenk-links', 'kueken-auge-gelenk-rechts',
     'kueken-wange-links', 'kueken-wange-rechts',
     'kueken-schnabel', 'kueken-bueschel', 'kueken-bueschel-2']);
  kueken.userData.kopfDrehpunkt = 0.0300;

  for (const [seite, v] of [['links', 1], ['rechts', -1]] as [string, number][]) {
    gelenkUm(THREE, kueken, 'fuss-gelenk-' + seite,
             [v * 0.0128, 0.0032, 0.0128 - 0.0075], ['kueken-fuss-' + seite]);
  }

  return kueken;
}
