/* Jahreszeit in der Hero-Szene: Wetter im Bild, Kleidung an der Figur.
 *
 * Die Outfit-Sprache kommt aus dem gezeichneten Maskottchen (mascot.tsx) —
 * dieselben Kleidungsstücke, DIESELBEN Farbwerte: Der 2D-Fallback (schmale
 * Fenster, reduzierte Bewegung) und die 3D-Szene erzählen sonst zwei
 * verschiedene Jahreszeiten. Frühling: Blume an der Mütze. Sommer:
 * Sonnenbrille. Herbst: warmer Schal. Winter: kühler Schal, Ohrenschützer,
 * und die Küken bekommen Mini-Schals.
 *
 * Feiertage überschreiben in der Zeichnung das ganze Outfit (Hexenhut,
 * Weihnachtsmütze, …). In 3D ist jedes davon eigene Geometrie; übernommen
 * ist nur der rote Weihnachtsschal — an den übrigen Feiertagen trägt die
 * 3D-Lotti ihr Jahreszeiten-Outfit weiter. Bewusst so schmal gehalten:
 * lieber wenige Teile, die sitzen, als ein Kostümfundus, der klemmt.
 *
 * Das Wetter richtet sich IMMER nach der Jahreszeit, auch an Feiertagen —
 * Schnee hört an Heiligabend nicht auf. Es bleibt Dekoration im Sinn der
 * Designsprache: klein, langsam, nie Vordergrund.
 */
import type * as THREE_NS from "three";
import type { MascotTheme, Season } from "@/lib/mascot-theme";

type TH = typeof THREE_NS;

/* Farbwerte 1:1 aus mascot.tsx (`C`) — wer dort umfärbt, zieht hier nach. */
const FARBE = {
  scarfWarm: "#E4572E",
  scarfCool: "#3D8FD1",
  santa: "#D7263D",
  leaf: "#E08A2B",
  leafDark: "#C56A16",
  leafGold: "#D9A13B",
  flower: "#F6A5C0",
  flowerCore: "#F2B441",
  brille: "#122A40",
  sonne: "#FFD989",
  /* Nicht das 2D-#DCEAF6: Das liegt dort auf dem WEISSEN Vogel. Frei
     fallende Flocken stehen hier vor dem hellen Seitengrund und brauchen
     einen Ton kühler, sonst sind sie unsichtbar. */
  schnee: "#A9C9E6",
};

/* ── Licht: die Tageszeit einer Jahreszeit ────────────────────────────────
 * Dezente Verschiebungen der bestehenden vier Lichter — kein neues Licht,
 * keine anderen Intensitäten. Winterlicht ist kühl und flach, Sommerlicht
 * warm, Herbstlicht golden von hinten (die Kante glüht), Frühling ist der
 * neutrale Ausgangszustand der Szene.
 */
export function lichtStimmung(season: Season): {
  hemiHimmel: number; hemiBoden: number; key: number; fill: number; rim: number;
} {
  switch (season) {
    case "winter":
      return { hemiHimmel: 0xf4f8ff, hemiBoden: 0x93a9c2, key: 0xecf3ff, fill: 0xcfe0f5, rim: 0xd8e8ff };
    case "summer":
      return { hemiHimmel: 0xfff8ec, hemiBoden: 0x8ea6bc, key: 0xfff0d2, fill: 0xd6e9fa, rim: 0xffcf9e };
    case "autumn":
      return { hemiHimmel: 0xfff4e4, hemiBoden: 0xa89a8a, key: 0xffedd8, fill: 0xd6e9fa, rim: 0xffc48f };
    default:
      return { hemiHimmel: 0xffffff, hemiBoden: 0x8ea6bc, key: 0xffffff, fill: 0xd6e9fa, rim: 0xffd9b8 };
  }
}

function stoff(THREE: TH, farbe: string, rau = 0.85): THREE_NS.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({ color: farbe, roughness: rau, metalness: 0.02 });
}

function part(
  THREE: TH, ziel: THREE_NS.Object3D, name: string,
  geo: THREE_NS.BufferGeometry, material: THREE_NS.Material,
): THREE_NS.Mesh {
  const m = new THREE.Mesh(geo, material);
  m.name = name;
  m.castShadow = true;
  m.receiveShadow = true;
  ziel.add(m);
  return m;
}

/* ── Kleidung an Lotti ────────────────────────────────────────────────────
 * Schal und Sonnenbrille hängen dort, wo sie in echt säßen: der Schal am
 * Rumpf (er neigt sich NICHT mit dem Kopf), Brille und Ohrenschützer im
 * Kopf-Gelenk, die Blume an der Mütze — jede Kopfbewegung nimmt sie mit.
 */
