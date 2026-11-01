#!/usr/bin/env python3
"""Fast checks that run before the build: JS syntax, duplicate top-level names, Python patch files compile."""
import re, subprocess, sys, pathlib, py_compile, tempfile

root = pathlib.Path(__file__).resolve().parent
html = (root / "index.html").read_text(encoding="utf-8")
blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
fail = []

# 1) every script block must parse
for i, b in enumerate(blocks):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(b)
    r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
    if r.returncode:
        fail.append(f"script block {i}: syntax error\n{r.stderr[:500]}")

# 2) the same top-level name declared twice (even in different blocks) kills the whole page
seen = {}
for i, b in enumerate(blocks):
    for m in re.finditer(r"^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)", b, re.M):
        seen.setdefault(m.group(1), []).append(i)
for name, where in seen.items():
    if len(where) > 1:
        fail.append(f"'{name}' is declared {len(where)} times (blocks {where})")

# 3) the Python patch scripts must compile
for f in sorted(root.glob("*.py")):
    try:
        py_compile.compile(str(f), doraise=True)
    except Exception as e:
        fail.append(f"{f.name}: {e}")

if fail:
    print("STATIC CHECK FAILED")
    for x in fail:
        print(" -", x)
    sys.exit(1)
print(f"static checks OK ({len(blocks)} script blocks, {len(seen)} top-level names)")
