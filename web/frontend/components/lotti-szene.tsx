"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { baueKueken, baueLotti } from "@/lib/lotti/modell";
import { kuekenAnziehen, lichtStimmung, lottiAnziehen, wetterBauen } from "@/lib/lotti/jahreszeit";
import { getMascotTheme } from "@/lib/mascot-theme";

/* Lotti live: die Lotsenmöwe und drei Küken, gerechnet statt gezeichnet.
 * Aus dem Design-Projekt („Lotti Hero Familie").
 *
 * Diese Datei wird NUR über einen dynamischen Import geladen (s. lotti-hero.tsx).
 * Sie zieht three.js nach — rund 600 KB — und das darf die Startseite nicht
 * bezahlen, bevor Überschrift und Knöpfe stehen.
 *
 * Der Grundsatz aus dem Entwurf: viel Bewegung, aber jede davon klein. Der Körper
 * dreht sich höchstens 25 Grad, das Hüpfen misst zwei Zentimeter, das Atmen ist
 * eher zu spüren als zu sehen. Bei einer App über Ratsbeschlüsse darf das
 * Maskottchen wärmen, aber nicht die Bühne übernehmen.
 */

/** Lebendig wird es erst, wenn die Teile unterschiedlich schnell reagieren.
 *  Dreht alles gleich schnell mit, wirkt es wie ein starres Bild, das man kippt. */
const FOLGERATE = {
  blick: 13,      // 01 Augen zuerst — das Schnellste am Körper, auch in echt
  blickY: 11,
  gier: 4.4,      // 02 Körper folgt gedämpft, nur halb so weit
  nick: 3.8,
  neige: 3.4,
  muetze: 6.2,    // 03 Mütze und Schwanz laufen nach und pendeln aus
  muetzeNeige: 5.4,
  schwanz: 3.0,
};

const KUEKEN = [
  { x: 0.078, z: 0.052, s: 1.00, ton: "orange", dreh: -0.26, takt: 0.00, zyklus: 2.55, folge: 3.4 },
  { x: 0.132, z: -0.018, s: 0.86, ton: "gold", dreh: -0.06, takt: 1.05, zyklus: 3.10, folge: 2.7 },
  { x: 0.174, z: 0.062, s: 0.78, ton: "orange", dreh: -0.48, takt: 1.85, zyklus: 2.20, folge: 4.6 },
] as const;

/** Ratsdokumente, die durchs Bild treiben — als echte Seiten gezeichnet
 *  (Kopfbalken, Textzeilen, Beschluss-Vermerk, Unterschriftslinien). Ohne
 *  Zeichnung wären es bloß graue Rechtecke. */
function seiteZeichnen(variante: number): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 300; c.height = 424;
  const g = c.getContext("2d")!;
  g.fillStyle = "#FAFCFE"; g.fillRect(0, 0, 300, 424);
  g.strokeStyle = "rgba(20,58,92,0.16)"; g.lineWidth = 3;
  g.strokeRect(1.5, 1.5, 297, 421);

  const M = 34;
  let y = 44;
  const zeile = (breite: number, hoehe: number, farbe: string) => {
    g.fillStyle = farbe;
    g.fillRect(M, y, (300 - M * 2) * breite, hoehe);
    y += hoehe + 9;
  };

  g.fillStyle = "rgba(20,58,92,0.30)";
  g.fillRect(M, y, 78, 7); y += 20;
  zeile(0.86, 13, "rgba(20,58,92,0.62)");
  zeile(0.54, 13, "rgba(20,58,92,0.62)");
  y += 7;
  g.strokeStyle = "rgba(20,58,92,0.18)"; g.lineWidth = 2;
  g.beginPath(); g.moveTo(M, y); g.lineTo(300 - M, y); g.stroke();
  y += 16;

  const absatz = (n: number) => {
    for (let i = 0; i < n; i++) zeile(0.62 + Math.random() * 0.38, 6, "rgba(20,58,92,0.20)");
    y += 8;
  };
  if (variante === 0) { absatz(5); absatz(4); absatz(3); }
  else if (variante === 1) {
    absatz(4);
    g.fillStyle = "rgba(20,58,92,0.10)";
    for (let r = 0; r < 4; r++) {
      g.fillRect(M, y, 300 - M * 2, 12);
      g.fillStyle = "rgba(20,58,92,0.24)";
      g.fillRect(300 - M - 52, y + 3, 46, 6);
      g.fillStyle = "rgba(20,58,92,0.10)";
      y += 17;
    }
    y += 8; absatz(3);
  } else { absatz(3); absatz(6); }

  g.fillStyle = "rgba(246,102,35,0.55)";
  g.fillRect(M, y, 52, 8);
  g.fillStyle = "rgba(20,58,92,0.34)";
  g.fillRect(M + 62, y, 74, 8);
  y += 30;
  g.strokeStyle = "rgba(20,58,92,0.22)"; g.lineWidth = 2;
  [0, 1].forEach((i) => {
    const x = M + i * 118;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + 96, y); g.stroke();
  });

  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

