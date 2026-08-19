### Behoben
- Die vom Social-Bot hochgeladenen Bilder werden jetzt auch ausgeliefert.
  Sie lagen im `public/`-Verzeichnis des Frontends, das Next.js aber nur beim
  Build einliest — der Upload lief, die Adresse gab trotzdem 404, und ein
  Beitrag wäre erst beim Veröffentlichen gescheitert.
