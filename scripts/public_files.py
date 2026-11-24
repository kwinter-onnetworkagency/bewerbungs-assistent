"""Eine gemeinsame Allowlist für Quellprüfung, Download und Installationsprobe."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = {"README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "ROADMAP.md", "CHANGELOG.md",
              ".gitignore", "start.py", "Start.command", "Start.bat", "start.sh"}
PATTERNS = ["bewerbung/*.py", "resources/*.txt", "resources/*.md", "docs/*.md", "examples/*.json",
            "tests/test_*.py", "scripts/*.py", ".github/workflows/ci.yml"]
SKIP = {".git", ".venv", "__pycache__", ".unlazy", ".claude", ".codex"}


def checked_files(root=ROOT):
    files = []
    for f in sorted(Path(root).rglob("*")):
        rel = f.relative_to(root)
        if any(part in SKIP for part in rel.parts):
            continue
        if f.is_symlink():
            raise ValueError("Symlink nicht im öffentlichen Lieferumfang zulässig: " + str(rel))
        if not f.is_file():
            continue
        if rel.as_posix() == "RELEASE-MANIFEST.json":
            continue
        if str(rel) not in ROOT_FILES and not any(rel.match(pattern) for pattern in PATTERNS):
            raise ValueError("Nicht freigegebene Datei im Quellordner: " + str(rel))
        value = f.read_text(encoding="utf-8")
        checks = [r"gh[pousr]_[A-Za-z0-9_]{24,}", r"sk-[A-Za-z0-9_-]{24,}",
                  r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                  r"/Users/[a-zA-Z][a-zA-Z0-9_.-]*/", r"/home/[a-zA-Z][a-zA-Z0-9_.-]*/"]
        if any(re.search(pattern, value) for pattern in checks):
            raise ValueError("Mögliche Zugangsdaten oder persönlicher Rechnerpfad in: " + str(rel))
        for email in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value):
            if not email.lower().endswith(("@example.com", "@example.org", "@example.net", "@users.noreply.github.com")):
                raise ValueError("Nicht fiktive E-Mail-Adresse in öffentlicher Datei: " + str(rel))
        files.append(f)
    for name in ["README.md", "LICENSE", "start.py", "resources/INTERVIEW.md", "docs/INSTALLATION.md"]:
        if not (Path(root) / name).is_file():
            raise ValueError("Pflichtdatei fehlt: " + name)
    manifest = Path(root) / "RELEASE-MANIFEST.json"
    if manifest.exists():
        expected = {f.relative_to(root).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
        entries = json.loads(manifest.read_text(encoding="utf-8"))["files"]
        supplied = {x["file"]: x["sha256"] for x in entries}
        if len(entries) != len(supplied) or supplied != expected:
            raise ValueError("Release-Manifest stimmt nicht mit den Dateien überein.")
    return files