export function lottiAnziehen(THREE: TH, lotti: THREE_NS.Group, theme: MascotTheme): void {
  const kopf = lotti.getObjectByName("kopf");
  const muetze = lotti.getObjectByName("muetze");
  if (!kopf || !muetze) return;
  /* Kopf-Teile rechnen in Kopf-Koordinaten: Lotti-Höhe minus Drehpunkt. */
  const KD = (lotti.userData.kopfDrehpunkt as number) ?? 0.095;

  const schalFarbe =
    theme.holiday === "christmas" ? FARBE.santa
    : theme.season === "autumn" ? FARBE.scarfWarm
    : theme.season === "winter" ? FARBE.scarfCool
    : null;

  if (schalFarbe) {
    const wolle = stoff(THREE, schalFarbe);
    /* Um den Hals: Der Rumpf hat bei y ≈ 0,118 den Radius 0,086 (Tiefe
       1,02). Die Mittellinie des Rings liegt AUSSEN darauf (0,092), sodass
       der Wulst sichtbar aufliegt und nur seine Innenkante im Gefieder
       steckt — bei 0,0855 war er zur Hälfte im Körper versunken (Tims
       Befund 24.08.). */
    const ring = new THREE.TorusGeometry(0.092, 0.013, 14, 48);
    ring.rotateX(Math.PI / 2);
    ring.scale(1, 1, 1.02);
    ring.translate(0, 0.118, 0);
    part(THREE, lotti, "schal", ring, wolle);
    /* Das hängende Ende liegt AUF der Brust: Die Körperfront steht bei
       y ≈ 0,082 auf z ≈ 0,088 — die Kapsel sitzt mit ihrer Innenfläche
       knapp darin und ragt nach vorn heraus. Bei z = 0,079 hing sie
       komplett IM Rumpf und war unsichtbar (Tims Befund 24.08.). */
    const ende = new THREE.CapsuleGeometry(0.0115, 0.040, 6, 14);
    ende.scale(1, 1, 0.55);
    ende.rotateZ(0.16);
    ende.rotateX(-0.10);
    ende.translate(0.036, 0.080, 0.0915);
    part(THREE, lotti, "schal-ende", ende, wolle);
  }

  if (theme.season === "winter") {
    /* Ohrenschützer: zwei Polster an den Kopfseiten, der Bügel läuft HINTER
       dem Kopf herum — über den Scheitel ginge er mitten durch die
       Kapitänsmütze, und die ist nicht verhandelbar. Hinterm Kopf getragen
       ist auch in echt eine übliche Bauart. */
    const polsterM = stoff(THREE, FARBE.scarfCool, 0.95);
    (
      [["links", 1], ["rechts", -1]] as [string, number][]
    ).forEach(([page, v]) => {
      const p = new THREE.SphereGeometry(0.0145, 22, 16);
      p.scale(0.62, 1, 1);
      p.translate(v * 0.0625, 0.152 - KD, 0.008);
      part(THREE, kopf, "ohrpolster-" + page, p, polsterM);
    });
    const buegel = new THREE.TorusGeometry(0.0630, 0.0032, 10, 40, Math.PI);
    buegel.rotateZ(Math.PI);          // offene Seite nach oben …
    buegel.rotateX(-1.22);            // … und der Bogen kippt in den Nacken
    buegel.translate(0, 0.150 - KD, 0.006);
    part(THREE, kopf, "ohrbuegel", buegel, polsterM);
  }

  if (theme.season === "summer" && !theme.holiday) {
    /* Sonnenbrille: zwei Gläser knapp VOR den Augen, Steg dazwischen,
       Bügel zu den Schläfen. Die Augen animieren dahinter weiter — man
       sieht es nicht, und genau das ist bei einer Sonnenbrille der Sinn. */
    const glasM = new THREE.MeshStandardMaterial({
      color: FARBE.brille, roughness: 0.22, metalness: 0.10,
    });
    ([1, -1] as const).forEach((v) => {
      const glas = new THREE.CylinderGeometry(0.0198, 0.0198, 0.0042, 28);
      glas.rotateX(Math.PI / 2);
      glas.translate(v * 0.0332, 0.1478 - KD, 0.0790);
      part(THREE, kopf, "brille-glas-" + (v === 1 ? "links" : "rechts"), glas, glasM);
      /* Der Bügel VERBINDET Glasrand und Schläfe — als Strecke zwischen den
         beiden Punkten gebaut, nicht als frei gedrehter Stab: Das alte
         `rotateY(±0.18)` kippte die Vorderkante nach AUSSEN, und der Stab
         hing sichtbar neben dem Glas in der Luft (Tims Befund 30.08.). */
      const vorn = new THREE.Vector3(v * 0.0508, 0.1482 - KD, 0.0782);
      const hinten = new THREE.Vector3(v * 0.0618, 0.1500 - KD, 0.0090);
      const buegel = new THREE.CylinderGeometry(0.0024, 0.0024, vorn.distanceTo(hinten), 10);
      buegel.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 1, 0), hinten.clone().sub(vorn).normalize()));
      const mitte = vorn.clone().add(hinten).multiplyScalar(0.5);
      buegel.translate(mitte.x, mitte.y, mitte.z);
      part(THREE, kopf, "brille-buegel-" + (v === 1 ? "links" : "rechts"), buegel, glasM);
    });
    const steg = new THREE.CylinderGeometry(0.0026, 0.0026, 0.0270, 10);
    steg.rotateZ(Math.PI / 2);
    steg.translate(0, 0.1508 - KD, 0.0788);
    part(THREE, kopf, "brille-steg", steg, glasM);
  }

  if (theme.season === "spring" && !theme.holiday) {
    /* Die Blume sitzt an der Mützenkrone, rechts vorn — als Kind der
       Mütze, damit sie deren Nachpendeln mitmacht. Die Mützen-Kinder
       tragen ihre Lage in ABSOLUTEN Lotti-Koordinaten (Gruppe + Kopf-
       Gelenk heben sich auf), also gilt das auch hier. */
    const bluete = new THREE.Group();
    bluete.name = "muetzen-blume";
    const blattM = stoff(THREE, FARBE.flower, 0.8);
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2;
      const b = new THREE.SphereGeometry(0.0062, 14, 10);
      b.scale(1, 1, 0.45);
      b.translate(Math.cos(a) * 0.0082, Math.sin(a) * 0.0082, 0);
      part(THREE, bluete, "bluetenblatt-" + i, b, blattM);
    }
    const kern = new THREE.SphereGeometry(0.0046, 14, 10);
    kern.scale(1, 1, 0.6);
    kern.translate(0, 0, 0.0018);
    part(THREE, bluete, "bluetenkern", kern, stoff(THREE, FARBE.flowerCore, 0.6));
    bluete.position.set(0.0560, 0.2065, 0.0400);
    /* Blüte schaut vom Krone-Mittelpunkt radial nach außen. */
    bluete.lookAt(0.14, 0.225, 0.10);
    muetze.add(bluete);
  }
}

