import sys
from pypdf import PdfReader

r = PdfReader(sys.argv[1])
out = []
for i, p in enumerate(r.pages, 1):
    t = p.extract_text() or ""
    out.append(f"\n\n===== [Seite {i}] =====\n{t}")
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("".join(out))
print(f"{len(r.pages)} Seiten -> {sys.argv[2]}")
