"""Eine gemeinsame Allowlist für Quellprüfung, Download und Installationsprobe."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import re

ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = {"README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "ROADMAP.md", "CHANGELOG.md",
              ".gitignore", "start.py", "package.json", "Start.command", "Start.bat", "start.sh"}
PATTERNS = ["resources/apple-mail.applescript", "resources/native-termine.js", "resources/portal.cjs", "resources/Persona.html", "resources/persona.cjs", "resources/domainwege.json", "resources/Portfolio.html", "resources/Dashboard.html", "bin/start.mjs", "tests/npx.test.mjs", "tests/portal.test.cjs", "resources/skills/*/SKILL.md", "bewerbung/*.py", "resources/*.txt", "resources/*.md", "docs/*.md", "examples/*.json",
            "tests/test_*.py", "scripts/*.py", ".github/workflows/ci.yml"]
SKIP = {".git", ".venv", "__pycache__", ".unlazy", ".claude", ".codex"}


def checked_files(root=ROOT):
    files = []
    tracked = []
    root = Path(root)
    if (root / ".git").exists():
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0")
        for name in filter(None, tracked):
            rel = Path(name)
            allowed = name in ROOT_FILES or any(len(rel.parts) == len(Path(p).parts) and rel.match(p) for p in PATTERNS)
            if any(part in SKIP for part in rel.parts) or not allowed:
                raise ValueError("Nicht freigegebene getrackte Datei: " + name)
    private_terms = []
    if os.environ.get("BEWERBUNG_PRIVATE_TERMS"):
        term_file = Path(os.environ["BEWERBUNG_PRIVATE_TERMS"])
        if term_file.resolve().is_relative_to(root.resolve()):
            raise ValueError("Private Prüfliste muss außerhalb des öffentlichen Quellordners liegen.")
        private_terms = [x.strip().casefold() for x in term_file.read_text(encoding="utf-8-sig").splitlines() if len(x.strip()) >= 3]
        if not private_terms:
            raise ValueError("Private Prüfliste ist leer.")
    def scan(rel, value):
        checks = [r"gh[pousr]_[A-Za-z0-9_]{24,}", r"sk-[A-Za-z0-9_-]{24,}",
                  r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                  r"/Users/[a-zA-Z][a-zA-Z0-9_.-]*/", r"/home/[a-zA-Z][a-zA-Z0-9_.-]*/",
                  r"[A-Za-z]:\\Users\\[^\\\s]+\\", r"(?<![\w])\+[1-9]\d{0,2}[ ()/-]*\d(?:[ ()/-]*\d){7,14}(?!\d)",
                  r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b"]
        if any(re.search(pattern, value) for pattern in checks):
            raise ValueError("Mögliche Zugangsdaten oder persönlicher Rechnerpfad in: " + str(rel))
        if any(term in value.casefold() for term in private_terms):
            raise ValueError("Privater Prüfbegriff in öffentlicher Datei: " + str(rel))
        for email in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value):
            if not email.lower().endswith(("@example.com", "@example.org", "@example.net", "@users.noreply.github.com")):
                raise ValueError("Nicht fiktive E-Mail-Adresse in öffentlicher Datei: " + str(rel))

    for name in filter(None, tracked):
        staged = subprocess.run(["git", "-C", str(root), "show", ":" + name],
                                capture_output=True, check=True).stdout.decode("utf-8-sig")
        scan(name + " (Git-Index)", staged)
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
        if rel.as_posix() not in ROOT_FILES and not any(len(rel.parts) == len(Path(p).parts) and rel.match(p) for p in PATTERNS):
            raise ValueError("Nicht freigegebene Datei im Quellordner: " + str(rel))
        value = f.read_text(encoding="utf-8")
        scan(rel, value)
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
