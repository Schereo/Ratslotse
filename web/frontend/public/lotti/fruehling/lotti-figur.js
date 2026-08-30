/* <lotti-figur> — Lotti auf einer Webseite, ohne three.js und ohne Abhängigkeiten.
 *
 *   <script type="module" src="/lotti/lotti-figur.js"></script>
 *   <lotti-figur quelle="/lotti/" groesse="112"></lotti-figur>
 *
 *   const lotti = document.querySelector('lotti-figur');
 *   lotti.spiele('freut-sich');
 *   lotti.spiele(['nickt', 'freut-sich']);   // nacheinander
 *   lotti.zeige('rechts');                   // zeigt und HÄLT
 *   lotti.zeigeAuf(element);                 // Richtung aus der Lage
 *   lotti.ruhe();                            // Geste auflösen
 *   lotti.spiele(['nickt', 700, 'freut-sich']);   // Zahl = Pause in ms
 *   lotti.spiele('winkt', { wiederholen: 2 });
 *
 * `regie="ruhig|lebhaft|aus"` steuert, was sie VON SELBST tut. Gewählt
 * wird nur aus Regungen, deren Blatt schon geladen ist — die Regie holt
 * nichts nach.
 *   lotti.laden('gesten');                   // Blatt vorab holen
 *
 * Gespielt wird ein Spritesheet aus `studio/sprites.mjs` — Bilder und eine
 * JSON-Datei. Kein WebGL, kein Canvas: Das Element ist ein `div` mit
 * `background-position`, und der Browser schiebt dafür nur eine bereits
 * dekodierte Textur. Das läuft auch auf einem alten Telefon.
 *
 * DREI BLÄTTER, EINZELN GEHOLT. Ein Blatt mit allem wäre bequem und
 * falsch: Eine Seite, die nur ein ruhendes Maskottchen zeigt, lädt sonst
 * auch das Winken, das Suchen und vier Zeigerichtungen mit. Der Kern
 * (ruhen, blinzeln, nicken) ist ein Fünftel des Ganzen; alles andere holt
 * der Abspieler erst, wenn es verlangt wird — oder vorab per `laden()`.
 *
 * DREI DINGE, DIE EIN MASKOTTCHEN AUF EINER INFORMATIONSSEITE BRAUCHT und
 * die deshalb eingebaut sind, nicht optional:
 *
 *   1. `prefers-reduced-motion` wird respektiert, auch fürs Blinzeln. Wer
 *      Bewegung abgeschaltet hat, bekommt das aussagekräftigste Standbild
 *      der Regung. Die Einstellung wird bei jedem Bild neu geprüft.
 *   2. Außerhalb des Sichtfelds und im Hintergrund-Tab läuft nichts.
 *   3. `aria-hidden`, solange kein `beschriftung` gesetzt ist. Für eine
 *      Vorlesesoftware ist die Figur Dekoration.
 */

const VORGABE_QUELLE = './';

/* Die Blätter werden EINMAL JE ADRESSE geholt, nicht einmal je Element.
 * Eine Seite hat schnell fünf Figuren — ein leerer Zustand, ein Avatar,
 * ein Hinweis —, und jede würde sonst ihr eigenes Bild dekodieren. Der
 * Browser hätte die Datei zwar im Zwischenspeicher, das Dekodieren aber
 * fällt fünfmal an. */
const BLAETTER = new Map();       // url → { url, bereit, versprechen }

class LottiFigur extends HTMLElement {
  static get observedAttributes() {
    return ['groesse', 'regung', 'beschriftung', 'spiegel', 'ohne-leben', 'regie'];
  }

