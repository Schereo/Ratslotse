/* Lotti, die Lotsenmöwe, als 3D-Modell — aus dem Design-Projekt übernommen
 * („Lotti Hero Familie", lotti-modell.js). Die Maße stammen ihrerseits aus
 * components/mascot.tsx, dem SVG-Maskottchen: Es ist dieselbe Figur, nur in
 * Metern statt in SVG-Einheiten. Wer die Zeichnung ändert, muss hier nachziehen.
 *
 * Bewusst unverändert übernommen. Jede „Verbesserung" an den Zahlen bricht die
 * Ähnlichkeit zur gezeichneten Lotti, und die ist der ganze Punkt.
 *
 * y-up, Standfläche auf y = 0, Gesamthöhe rund 24 cm.
 */
import type * as THREE_NS from "three";

type TH = typeof THREE_NS;

export function baueLotti(THREE: TH, opt: { augen?: string; pose?: string } = {}): THREE_NS.Group {
  const augenZu = opt.augen === "zu";           // Lidschlag-Variante für die Hero-Animation
  const winkt = opt.pose === "winkt";           // rechter Flügel erhoben
  const TIEFE = 1.02;                           // Rumpf vorne–hinten minimal tiefer als breit
  const V2 = (r: number, y: number) => new THREE.Vector2(r, y);

  const M = {
    koerper:   new THREE.MeshStandardMaterial({ name: "koerper-weiss",   color: "#FBFDFF", roughness: 0.62, metalness: 0.02 }),
    gefieder:  new THREE.MeshStandardMaterial({ name: "gefieder",        color: "#C7D6E4", roughness: 0.72, metalness: 0.02 }),
    spitze:    new THREE.MeshStandardMaterial({ name: "gefieder-spitze", color: "#8CA6BC", roughness: 0.72, metalness: 0.02 }),
    navy:      new THREE.MeshStandardMaterial({ name: "muetze-navy",     color: "#143A5C", roughness: 0.55, metalness: 0.05 }),
    navyTief:  new THREE.MeshStandardMaterial({ name: "muetze-dunkel",   color: "#0A1F33", roughness: 0.32, metalness: 0.10 }),
    auge:      new THREE.MeshStandardMaterial({ name: "auge",            color: "#122A40", roughness: 0.16, metalness: 0.05 }),
    glanz:     new THREE.MeshStandardMaterial({ name: "auge-glanz",      color: "#FFFFFF", roughness: 0.10, metalness: 0.00, emissive: "#FFFFFF", emissiveIntensity: 0.30 }),
    schnabel:  new THREE.MeshStandardMaterial({ name: "schnabel",        color: "#F66623", roughness: 0.42, metalness: 0.03 }),
    schnabelD: new THREE.MeshStandardMaterial({ name: "schnabel-dunkel", color: "#D9531E", roughness: 0.46, metalness: 0.03 }),
    gold:      new THREE.MeshStandardMaterial({ name: "gold",            color: "#F7CB63", roughness: 0.28, metalness: 0.38 }),
    wange:     new THREE.MeshStandardMaterial({ name: "wange",           color: "#FFAD85", roughness: 0.85, metalness: 0.00 }),
  };

  const lotti = new THREE.Group();
  lotti.name = "lotti";
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
  teil("koerper", koerperGeo, M.koerper);

  /* ── Schwanzfedern ── */
  const schwanzGelenk = new THREE.Group();
  schwanzGelenk.name = "schwanz-gelenk";
  schwanzGelenk.position.set(0, 0.075, -0.030);
  lotti.add(schwanzGelenk);
  const schwanz = new THREE.SphereGeometry(0.037, 28, 18);
  schwanz.scale(0.92, 0.26, 1.80);
  schwanz.rotateX(0.24);
  schwanz.translate(0, 0.0615 - 0.075, -0.0705 + 0.030);
  teil("schwanz", schwanz, M.gefieder, schwanzGelenk);

  /* ── Flügel an einem Schultergelenk, damit sie sich heben und winken lassen ── */
  ([["links", 1], ["rechts", -1]] as const).forEach(([seite, v]) => {
    const px = v * 0.0700, py = 0.1480, pz = 0.0020;
    const schulter = new THREE.Group();
    schulter.name = "schulter-" + seite;
    schulter.position.set(px, py, pz);
    lotti.add(schulter);

    const feder = new THREE.SphereGeometry(0.0445, 34, 26);
    feder.scale(0.26, 1.06, 0.80);
    feder.rotateZ(v * -0.15);
    feder.rotateY(v * 0.12);
    feder.translate(v * 0.0842 - px, 0.1045 - py, 0.0015 - pz);
    teil("fluegel-" + seite, feder, M.gefieder, schulter);

    const spitze = new THREE.SphereGeometry(0.0205, 26, 20);
    spitze.scale(0.30, 0.92, 1.05);
    spitze.rotateZ(v * -0.30);
    spitze.rotateY(v * 0.12);
    spitze.translate(v * 0.0818 - px, 0.0632 - py, -0.0135 - pz);
    teil("fluegelspitze-" + seite, spitze, M.spitze, schulter);

    if (winkt && v === -1) schulter.rotation.z = -1.58;
  });

  /* ── Schwimmfüße: geschlossener Fächer statt aufgeschnittenem Zylinder ── */
  const fussForm = new THREE.Shape();
  fussForm.moveTo(-0.0085, -0.0125);
  fussForm.quadraticCurveTo(0, -0.0205, 0.0085, -0.0125);
  fussForm.quadraticCurveTo(0.0262, 0.0045, 0.0238, 0.0280);
  fussForm.quadraticCurveTo(0, 0.0362, -0.0238, 0.0280);
  fussForm.quadraticCurveTo(-0.0262, 0.0045, -0.0085, -0.0125);
  ([["links", 1], ["rechts", -1]] as const).forEach(([seite, v]) => {
    const fuss = new THREE.ExtrudeGeometry(fussForm, {
      depth: 0.0062, curveSegments: 22, bevelEnabled: true,
      bevelThickness: 0.0024, bevelSize: 0.0026, bevelSegments: 3,
    });
    fuss.rotateX(Math.PI / 2);
    fuss.rotateY(v * 0.30);
    fuss.translate(v * 0.0305, 0.0092, 0.0405);
    teil("fuss-" + seite, fuss, M.schnabelD);
  });

  /* ── Augen mit zwei Glanzpunkten ── */
  ([["links", 1], ["rechts", -1]] as const).forEach(([seite, v]) => {
    const ax = v * 0.0332, ay = 0.1478, az = 0.0650;
    const gelenk = new THREE.Group();
    gelenk.name = "auge-gelenk-" + seite;
    gelenk.position.set(ax, ay, az);
    lotti.add(gelenk);

    if (augenZu) {
      const lid = new THREE.TorusGeometry(0.0132, 0.0026, 10, 22, Math.PI * 0.86);
      lid.rotateZ(Math.PI + Math.PI * 0.07);
      lid.translate(0, 0.0042, 0.0128);
      teil("auge-" + seite, lid, M.auge, gelenk);
      return;
    }
    const aug = new THREE.SphereGeometry(0.0178, 34, 26);
    aug.scale(1, 1.06, 0.88);
    teil("auge-" + seite, aug, M.auge, gelenk);

    const gross = new THREE.SphereGeometry(0.0066, 22, 16);
    gross.translate(-0.0062, 0.0058, 0.0122);
    teil("augenglanz-" + seite, gross, M.glanz, gelenk);

    const klein = new THREE.SphereGeometry(0.0029, 14, 10);
    klein.translate(0.0074, -0.0064, 0.0112);
    teil("augenglanz-klein-" + seite, klein, M.glanz, gelenk);
  });

  /* ── Schnabel: kurzer weicher Wulst, darunter die dunkle Unterhälfte ── */
  const oben = new THREE.SphereGeometry(0.0218, 32, 22);
  oben.scale(1.00, 0.54, 1.42);
  oben.rotateX(0.10);
  oben.translate(0, 0.1332, 0.0810);
  teil("schnabel-oben", oben, M.schnabel);

  const unten = new THREE.SphereGeometry(0.0182, 26, 18);
  unten.scale(0.86, 0.30, 1.16);
  unten.rotateX(0.16);
  unten.translate(0, 0.1232, 0.0778);
  teil("schnabel-unten", unten, M.schnabelD);

  /* ── Wangen ── */
  ([["links", 1], ["rechts", -1]] as const).forEach(([seite, v]) => {
    const w = new THREE.SphereGeometry(0.0155, 26, 18);
    w.scale(1, 0.66, 0.30);
    w.rotateY(v * 0.72);
    w.translate(v * 0.0556, 0.1262, 0.0612);
    teil("wange-" + seite, w, M.wange);
  });

  /* ── Kapitänsmütze ── */
  const muetze = new THREE.Group();
  muetze.name = "muetze";
  const muetzenTeil = (name: string, geo: THREE_NS.BufferGeometry, material: THREE_NS.Material) => {
    geo.scale(1, 1, 1.04);
    return teil(name, geo, material, muetze);
  };

  muetzenTeil("muetzen-krone", new THREE.LatheGeometry([
    V2(0, 0.1795), V2(0.0745, 0.1800), V2(0.0768, 0.1880), V2(0.0755, 0.1962),
    V2(0.0702, 0.2062), V2(0.0602, 0.2158), V2(0.0432, 0.2248), V2(0.0242, 0.2300), V2(0, 0.2322),
  ], 64), M.navy);

  // geschlossener Zylinder: ein offener hätte von unten und an den Kanten Löcher gezeigt
  muetzenTeil("muetzen-bund", new THREE.CylinderGeometry(0.0772, 0.0764, 0.0145, 64)
    .translate(0, 0.1855, 0), M.navyTief);

  muetzenTeil("muetzen-litze", new THREE.TorusGeometry(0.0776, 0.0021, 12, 72)
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
  muetzenTeil("muetzen-schirm", schirm, M.navyTief);

  const emblem = new THREE.CylinderGeometry(0.0152, 0.0152, 0.0052, 40);
  emblem.rotateX(Math.PI / 2 - 0.34);
  emblem.translate(0, 0.2046, 0.0710);
  muetzenTeil("muetzen-emblem", emblem, M.gold);

  const sternForm = new THREE.Shape();
  const ZACKEN = 4, RA = 0.0091, RI = 0.0045;
  for (let i = 0; i < ZACKEN * 2; i++) {
    const r = i % 2 === 0 ? RA : RI;
    const a = (i / (ZACKEN * 2)) * Math.PI * 2 + Math.PI / 2;
    const px = Math.cos(a) * r, py = Math.sin(a) * r;
    if (i === 0) sternForm.moveTo(px, py); else sternForm.lineTo(px, py);
  }
  sternForm.closePath();
  const stern = new THREE.ExtrudeGeometry(sternForm, { depth: 0.0022, bevelEnabled: false });
  stern.rotateX(-0.34);
  stern.translate(0, 0.2046, 0.0731);
  muetzenTeil("muetzen-stern", stern, M.navyTief);

  muetze.rotation.x = -0.085;               // leicht in den Nacken gekippt
  muetze.rotation.z = 0.045;
  lotti.add(muetze);

  return lotti;
}

/* ── Küken: kleiner, runder, ohne Mütze — nach dem Chick aus mascot.tsx ── */
export function baueKueken(THREE: TH, opt: { ton?: string } = {}): THREE_NS.Group {
  const gold = opt.ton === "gold";

  const M = {
    koerper:  new THREE.MeshStandardMaterial({ name: "kueken-weiss",    color: "#FBFDFF", roughness: 0.66, metalness: 0.02 }),
    gefieder: new THREE.MeshStandardMaterial({ name: "kueken-gefieder", color: "#C7D6E4", roughness: 0.74, metalness: 0.02 }),
    auge:     new THREE.MeshStandardMaterial({ name: "kueken-auge",     color: "#122A40", roughness: 0.16, metalness: 0.05 }),
    glanz:    new THREE.MeshStandardMaterial({ name: "kueken-glanz",    color: "#FFFFFF", roughness: 0.10, metalness: 0.00, emissive: "#FFFFFF", emissiveIntensity: 0.30 }),
    schnabel: new THREE.MeshStandardMaterial({ name: "kueken-schnabel", color: gold ? "#F2B441" : "#F66623", roughness: 0.44, metalness: 0.03 }),
    fuss:     new THREE.MeshStandardMaterial({ name: "kueken-fuss",     color: gold ? "#D99A1F" : "#D9531E", roughness: 0.48, metalness: 0.03 }),
    wange:    new THREE.MeshStandardMaterial({ name: "kueken-wange",    color: "#FFAD85", roughness: 0.85, metalness: 0.00 }),
  };

  const kueken = new THREE.Group();
  kueken.name = "kueken";
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
  teil("kueken-koerper", koerper, M.koerper);

  ([["links", 1], ["rechts", -1]] as const).forEach(([seite, v]) => {
    const schulter = new THREE.Group();
    schulter.name = "kueken-schulter-" + seite;
    schulter.position.set(v * 0.0300, 0.0560, 0.0010);
    kueken.add(schulter);
    const fl = new THREE.SphereGeometry(0.0192, 26, 20);
    fl.scale(0.28, 1.02, 0.82);
    fl.rotateZ(v * -0.16);
    fl.translate(v * 0.0038, -0.0155, 0);
    teil("kueken-fluegel-" + seite, fl, M.gefieder, schulter);

    const gelenk = new THREE.Group();
    gelenk.name = "kueken-auge-gelenk-" + seite;
    gelenk.position.set(v * 0.0128, 0.0478, 0.0292);
    kueken.add(gelenk);

    const aug = new THREE.SphereGeometry(0.0084, 26, 20);
    aug.scale(1, 1.05, 0.90);
    teil("kueken-auge-" + seite, aug, M.auge, gelenk);

    const gl = new THREE.SphereGeometry(0.0033, 16, 12);
    gl.translate(-0.0029, 0.0027, 0.0060);
    teil("kueken-glanz-" + seite, gl, M.glanz, gelenk);

    const w = new THREE.SphereGeometry(0.0072, 20, 14);
    w.scale(1, 0.66, 0.30);
    w.rotateY(v * 0.74);
    w.translate(v * 0.0236, 0.0348, 0.0250);
    teil("kueken-wange-" + seite, w, M.wange);

    const f = new THREE.SphereGeometry(0.0088, 18, 12);
    f.scale(0.86, 0.34, 1.30);
    f.translate(v * 0.0128, 0.0032, 0.0128);
    teil("kueken-fuss-" + seite, f, M.fuss);
  });

  const schnabel = new THREE.SphereGeometry(0.0092, 26, 18);
  schnabel.scale(1, 0.56, 1.30);
  schnabel.rotateX(0.10);
  schnabel.translate(0, 0.0362, 0.0318);
  teil("kueken-schnabel", schnabel, M.schnabel);

  const bueschel = new THREE.SphereGeometry(0.0062, 18, 14);
  bueschel.scale(0.55, 1.75, 0.55);
  bueschel.rotateZ(-0.34);
  bueschel.translate(0.0028, 0.0855, -0.0016);
  teil("kueken-bueschel", bueschel, M.gefieder);

  const bueschel2 = new THREE.SphereGeometry(0.0052, 18, 14);
  bueschel2.scale(0.55, 1.45, 0.55);
  bueschel2.rotateZ(0.30);
  bueschel2.translate(-0.0044, 0.0822, -0.0022);
  teil("kueken-bueschel-2", bueschel2, M.gefieder);

  return kueken;
}