/** Winter-Küken: ein Mini-Schal, sonst nichts — wie in der Zeichnung. */
export function kuekenAnziehen(THREE: TH, kueken: THREE_NS.Group, theme: MascotTheme): void {
  if (theme.season !== "winter") return;
  /* Küken-Körper (Kugel r 0,0357, gestaucht) hat bei y ≈ 0,0335 den
     Radius ~0,0344 — Mittellinie außen darauf, wie bei Lotti. */
  const ring = new THREE.TorusGeometry(0.0375, 0.0072, 12, 36);
  ring.rotateX(Math.PI / 2);
  ring.translate(0, 0.0335, 0);
  part(THREE, kueken, "kueken-schal", ring,
       stoff(THREE, theme.holiday === "christmas" ? FARBE.santa : FARBE.scarfCool));
}

/* ── Wetter ───────────────────────────────────────────────────────────────
 * Gebaut wie die treibenden Ratsdokumente der Szene: wenige, kleine Teile
 * mit eigenem `userData`-Zustand, die im selben Takt animiert werden.
 * Schnee fällt, Blüten taumeln, Blätter treiben im Wind, die Sommersonne
 * steht still und dreht nur ihre Strahlen. `MeshBasicMaterial`, weil
 * Wetter nicht beleuchtet aussehen soll wie ein Objekt der Szene — es ist
 * Hintergrund, `depthWrite: false` hält es hinter den Figuren weich.
 */
export interface Wetter {
  gruppe: THREE_NS.Group;
  animieren(uhr: number, dt: number, ruhe: boolean): void;
}

interface Flocke {
  x: number; z: number; y0: number; tempo: number; phase: number;
  wind: number; dreh: number;
}

function streuen(count: number, tempo: [number, number], wind: number): Flocke[] {
  return Array.from({ length: count }, () => ({
    x: -0.36 + Math.random() * 0.80,
    z: -0.32 + Math.random() * 0.26,
    y0: -0.05 + Math.random() * 0.55,
    tempo: tempo[0] + Math.random() * (tempo[1] - tempo[0]),
    phase: Math.random() * Math.PI * 2,
    wind: wind * (0.6 + Math.random() * 0.8),
    dreh: (Math.random() - 0.5) * 1.6,
  }));
}

