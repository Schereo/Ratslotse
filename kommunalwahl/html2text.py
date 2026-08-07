"""HTML -> Text. Aufruf: python3 html2text.py <in.html> <out.txt> [--append]"""
import sys, re
from html.parser import HTMLParser


class T(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "svg", "noscript"):
            self.skip += 1
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "br", "section", "tr", "td"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "svg", "noscript") and self.skip > 0:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.parts.append(d)


t = T()
t.feed(open(sys.argv[1], encoding="utf-8", errors="ignore").read())
txt = re.sub(r"[ \t\xa0]+", " ", "".join(t.parts))
txt = re.sub(r"\n[ \t]+", "\n", txt)
txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
mode = "a" if "--append" in sys.argv else "w"
with open(sys.argv[2], mode, encoding="utf-8") as f:
    if mode == "a":
        f.write(f"\n\n===== [Quelle: {sys.argv[1]}] =====\n")
    f.write(txt)
print(f"-> {sys.argv[2]} ({len(txt)} Zeichen, Modus {mode})")
