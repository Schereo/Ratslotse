# Lotti-Spriteanimationen

Die vier Sprite-Sheets in `Assets.xcassets/LottiSprite*.imageset` stammen aus
dem Ratslotse-Social-Repository:

- Quelle: `ratslotse-social/assets/lotti/`
- Metadaten: `ratslotse-social/assets/lotti/lotti.json`
- Modell-Fingerabdruck: `2026-08-28 (1ra2kqk)`
- Kachelgröße der iOS-Fassung: 384 × 384 Pixel

Die Regungen werden mit `studio/sprites.mjs --px 384 --png` neu gerendert und
anschließend durch `ios/scripts/make_lotti_ios_sprites.swift` in ein kleines
Sheet pro Animation zerlegt. Dadurch bleibt eine groß dargestellte Lotti
scharf, ohne dass iOS für eine einzelne Regung den gesamten Atlas dekodieren
muss. Animationsbereiche, Bildraten, Schleifen und Haltebilder werden in
`LottiSpriteView.swift` aus den gemeinsamen Metadaten abgebildet.

Regeneration aus einem lokalen Checkout beider Repositories:

```sh
cd /pfad/zu/ratslotse-social
node studio/sprites.mjs --px 384 --png

cd /pfad/zu/kommunalwahl-scraper
swift ios/scripts/make_lotti_ios_sprites.swift \
  /pfad/zu/ratslotse-social/studio/build/web \
  ios/Resources/Assets.xcassets
```
