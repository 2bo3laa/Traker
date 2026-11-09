#!/usr/bin/env python3
"""Merge i18n.txt (ar|en|fr|es|tr|de|id|ur, one string per line) into index.html's translation packs.
Fails if a line is malformed, placeholders differ, or a language column contains another language."""
import re, json, pathlib, sys

root = pathlib.Path(__file__).resolve().parent
LANGS = ["en", "fr", "es", "tr", "de", "id", "ur"]
AR = re.compile(r"[\u0600-\u06FF]")
LAT = re.compile(r"[A-Za-z]{2,}")
START, END = "/*I18N:START*/", "/*I18N:END*/"

rows, fail, seen = [], [], set()
for n, line in enumerate((root / "i18n.txt").read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip():
        continue
    c = line.split("|")
    if len(c) != 8:
        fail.append(f"line {n}: {len(c)} columns"); continue
    ar = c[0].replace("\ufe0f", "")
    if ar in seen:
        fail.append(f"line {n}: duplicate key {ar}"); continue
    seen.add(ar)
    ph = sorted(re.findall(r"\{\d+\}", ar))
    for lang, v in zip(LANGS, c[1:]):
        if not v.strip(): fail.append(f"line {n} {lang}: empty")
        if sorted(re.findall(r"\{\d+\}", v)) != ph: fail.append(f"line {n} {lang}: placeholders differ")
        if AR.search(v) and lang != "ur": fail.append(f"line {n} {lang}: Arabic script in {v!r}")
        if lang == "ur" and LAT.search(v): fail.append(f"line {n} ur: Latin text in {v!r}")
    rows.append((ar, c[1:]))
if fail:
    print("\n".join(fail)); sys.exit(1)

block = START + "\n" + "\n".join(
    "Object.assign(PACK.%s,%s);" % (lang, json.dumps({k: v[i] for k, v in rows}, ensure_ascii=False))
    for i, lang in enumerate(LANGS)) + "\n" + END
p = root / "index.html"
html = p.read_text(encoding="utf-8")
if START in html:
    html = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda m: block, html, flags=re.S)
else:
    m = re.search(r"PACK\.ur=\{.*?\n\};\n", html, re.S)
    html = html[:m.end()] + block + "\n" + html[m.end():]
p.write_text(html, encoding="utf-8")
print(f"merged {len(rows)} strings into {len(LANGS)} languages")