export default function LottiSzene({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const huelleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cv = canvasRef.current;
    const huelle = huelleRef.current;
    if (!cv || !huelle) return;

    const mag = window.matchMedia("(prefers-reduced-motion: reduce)");
    let ruhe = mag.matches;

    const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearAlpha(0);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.06;

    /* Jahreszeit einmal beim Aufbau bestimmen — dieselbe Logik wie beim
       gezeichneten Fallback (mascot-theme). Kein Hydration-Thema: Diese
       Datei läuft nur im Browser (`ssr: false` in lotti-hero), das Datum
       ist also immer das der Besucherin. Läuft die Seite über Mitternacht
       in eine neue Jahreszeit, bleibt die alte stehen — der nächste Besuch
       richtet es, ein Umbau der ganzen Szene zur Laufzeit wäre teurer als
       dieser Grenzfall wert ist. */
    const jahreszeit = getMascotTheme();

    /* Die vier Lichter behalten Ort und Stärke; nur die FARBEN wandern mit
       der Jahreszeit (kühles Winterlicht, goldener Herbst — s. jahreszeit.ts). */
    const licht = lichtStimmung(jahreszeit.season);
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(licht.hemiHimmel, licht.hemiBoden, 1.9));
    const key = new THREE.DirectionalLight(licht.key, 2.5);
    key.position.set(0.40, 0.70, 0.55);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 0.05; key.shadow.camera.far = 3;
    key.shadow.camera.left = -0.42; key.shadow.camera.right = 0.42;
    key.shadow.camera.top = 0.40; key.shadow.camera.bottom = -0.40;
    key.shadow.bias = -0.0009;
    scene.add(key);
    const fill = new THREE.DirectionalLight(licht.fill, 1.0);
    fill.position.set(-0.60, 0.28, 0.42);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(licht.rim, 1.5);
    rim.position.set(-0.30, 0.42, -0.62);
    scene.add(rim);

    const boden = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 2.4), new THREE.ShadowMaterial({ opacity: 0.26 }));
    boden.rotation.x = -Math.PI / 2;
    boden.receiveShadow = true;
    scene.add(boden);

    /* ── Figuren ── */
    const lotti = baueLotti(THREE);
    lotti.position.set(-0.030, 0, 0);
    lottiAnziehen(THREE, lotti, jahreszeit);
    scene.add(lotti);

    /* Seit dem Studio-Stand vom 28.08. sind die Gelenke echte Knochen
       (THREE.Bone) mit unveränderten Namen; Rumpf und Flügel sind gehäutet
       (SkinnedMesh) und folgen den Knochen von selbst. */
    const schulterR = lotti.getObjectByName("schulter-rechts")!;
    const schulterL = lotti.getObjectByName("schulter-links")!;
    const ellbogenR = lotti.getObjectByName("ellbogen-rechts")!;
    const handgelenkR = lotti.getObjectByName("handgelenk-rechts")!;
    /* Gewinkt wird, wie das Studio es für DIESE Figur eingemessen hat
       (studio/regungen.mjs, Regung „winkt", Tims Abnahme 29.08.): Der Oberarm
       geht auf 112° und BLEIBT dort — 150° läge quer überm Gesicht, und was
       nicht verdeckt wäre, verschwände hinter der Mützenkrempe. Der Ellbogen
       stellt den Unterarm ein (46°), und DAS WINKEN KOMMT AUS DEM HANDGELENK:
       Vorher pendelte der ganze Unterarm, das sah aus, als rühre sie in einem
       Topf. Werte der linken Seite; für die rechte kippen z und y das
       Vorzeichen (Spiegelung wie in GRENZEN des Modells). */
    const GRAD = Math.PI / 180;
    const WINK = { schulter: 112 * GRAD, y: 6 * GRAD, ellbogen: 46 * GRAD, hand: 35 * GRAD };


    const muetze = lotti.getObjectByName("muetze")!;
    const schwanz = lotti.getObjectByName("schwanz-gelenk")!;
    /* Fürs Atmen: Der Rumpf ist jetzt ein SkinnedMesh, und dessen eigene
       `scale` ist wirkungslos — die Haut hört nur auf Knochen. Skaliert
       wird deshalb der Bauch-Knochen; alles darüber (Brust, Hals, Kopf)
       weitet sich die 1,4 % mit, genau wie vorher das ganze Ei. */
    const bauch = lotti.getObjectByName("bauch")!;
    const augen = ["links", "rechts"].map((s) => lotti.getObjectByName("auge-gelenk-" + s)!);
    const MUETZE0 = { x: muetze.rotation.x, z: muetze.rotation.z };
    const AUGE0 = augen.map((a) => a.position.clone());

    type Kueken = typeof KUEKEN[number] & {
      obj: THREE.Group; gier: number; basis: number;
      fl: (THREE.Object3D | null)[]; augen: THREE.Object3D[]; augen0: THREE.Vector3[]; flatterBis: number;
    };
    const kuekenGruppe = new THREE.Group();
    const kueken: Kueken[] = KUEKEN.map((k) => {
      const g = baueKueken(THREE, { ton: k.ton });
      kuekenAnziehen(THREE, g, jahreszeit);
      g.position.set(k.x, 0, k.z);
      g.scale.setScalar(k.s);
      const augenG = ["links", "rechts"].map((s) => g.getObjectByName("kueken-auge-gelenk-" + s)!);
      kuekenGruppe.add(g);
      return {
        ...k, obj: g, gier: k.dreh, basis: k.dreh,
        fl: ["links", "rechts"].map((s) => g.getObjectByName("kueken-schulter-" + s) ?? null),
        augen: augenG, augen0: augenG.map((a) => a.position.clone()), flatterBis: -1,
      };
    });
    scene.add(kuekenGruppe);

    /* ── Treibende Ratsdokumente ── */
    const seitenTexturen = [0, 1, 2].map(seiteZeichnen);
    const papiere = new THREE.Group();
    for (let i = 0; i < 7; i++) {
      const b = 0.034 + Math.random() * 0.016;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(b, b * 1.414), new THREE.MeshStandardMaterial({
        map: seitenTexturen[i % 3], color: "#ffffff", roughness: 0.92, metalness: 0,
        transparent: true, opacity: 0.5, side: THREE.DoubleSide, depthWrite: false,
      }));
      m.userData = {
        x: -0.20 + Math.random() * 0.52,
        z: -0.26 + Math.random() * 0.28,
        y0: -0.06 + Math.random() * 0.34,
        tempo: 0.011 + Math.random() * 0.014,
        dreh: (Math.random() - 0.5) * 0.35,
        phase: Math.random() * Math.PI * 2,
      };
      papiere.add(m);
    }
    scene.add(papiere);

    /* ── Wetter der Jahreszeit: Schnee, Blüten, Blätter — oder die Sonne ── */
    const wetter = wetterBauen(THREE, jahreszeit.season);
    scene.add(wetter.gruppe);

    /* ── Kamera: Ausschnitt aus der größten Pose ableiten (Flügel oben), damit er
       nie abgeschnitten wird. Eingepasst wird die projizierte Silhouette, nicht
       eine Hüllkugel — die wäre bei einer breiten, flachen Gruppe viel größer als
       das, was die Kamera wirklich sieht. ── */
    const cam = new THREE.PerspectiveCamera(30, 1, 0.02, 8);
    const CAMZIEL = new THREE.Vector3();
    const ECKEN: THREE.Vector3[] = [];
    {
      const merkZ = schulterR.rotation.z;
      schulterR.rotation.z = -WINK.schulter;
      scene.updateMatrixWorld(true);
      /* `precise`, sonst misst Box3 bei SkinnedMesh die RUHELAGE statt der
         Pose — der gehobene Wink-Flügel bliebe unberücksichtigt und würde
         oben aus dem Bild ragen (Falle aus studio/skelett.js). */
      const box = new THREE.Box3().setFromObject(lotti, true)
        .union(new THREE.Box3().setFromObject(kuekenGruppe, true));
      schulterR.rotation.z = merkZ;
      box.getCenter(CAMZIEL);
      for (const x of [box.min.x, box.max.x])
        for (const y of [box.min.y, box.max.y])
          for (const z of [box.min.z, box.max.z]) ECKEN.push(new THREE.Vector3(x, y, z));
    }
    const CAMRICHTUNG = new THREE.Vector3(0.10, 0.13, 1).normalize();
    const RAND = 0.96;   // lässt Luft für Parallaxe und Atmen
    let camDist = 0.9;

    function rahmen() {
      const w = cv!.clientWidth || 480, h = cv!.clientHeight || 452;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      cam.aspect = w / h;
      let d = 0.9;
      for (let i = 0; i < 7; i++) {          // Abstand iterativ auf max|NDC| = RAND einregeln
        cam.position.copy(CAMZIEL).addScaledVector(CAMRICHTUNG, d);
        cam.lookAt(CAMZIEL);
        cam.updateProjectionMatrix();
        cam.updateMatrixWorld(true);
        let m = 0;
        for (const e of ECKEN) {
          const p = e.clone().project(cam);
          m = Math.max(m, Math.abs(p.x), Math.abs(p.y));
        }
        d *= m / RAND;
      }
      camDist = d;
    }
    rahmen();
    const groessenWaechter = new ResizeObserver(rahmen);
    groessenWaechter.observe(cv);

    /* ── Zeigerposition, normiert über die ganze Hülle ── */
    let zx = 0, zy = 0, zeigerAn = false, letzteBewegung = -99;
    const aufZeiger = (e: PointerEvent) => {
      const r = huelle!.getBoundingClientRect();
      zx = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width - 0.52) * 2.1));
      zy = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height - 0.48) * 2.1));
      zeigerAn = true;
      letzteBewegung = uhr;
    };
    const aufVerlassen = () => { zeigerAn = false; };
    huelle.addEventListener("pointermove", aufZeiger);
    huelle.addEventListener("pointerleave", aufVerlassen);

    /* ── Zustände ── */
    let uhr = 0, letzterFrame = performance.now(), sichtbar = true;
    let winkStart = 0.45, winkDauer = 2.0, winkZyklen = 3;
    let blinzelnBis = -1, naechstesBlinzeln = 2.4, doppelBlick = false;
    let hoppStart = -9;
    let start = 0;                                   // Auftritt 0 → 1
    let blickX = 0, blickY = 0, gierIst = 0, nickIst = 0, neigeIst = 0;
    let muetzeGier = 0, muetzeNeige = 0, schwanzGier = 0;
    let umschauX = 0, umschauZiel = 0, naechstesUmschauen = 6;
    let laeuft = true;

    const daempf = (ist: number, ziel: number, rate: number, dt: number) =>
      ist + (ziel - ist) * (1 - Math.exp(-rate * dt));
    const easeOutBack = (t: number) => { const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };

    function winken(dauer = 2.0) {
      winkStart = uhr; winkDauer = dauer;
      winkZyklen = Math.max(2, Math.round(dauer * 1.35));   // hält die Schwungfrequenz bei ~2,7 Hz
    }
    function huepfen() { hoppStart = uhr; }

    let handle = 0;
    function bild(now: number) {
      handle = requestAnimationFrame(bild);
      const roh = (now - letzterFrame) / 1000;
      if (roh < 1 / 37) return;                      // 12 · Deckel bei ~36 fps
      letzterFrame = now;
      if (!sichtbar || !laeuft) return;              // 10 · außer Sicht wird nicht gerechnet
      const dt = Math.min(roh, 0.06);
      uhr += dt;

      /* Auftritt */
      if (start < 1) start = Math.min(1, start + dt / 0.9);
      const e = easeOutBack(Math.min(1, start / 0.75));
      lotti.scale.setScalar(0.86 + 0.14 * e);

      /* 08 Blickziel: Zeiger — oder bei Stillstand ein eigener Blick, statt einzufrieren */
      const stillSeit = uhr - letzteBewegung;
      let zielX = zx, zielY = zy;
      if (!zeigerAn || stillSeit > 5) {
        if (uhr > naechstesUmschauen) {
          umschauZiel = (Math.random() - 0.5) * 1.5;
          naechstesUmschauen = uhr + 2.6 + Math.random() * 3.4;
        }
        umschauX = daempf(umschauX, umschauZiel, 1.5, dt);
        zielX = umschauX; zielY = -0.12;
      } else {
        umschauX = daempf(umschauX, zx, 3, dt);
        naechstesUmschauen = uhr + 3.2;
      }
      if (ruhe) { zielX = zeigerAn ? zx : 0; zielY = zeigerAn ? zy : 0; }

      blickX = daempf(blickX, zielX, FOLGERATE.blick, dt);
      blickY = daempf(blickY, zielY, FOLGERATE.blickY, dt);
      gierIst = daempf(gierIst, zielX * 0.42, FOLGERATE.gier, dt);
      nickIst = daempf(nickIst, zielY * -0.10, FOLGERATE.nick, dt);
      neigeIst = daempf(neigeIst, zielX * -0.055, FOLGERATE.neige, dt);

      /* 09 Winken: ausholen, hinführen, dort pendeln, weich senken */
      let heben = 0, schwung = 0;
      const wp = (uhr - winkStart) / winkDauer;
      if (!ruhe && wp >= 0 && wp <= 1) {
        if (wp < 0.10) {
          heben = -0.16 * Math.sin((wp / 0.10) * Math.PI);          // kurz ausholen
        } else if (wp < 0.30) {
          const u = (wp - 0.10) / 0.20;
          heben = 1 + 1.9 * Math.pow(u - 1, 3) + 0.9 * Math.pow(u - 1, 2);
        } else if (wp < 0.74) {
          heben = 1;
        } else {
          const u = (wp - 0.74) / 0.26;
          heben = (1 - u * u * (3 - 2 * u)) * (1 + Math.sin(u * Math.PI * 2) * 0.10);
        }
        if (wp > 0.27 && wp < 0.78) {
          const u = (wp - 0.27) / 0.51;
          schwung = Math.pow(Math.sin(u * Math.PI), 0.55) * Math.sin(u * Math.PI * 2 * winkZyklen);
        }
      }
      const winkAus = Math.max(0, heben);

      const atem = ruhe ? 0 : Math.sin(uhr * 2.7) * 0.5 + 0.5;
      lotti.rotation.set(nickIst - winkAus * 0.030, gierIst + winkAus * 0.055, neigeIst - winkAus * 0.050);
      lotti.position.y = (ruhe ? 0 : atem * 0.0042 + Math.sin(uhr * 0.9) * 0.0016) + winkAus * 0.0045;
      /* 05 Atmen: der Rumpf weitet sich, statt bloß zu schweben */
      bauch.scale.set(1 + atem * 0.014, 1 - atem * 0.007, 1 + atem * 0.014);

      muetzeGier = daempf(muetzeGier, gierIst, FOLGERATE.muetze, dt);
      muetzeNeige = daempf(muetzeNeige, neigeIst, FOLGERATE.muetzeNeige, dt);
      schwanzGier = daempf(schwanzGier, gierIst, FOLGERATE.schwanz, dt);
      muetze.rotation.y = (muetzeGier - gierIst) * 1.5;
      muetze.rotation.z = MUETZE0.z + (muetzeNeige - neigeIst) * 1.8;
      muetze.rotation.x = MUETZE0.x + Math.sin(uhr * 1.6) * 0.006;
      schwanz.rotation.y = (schwanzGier - gierIst) * 2.1;
      schwanz.rotation.x = ruhe ? 0 : Math.sin(uhr * 1.35) * 0.05;

      /* 06 Blinzeln — zufällig, gelegentlich zweimal kurz hintereinander */
      if (!ruhe && uhr > naechstesBlinzeln && uhr > blinzelnBis) {
        blinzelnBis = uhr + 0.13;
        if (doppelBlick) { naechstesBlinzeln = uhr + 0.30; doppelBlick = false; }
        else { naechstesBlinzeln = uhr + 2.2 + Math.random() * 4.2; doppelBlick = Math.random() < 0.28; }
      }
      const lid = uhr < blinzelnBis ? 1 - Math.abs((uhr - (blinzelnBis - 0.065)) / 0.065) : 0;
      augen.forEach((a, i) => {
        a.position.x = AUGE0[i].x + blickX * 0.0030;
        a.position.y = AUGE0[i].y + blickY * -0.0020;
        a.rotation.y = blickX * 0.52;
        a.rotation.x = blickY * 0.34;
        a.scale.y = 1 - Math.max(0, lid) * 0.92;
      });

      schulterR.rotation.z = -WINK.schulter * heben;   // heben <0 holt aus, >1 schwingt über
      schulterR.rotation.y = -WINK.y * winkAus;
      ellbogenR.rotation.z = WINK.ellbogen * winkAus;  // Unterarm einstellen …
      handgelenkR.rotation.z = -schwung * WINK.hand * winkAus; // … die Hand wippt
      schulterL.rotation.z = ruhe ? 0 : Math.sin(uhr * 1.9) * 0.045 + atem * 0.02;

      /* 07 Küken: hüpfen mit Stauchung, schauen versetzt mit, flattern gelegentlich */
      const hopExtra = uhr - hoppStart;
      kueken.forEach((k, i) => {
        k.gier = daempf(k.gier, k.basis + zielX * (0.30 + i * 0.10), k.folge, dt);
        k.obj.rotation.y = k.gier;

        let u = ruhe ? 9 : ((uhr + k.takt) % k.zyklus) / 0.46;
        if (hopExtra >= 0 && hopExtra < 0.5 + i * 0.09) u = Math.max(0, (hopExtra - i * 0.09) / 0.46);
        if (u < 1) {
          const h = Math.sin(u * Math.PI);
          k.obj.position.y = Math.pow(h, 1.35) * 0.021;
          k.obj.scale.set(k.s * (1 - h * 0.07), k.s * (1 + h * 0.12), k.s * (1 - h * 0.07));
          k.obj.rotation.z = Math.sin(u * Math.PI * 2) * 0.07;
          k.fl.forEach((f, j) => { if (f) f.rotation.z = (j ? 1 : -1) * h * 0.75; });
        } else {
          const nach = Math.max(0, 1 - (u - 1) * 7);   // kurzes Nachfedern beim Landen
          k.obj.position.y = 0;
          k.obj.scale.set(k.s * (1 + nach * 0.05), k.s * (1 - nach * 0.09), k.s * (1 + nach * 0.05));
          k.obj.rotation.z = 0;
          const flattern = uhr < k.flatterBis;
          if (!ruhe && !flattern && Math.random() < 0.0016) k.flatterBis = uhr + 0.55;
          const a = flattern ? Math.sin(uhr * 26) * 0.55 : Math.sin(uhr * 2.2 + i) * 0.05;
          k.fl.forEach((f, j) => { if (f) f.rotation.z = (j ? 1 : -1) * Math.abs(a); });
        }
        k.augen.forEach((a, j) => {
          a.position.x = k.augen0[j].x + blickX * 0.0013;
          a.position.y = k.augen0[j].y + blickY * -0.0009;
          a.scale.y = 1 - Math.max(0, lid) * (i === 1 ? 0.9 : 0);
        });
      });

      /* Treibende Dokumente + Parallaxe der Kamera */
      papiere.children.forEach((p) => {
        const d = p.userData as Record<string, number>;
        if (!ruhe) d.y0 += d.tempo * dt;
        if (d.y0 > 0.42) { d.y0 = -0.08; d.x = -0.20 + Math.random() * 0.52; }
        p.position.set(d.x + Math.sin(uhr * 0.5 + d.phase) * 0.012, d.y0, d.z);
        p.rotation.set(
          Math.sin(uhr * 0.4 + d.phase) * 0.22,
          Math.sin(uhr * d.dreh + d.phase) * 0.5,
          Math.cos(uhr * 0.33 + d.phase) * 0.18,
        );
      });
      wetter.animieren(uhr, dt, ruhe);

      const px = ruhe ? 0 : blickX, py = ruhe ? 0 : blickY;
      cam.position.set(
        CAMZIEL.x + CAMRICHTUNG.x * camDist + px * 0.022,
        CAMZIEL.y + CAMRICHTUNG.y * camDist - py * 0.018,
        CAMZIEL.z + CAMRICHTUNG.z * camDist,
      );
      cam.lookAt(CAMZIEL.x + px * 0.006, CAMZIEL.y, CAMZIEL.z);

      renderer.render(scene, cam);
    }

    /* ── 10 · Schutzschalter: außer Sicht und im Hintergrund-Tab steht sie still ── */
    const sichtWaechter = new IntersectionObserver(([e]) => { sichtbar = e.isIntersecting; }, { threshold: 0.05 });
    sichtWaechter.observe(huelle);
    const aufTabWechsel = () => { laeuft = !document.hidden; };
    document.addEventListener("visibilitychange", aufTabWechsel);

    /* ── 11 · Reduzierte Bewegung: umschaltbar zur Laufzeit, nicht nur beim Start ── */
    const aufRuhe = (ev: MediaQueryListEvent) => {
      ruhe = ev.matches;
      if (ruhe) {
        schulterR.rotation.set(0, 0, 0);
        ellbogenR.rotation.set(0, 0, 0);
        handgelenkR.rotation.set(0, 0, 0);
        kueken.forEach((k) => { k.obj.position.y = 0; k.obj.scale.setScalar(k.s); });
      }
    };
    mag.addEventListener("change", aufRuhe);

    /* ── Auslöser: Klick in die Szene, und ab und zu von selbst ── */
    const aufKlick = (ev: MouseEvent) => {
      if ((ev.target as HTMLElement).closest("button, a")) return;
      huepfen();
      if (Math.random() < 0.5) winken(1.8);
    };
    huelle.addEventListener("click", aufKlick);
    const takt = window.setInterval(() => {
      if (sichtbar && laeuft && !ruhe && uhr - winkStart > 8) winken(1.9);
    }, 9000);

    handle = requestAnimationFrame(bild);

    return () => {
      cancelAnimationFrame(handle);
      window.clearInterval(takt);
      sichtWaechter.disconnect();
      groessenWaechter.disconnect();
      document.removeEventListener("visibilitychange", aufTabWechsel);
      mag.removeEventListener("change", aufRuhe);
      huelle.removeEventListener("pointermove", aufZeiger);
      huelle.removeEventListener("pointerleave", aufVerlassen);
      huelle.removeEventListener("click", aufKlick);
      // GPU-Speicher gibt three nicht von allein zurück — bei jedem Seitenwechsel
      // bliebe sonst eine komplette Szene liegen.
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else if (mat) mat.dispose();
        // Die Skelette der gehäuteten Teile halten eine Bone-Textur auf der GPU.
        if ((o as THREE.SkinnedMesh).isSkinnedMesh) (o as THREE.SkinnedMesh).skeleton.dispose();
      });
      seitenTexturen.forEach((t) => t.dispose());
      renderer.dispose();
    };
  }, []);

  return (
    <div ref={huelleRef} className={className}>
      <canvas ref={canvasRef} aria-hidden="true" className="block h-full w-full" />
    </div>
  );
}