export function wetterBauen(THREE: TH, season: Season): Wetter {
  const gruppe = new THREE.Group();
  gruppe.name = "wetter";

  if (season === "summer") {
    /* Die Sonne: Scheibe, weicher Hof, acht Strahlen — oben rechts hinter
       den Figuren, wo auf der Karte sonst Himmel wäre. Sie fällt nicht,
       sie dreht nur unmerklich ihre Strahlen.

       Höhe 0,32, nicht höher: Die Kamera rahmt die FIGUREN ein (rahmen()
       in lotti-szene), alles über ~0,30 Welthöhe liegt außerhalb des
       Bildes — bei 0,415 war nur der untere Sonnenrand zu sehen. */
    const sonne = new THREE.Group();
    sonne.position.set(0.250, 0.292, -0.34);
    const scheibeM = new THREE.MeshBasicMaterial({
      color: FARBE.sonne, transparent: true, opacity: 0.9, depthWrite: false,
    });
    const hofM = new THREE.MeshBasicMaterial({
      color: FARBE.sonne, transparent: true, opacity: 0.22, depthWrite: false,
    });
    sonne.add(new THREE.Mesh(new THREE.CircleGeometry(0.062, 40), scheibeM));
    sonne.add(new THREE.Mesh(new THREE.CircleGeometry(0.092, 40), hofM));
    const strahlen = new THREE.Group();
    for (let i = 0; i < 8; i++) {
      const s = new THREE.Mesh(new THREE.PlaneGeometry(0.042, 0.0075), hofM);
      const a = (i / 8) * Math.PI * 2;
      s.position.set(Math.cos(a) * 0.117, Math.sin(a) * 0.117, 0);
      s.rotation.z = a;
      strahlen.add(s);
    }
    sonne.add(strahlen);
    gruppe.add(sonne);
    return {
      gruppe,
      animieren(_uhr, dt, ruhe) {
        if (!ruhe) strahlen.rotation.z += dt * 0.045;
      },
    };
  }

  let flocken: Flocke[];
  let bauen: (f: Flocke) => THREE_NS.Mesh;
  if (season === "winter") {
    flocken = streuen(40, [0.045, 0.085], 0.004);
    const m = new THREE.MeshBasicMaterial({
      color: FARBE.schnee, transparent: true, opacity: 0.9, depthWrite: false,
    });
    const g = new THREE.SphereGeometry(1, 10, 8);
    bauen = () => {
      const mesh = new THREE.Mesh(g, m);
      mesh.scale.setScalar(0.0030 + Math.random() * 0.0026);
      return mesh;
    };
  } else if (season === "autumn") {
    /* Ein Blatt: spitze Ellipse aus zwei Bögen, flach — die Form aus der
       gezeichneten FallingLeaf, nur eben im Raum taumelnd. */
    flocken = streuen(18, [0.030, 0.058], 0.030);
    const blattForm = new THREE.Shape();
    blattForm.moveTo(0, -0.0085);
    blattForm.quadraticCurveTo(0.0068, 0, 0, 0.0085);
    blattForm.quadraticCurveTo(-0.0068, 0, 0, -0.0085);
    const g = new THREE.ShapeGeometry(blattForm, 10);
    const toene = [FARBE.leaf, FARBE.leafDark, FARBE.leafGold].map((f) =>
      new THREE.MeshBasicMaterial({
        color: f, transparent: true, opacity: 0.85,
        side: THREE.DoubleSide, depthWrite: false,
      }));
    let i = 0;
    bauen = () => new THREE.Mesh(g, toene[i++ % toene.length]);
  } else {
    /* Frühling: Blütenblätter, rosa, leichter als alles andere. */
    flocken = streuen(20, [0.020, 0.042], 0.012);
    const g = new THREE.PlaneGeometry(0.0088, 0.0062);
    const m = new THREE.MeshBasicMaterial({
      color: FARBE.flower, transparent: true, opacity: 0.85,
      side: THREE.DoubleSide, depthWrite: false,
    });
    bauen = () => new THREE.Mesh(g, m);
  }

  const teile = flocken.map((f) => {
    const mesh = bauen(f);
    mesh.userData = f;
    gruppe.add(mesh);
    return mesh;
  });

  return {
    gruppe,
    animieren(uhr, dt, ruhe) {
      for (const mesh of teile) {
        const f = mesh.userData as Flocke;
        if (!ruhe) {
          f.y0 -= f.tempo * dt;
          f.x += f.wind * dt;
        }
        /* Unten raus → oben neu herein; im Herbstwind auch seitlich. */
        if (f.y0 < -0.06 || f.x > 0.48) {
          f.y0 = 0.52 + Math.random() * 0.06;
          f.x = -0.36 + Math.random() * 0.80;
        }
        mesh.position.set(f.x + Math.sin(uhr * 0.8 + f.phase) * 0.016, f.y0, f.z);
        mesh.rotation.set(
          Math.sin(uhr * 0.6 + f.phase) * 0.9,
          uhr * f.dreh,
          Math.cos(uhr * 0.5 + f.phase) * 0.7,
        );
      }
    },
  };
}