  constructor() {
    super();
    this._wurzel = this.attachShadow({ mode: 'open' });
    /* DREI SCHICHTEN, und jede hat einen Grund.
       `rahmen` spiegelt (das kann nicht die Bühne selbst, weil dort schon
       die Grundregung sitzt und beide `transform` bräuchten). `blende`
       liegt hinter der Bühne und hält beim Wechsel das LETZTE Bild der
       vorigen Regung fest — ohne sie springt eine Figur von der
       Winkhaltung in die Ruhehaltung, und dieser eine Sprung ist das
       Einzige, was man an einer sonst weichen Folge sieht. */
    this._rahmen = document.createElement('div');
    this._rahmen.className = 'rahmen';
    this._blende = document.createElement('div');
    this._blende.className = 'schicht blende';
    this._buehne = document.createElement('div');
    this._buehne.className = 'schicht buehne';
    this._rahmen.append(this._blende, this._buehne);
    const stil = document.createElement('style');
    stil.textContent = `
      :host { display: inline-block; line-height: 0; }
      :host([spiegel]) .rahmen { transform: scaleX(-1); }
      .rahmen { position: relative; width: 100%; aspect-ratio: 1 / 1; }
      .schicht {
        position: absolute; inset: 0;
        background-repeat: no-repeat;
      }
      .blende { opacity: 0; }
      .blende.faellt { opacity: 0; transition: opacity 140ms linear; }

      /* DIE GRUNDREGUNG — Atmen und Wiegen über dem RUHEBILD.
         Sie könnte auch gebacken sein; das kostete aber Bilder in der
         Gruppe, die auf JEDER Seite geladen wird (drei Sekunden bei 12/s
         sind 36 Kacheln). Als zwei CSS-Kurven kostet sie null Bytes und
         läuft zudem flüssiger als 12 Bilder je Sekunde.
         Krumme Perioden, damit sich die beiden nicht zu einer einzigen,
         mechanischen Bewegung addieren. */
      .buehne.lebt { animation: atmen 4.7s ease-in-out infinite,
                                wiegen 6.3s ease-in-out infinite; }
      @keyframes atmen {
        0%, 100% { transform: scale(1)     translateY(0); }
        50%      { transform: scale(1.009) translateY(-0.4%); }
      }
      @keyframes wiegen {
        0%, 100% { rotate: -0.5deg; }
        50%      { rotate:  0.5deg; }
      }
      @media (prefers-reduced-motion: reduce) {
        .buehne.lebt { animation: none; }
        .blende.faellt { transition: none; }
      }`;
    this._wurzel.append(stil, this._rahmen);

    this._verzeichnis = null;
    this._basis = VORGABE_QUELLE;
    this._gruppeImBild = null;
    this._bild = 0;
    this._regung = null;
    this._imBild = 0;
    this._seit = 0;
    this._haelt = false;
    this._richtung = 1;
    this._folge = [];               // noch abzuspielende Regungen
    this._dann = null;
    this._sichtbar = true;
    this._laeuft = false;
    this._naechstesBlinzeln = 0;
    this._pause = null;

    /* Bewegungsarmut kann sich WÄHREND der Sitzung ändern (Systemschalter,
       Fokusmodus). Deshalb nicht einmal abfragen, sondern zuhören — und
       der Takt prüft es bei jedem Bild neu. */
    this._bewegungsfrage = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    this._ruhig = this._bewegungsfrage?.matches ?? false;
    this._bewegungsfrage?.addEventListener?.('change', (e) => {
      this._ruhig = e.matches;
      if (this._ruhig) this.ruhe();
      this._lebenAnwenden();
      this._takten();
    });
  }

