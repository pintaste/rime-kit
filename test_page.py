import re
import subprocess
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parent
html = (root / "index.html").read_text()
match = re.search(r'<script type="module">([\s\S]*?)</script>', html)
if match is None:
    raise SystemExit("module script not found")

with tempfile.NamedTemporaryFile("w", suffix=".mjs") as file:
    file.write(match.group(1))
    file.flush()
    result = subprocess.run(
        ["node", "--check", file.name],
        capture_output=True,
        text=True,
    )

if result.returncode != 0:
    raise SystemExit(result.stderr.strip())

print("page ok")