  async connectedCallback() {
    const beschriftung = this.getAttribute('beschriftung');
    this.setAttribute('role', beschriftung ? 'img' : 'presentation');
    if (beschriftung) this.setAttribute('aria-label', beschriftung);
    else this.setAttribute('aria-hidden', 'true');
    this._groesseAnwenden();

    const quelle = this.getAttribute('quelle') ?? VORGABE_QUELLE;
    this._basis = quelle.endsWith('/') ? quelle : quelle + '/';
    try {
      this._verzeichnis = await (await fetch(this._basis + 'lotti.json')).json();
    } catch {
      // Kein Blatt, keine Figur — aber auch kein Fehler auf der Seite.
      return;
    }

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([e]) => {
        this._sichtbar = e.isIntersecting;
        this._takten();
      }, { threshold: 0.05 }).observe(this);
    }
    document.addEventListener('visibilitychange', () => this._takten());

    await this.laden(this._gruppeVon('ruht'));
    this._zeigeStand('ruht', 0);
    this._lebenAnwenden();
    const start = this.getAttribute('regung');
    if (start) this.spiele(start);
    else this._takten();
  }

  attributeChangedCallback(name) {
    if (name === 'groesse') this._groesseAnwenden();
    if (name === 'regung' && this._verzeichnis) this.spiele(this.getAttribute('regung'));
    if (name === 'ohne-leben') this._lebenAnwenden();
  }

  /* ── Blätter ──────────────────────────────────────────────────────── */

  _gruppeVon(regung) {
    return this._verzeichnis?.regungen?.[regung]?.gruppe ?? 'kern';
  }

  /**
   * Ein Blatt holen. Mehrfach aufrufbar; es wird höchstens einmal geladen.
   *
   * Vorgeladen wird über ein `Image`, nicht über den Hintergrund: So ist
   * das Bild dekodiert, BEVOR es gezeigt wird. Setzt man es direkt als
   * `background-image`, blitzt beim ersten Wechsel eine leere Fläche auf.
   */
  _blatt(gruppe) {
    const eintrag = this._verzeichnis?.gruppen?.[gruppe];
    return eintrag ? BLAETTER.get(this._basis + eintrag.blatt) : null;
  }

  laden(gruppe) {
    const eintrag = this._verzeichnis?.gruppen?.[gruppe];
    if (!eintrag) return Promise.resolve(false);
    const url = this._basis + eintrag.blatt;
    let stand = BLAETTER.get(url);
    if (!stand) {
      stand = { url, bereit: false };
      stand.versprechen = new Promise((fertig) => {
        const bild = new Image();
        bild.onload = () => { stand.bereit = true; fertig(true); };
        bild.onerror = () => fertig(false);
        bild.src = url;
      });
      BLAETTER.set(url, stand);
    }
    return stand.versprechen;
  }

  /* ── Darstellung ──────────────────────────────────────────────────── */

  _groesseAnwenden() {
    const g = Number(this.getAttribute('groesse') || 0);
    if (g > 0) this.style.width = g + 'px';
    if (this._regung) this._zeigeStand(this._regung.name, this._imBild);
  }

  /**
   * Ein Bild einer Regung zeigen.
   *
   * Die Prozentrechnung ist die Falle jedes Spritesheets:
   * `background-position` in Prozent misst NICHT die Kachel, sondern
   * verteilt den Überstand — bei n Spalten liegt das i-te Bild bei
   * `i / (n − 1) × 100 %`. Mit `i / n × 100 %` sieht man überall den
   * halben Nachbarn.
   */
  _zeigeStand(regungName, nummer) {
    const eintrag = this._verzeichnis?.regungen?.[regungName];
    if (!eintrag) return;
    const gruppe = this._verzeichnis.gruppen[eintrag.gruppe];
    if (!gruppe) return;
    if (this._gruppeImBild !== eintrag.gruppe) {
      const stand = this._blatt(eintrag.gruppe);
      if (!stand?.bereit) return;                 // noch nicht da: altes Bild bleibt
      this._buehne.style.backgroundImage = `url("${stand.url}")`;
      const [spalten, zeilen] = gruppe.raster;
      this._buehne.style.backgroundSize = `${spalten * 100}% ${zeilen * 100}%`;
      this._gruppeImBild = eintrag.gruppe;
    }
    const [spalten, zeilen] = gruppe.raster;
    const i = eintrag.von + Math.max(0, Math.min(eintrag.bilder - 1, nummer));
    this._bild = i;
    const x = i % spalten;
    const y = Math.floor(i / spalten);
    this._buehne.style.backgroundPosition =
      `${spalten > 1 ? (x / (spalten - 1)) * 100 : 0}% `
      + `${zeilen > 1 ? (y / (zeilen - 1)) * 100 : 0}%`;
  }

  /**
   * Die Grundregung läuft nur im RUHEBILD.
   *
   * Während einer gebackenen Regung wäre sie eine zweite Bewegung über
   * einer ersten — zwei Takte übereinander lesen sich als Zittern, nicht
   * als Leben. Genau dort, wo ein einzelnes Standbild steht, fehlt sie
   * dagegen am meisten.
   */
  _lebenAnwenden() {
    const an = !this._regung && !this._ruhig && !this.hasAttribute('ohne-leben');
    this._buehne.classList.toggle('lebt', an);
  }

  /**
   * Weich überblenden: das aktuelle Bild einfrieren und ausblenden.
   *
   * Kein zweites Blatt, kein zweiter Ladevorgang — die Blende bekommt
   * exakt die Hintergrundangaben, die die Bühne gerade hat. Sie zeigt
   * damit dasselbe Bild, nur eine Schicht tiefer, und verschwindet in
   * 140 ms darunter.
   */
  _ueberblenden() {
    if (this._ruhig || !this._gruppeImBild) return;
    const b = this._buehne.style;
    if (!b.backgroundImage) return;
    const s = this._blende.style;
    s.backgroundImage = b.backgroundImage;
    s.backgroundSize = b.backgroundSize;
    s.backgroundPosition = b.backgroundPosition;
    this._blende.classList.remove('faellt');
    s.opacity = '1';
    // Ein Bild abwarten, sonst fasst der Browser Setzen und Übergang
    // zusammen und es blendet gar nicht.
    requestAnimationFrame(() => {
      this._blende.classList.add('faellt');
      s.opacity = '0';
    });
  }

  /* ── Steuerung ────────────────────────────────────────────────────── */

  /**
   * Eine Regung abspielen — oder eine Folge davon.
   *
   *   spiele('nickt')
   *   spiele(['nickt', 'freut-sich'])
   *   spiele('zeigt-rechts', { halten: true })
   *   spiele('winkt', { dann: () => … })
   *
   * Fehlt das Blatt der Gruppe noch, wird es geholt und danach gespielt;
   * bis dahin bleibt das aktuelle Bild stehen. Das ist die richtige
   * Reihenfolge: lieber ein Sekundenbruchteil Ruhe als ein leeres Feld.
   */
  spiele(was, { halten = false, dann = null, wiederholen = 1 } = {}) {
    /* EINE ZAHL IN DER FOLGE IST EINE PAUSE in Millisekunden:
         spiele(['nickt', 700, 'freut-sich'])
       Ohne sie hängt jede Geste an der vorigen, und eine Folge liest sich
       als eine einzige lange Bewegung. Zwischen zwei Sätzen steht ein
       Punkt; zwischen zwei Gesten steht eine Pause. */
    const folge = Array.isArray(was) ? [...was] : [was];
    if (wiederholen > 1 && !Array.isArray(was)) {
      for (let i = 1; i < wiederholen; i++) folge.push(was);
    }
    const name = folge.shift();
    if (!this._verzeichnis?.regungen?.[name]) return false;
    this._folge = folge;
    this._dann = dann;
    return this._starte(name, { halten });
  }

  /**
   * Eine einzelne Regung starten — ohne an Folge oder Abschluss zu rühren.
   *
   * Die Trennung ist nötig, weil `spiele()` beides SETZT: Rief das
   * Weiterschalten einer Folge `spiele()` auf, löschte es damit den
   * Abschluss-Rückruf der Folge, und `dann` kam nie (gefunden beim
   * Nachfahren des Zustandsautomaten, 28.08.26).
   */
  _starte(name, { halten = false } = {}) {
    const eintrag = this._verzeichnis?.regungen?.[name];
    if (!eintrag) return false;

    const starten = () => {
      this._ueberblenden();
      this._regung = { name, ...eintrag };
      this._imBild = 0;
      this._richtung = 1;
      this._haelt = halten && eintrag.halt != null;
      this._seit = performance.now();
      this.dispatchEvent(new CustomEvent('regung', { detail: { name } }));
      if (this._ruhig) {
        /* Ohne Bewegung bleibt das AUSSAGEKRÄFTIGSTE Bild stehen: der
           Haltepunkt, wo es einen gibt, sonst die Mitte. Das erste Bild
           wäre für „freut sich" oder „winkt" die Ruhehaltung — die Geste
           käme gar nicht an. */
        this._zeigeStand(name, eintrag.halt ?? Math.floor((eintrag.bilder - 1) / 2));
        this._regung = null;
        this._lebenAnwenden();
        this.dispatchEvent(new CustomEvent('fertig', { detail: { name } }));
        this._folgeWeiter();
        return;
      }
      this._zeigeStand(name, 0);
      this._lebenAnwenden();
      this._takten();
    };

    const stand = this._blatt(eintrag.gruppe);
    if (stand?.bereit) starten();
    else this.laden(eintrag.gruppe).then((ok) => { if (ok) starten(); });
    return true;
  }

  /** Zeigen und die Geste halten, bis `ruhe()` kommt. */
  zeige(richtung = 'rechts') {
    return this.spiele('zeigt-' + richtung, { halten: true });
  }

  /**
   * Auf ein Element zeigen — die Richtung ergibt sich aus der Lage.
   * Damit muss eine Seite nicht selbst rechnen, wohin Lotti greifen soll.
   */
  zeigeAuf(element) {
    if (!element?.getBoundingClientRect) return false;
    const a = this.getBoundingClientRect();
    const b = element.getBoundingClientRect();
    const dx = (b.left + b.width / 2) - (a.left + a.width / 2);
    const dy = (b.top + b.height / 2) - (a.top + a.height / 2);
    const richtung = Math.abs(dx) > Math.abs(dy)
      ? (dx > 0 ? 'rechts' : 'links')
      : (dy > 0 ? 'runter' : 'hoch');
    return this.zeige(richtung);
  }

  /**
   * Auf ein Element REAGIEREN: beim Überfahren etwas spielen, beim
   * Verlassen zur Ruhe. Der häufigste Fall in einer Oberfläche, und ohne
   * diese Zeilen schreibt ihn jede Seite neu.
   */
  reagiereAuf(element, { hinein = null, hinaus = 'ruhe' } = {}) {
    if (!element?.addEventListener) return () => {};
    const rein = () => {
      if (hinein) this.spiele(hinein);
      else this.zeigeAuf(element);
    };
    const raus = () => { if (hinaus === 'ruhe') this.ruhe(); else this.spiele(hinaus); };
    element.addEventListener('pointerenter', rein);
    element.addEventListener('pointerleave', raus);
    element.addEventListener('focusin', rein);
    element.addEventListener('focusout', raus);
    return () => {
      element.removeEventListener('pointerenter', rein);
      element.removeEventListener('pointerleave', raus);
      element.removeEventListener('focusin', rein);
      element.removeEventListener('focusout', raus);
    };
  }

  /** Eine gehaltene Geste auflösen und zur Ruhe zurück. */
  ruhe() {
    this._folge = [];
    clearTimeout(this._pause);
    if (this._regung && this._haelt) {
      this._haelt = false;
      // Zeige-Regungen sind nur bis zum Haltepunkt gebacken; ihr Rückweg
      // ist derselbe Weg rückwärts.
      this._richtung = this._regung.rueckwaerts ? -1 : 1;
      this._seit = performance.now();
      this._takten();
      return;
    }
    this._ueberblenden();
    this._regung = null;
    this._richtung = 1;
    this._zeigeStand('ruht', 0);
    this._lebenAnwenden();
  }

  /* ── Takt ─────────────────────────────────────────────────────────── */

  get _sollLaufen() {
    return Boolean(this._sichtbar && !document.hidden && !this._ruhig
      && this._verzeichnis);
  }

  _takten() {
    if (!this._sollLaufen) { this._laeuft = false; return; }
    if (this._laeuft) return;
    this._laeuft = true;
    const schritt = (jetzt) => {
      /* Die Bedingung wird bei JEDEM Bild geprüft, nicht nur beim Start.
         Sonst liefe die Schleife weiter, wenn sich unterwegs etwas ändert
         — genau das ist beim Nachstellen von `prefers-reduced-motion`
         aufgefallen: abgeschaltet, und sie blinzelte weiter. */
      if (!this._laeuft || !this._sollLaufen) { this._laeuft = false; return; }
      this._schritt(jetzt);
      requestAnimationFrame(schritt);
    };
    requestAnimationFrame(schritt);
  }

  _schritt(jetzt) {
    if (!this._regung) {
      if (this._ruhig) return;
      if (!this._naechstesBlinzeln) {
        this._naechstesBlinzeln = jetzt + this._regiePause();
      }
      if (jetzt >= this._naechstesBlinzeln) {
        this._naechstesBlinzeln = 0;
        this.spiele(this._regieWaehlt());
      }
      return;
    }

    const takt = 1000 / (this._regung.takt || this._verzeichnis.takt || 12);
    /* Verbrauchte Takte abziehen statt „Zeit seit Start" zu rechnen: Nur
       so lässt sich mitten in der Regung die Richtung umkehren, ohne dass
       der Zähler springt. */
    const schritte = Math.floor((jetzt - this._seit) / takt);
    if (schritte < 1) return;
    this._seit += schritte * takt;

    const letztes = this._haelt ? this._regung.halt : this._regung.bilder - 1;
    const bild = this._imBild + schritte * this._richtung;

    if (this._richtung > 0 && bild >= letztes) {
      this._imBild = letztes;
      this._zeigeStand(this._regung.name, letztes);
      if (this._haelt) return;                       // eingefroren bis ruhe()
      if (this._regung.wiederholt) { this._imBild = 0; return; }
      if (this._regung.rueckwaerts) { this._richtung = -1; return; }
      this._beenden(jetzt);
      return;
    }
    if (this._richtung < 0 && bild <= 0) { this._beenden(jetzt); return; }
    this._imBild = bild;
    this._zeigeStand(this._regung.name, bild);
  }

  _beenden(jetzt) {
    const name = this._regung?.name;
    this._ueberblenden();
    this._regung = null;
    this._richtung = 1;
    this._imBild = 0;
    this._naechstesBlinzeln = jetzt + 1800 + Math.random() * 3000;
    this._zeigeStand('ruht', 0);
    this._lebenAnwenden();
    this.dispatchEvent(new CustomEvent('fertig', { detail: { name } }));
    this._folgeWeiter();
  }

  /* ══════════════════════════════════════════════════════════════════
     REGIE — was die Figur von selbst tut.

     Bisher war das ein Lidschlag alle paar Sekunden, und der war schon
     der halbe Unterschied zwischen Puppe und Figur. Er ist aber auch das
     Einzige: Eine Lotti, die zehn Minuten neben einem Text steht,
     blinzelt zehn Minuten lang und tut sonst nichts.

     DIE REGIE HOLT NICHTS NACH. Das ist die Regel, an der alles hängt:
     Gewählt wird nur aus Regungen, deren Blatt SCHON DA ist. Eine Seite,
     die ein ruhendes Maskottchen wollte, soll nicht dadurch 590 kB
     nachladen, dass die Figur Lust auf eine Geste bekommt. Wer mehr will,
     lädt mehr (`laden('gesten')`) — und bekommt die Vielfalt automatisch
     dazu, weil der Vorrat mitwächst.

     Die GEWICHTE sind der Rest: Blinzeln ist immer richtig, Nicken
     gelegentlich, alles andere selten. Ein Maskottchen, das ständig winkt,
     ist kein lebendiges, sondern ein aufdringliches. */

  /** Was die Regie überhaupt spielen darf, nach Häufigkeit gewichtet. */
  static REGIE = {
    blinzelt: 10, nickt: 2, wartet: 2, 'schaut-umher': 2,
    denkt: 1, staunt: 1, 'freut-sich': 1, seufzt: 1, lacht: 1, winkt: 1,
  };

  /** Wie lange die Regie zwischen zwei Einfällen wartet. */
  _regiePause() {
    const art = this.getAttribute('regie') ?? 'ruhig';
    if (art === 'lebhaft') return 900 + Math.random() * 1800;
    return 1200 + Math.random() * 2600;
  }

  _regieWaehlt() {
    if (this.getAttribute('regie') === 'aus') return 'blinzelt';
    /* Nur Geladenes. `_blatt(gruppe).bereit` ist genau die Frage „liegt
       das Blatt schon im Speicher" — dieselbe, die `_zeigeStand` stellt,
       bevor es ein Bild zeigt. */
    const vorrat = [];
    for (const [name, gewicht] of Object.entries(LottiFigur.REGIE)) {
      const eintrag = this._verzeichnis?.regungen?.[name];
      if (!eintrag || !this._blatt(eintrag.gruppe)?.bereit) continue;
      // Nichts, was hängen bleibt: Eine gehaltene Geste löste sich nie auf.
      if (eintrag.halt != null) continue;
      for (let i = 0; i < gewicht; i++) vorrat.push(name);
    }
    if (!vorrat.length) return 'blinzelt';
    return vorrat[Math.floor(Math.random() * vorrat.length)];
  }

  /** Die nächste Regung einer Folge — oder der Abschluss. */
  _folgeWeiter() {
    while (this._folge.length) {
      const naechst = this._folge.shift();
      if (typeof naechst === 'number') {
        // Pause: Der Takt läuft weiter, die Regie hält so lange still.
        this._naechstesBlinzeln = performance.now() + naechst;
        clearTimeout(this._pause);
        this._pause = setTimeout(() => {
          this._naechstesBlinzeln = 0;
          this._folgeWeiter();
        }, naechst);
        return;
      }
      this._starte(naechst);
      return;
    }
    const dann = this._dann;
    this._dann = null;
    dann?.();
  }
}

customElements.define('lotti-figur', LottiFigur);
export { LottiFigur };
