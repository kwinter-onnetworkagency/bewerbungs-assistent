"""Downloadpakete des geprüften Quellstands mit ausschließlich fiktiven Beispielen bauen."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

from package_release import package, require_clean_source
from public_files import ROOT

sys.path.insert(0, str(ROOT))
from bewerbung import __version__
from bewerbung.core import Workspace, write
from bewerbung.export import report
from bewerbung.setup import initialize


def release_assets(folder):
    folder = Path(folder).resolve()
    if folder.is_relative_to(ROOT):
        raise ValueError("Release außerhalb des Quellordners bauen.")
    require_clean_source()
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    package(folder / f"Bewerbungs-Assistent-v{__version__}.zip")
    shutil.copyfile(ROOT / "examples/dashboard-demo.json", folder / "dashboard-demo.json")
    template = (ROOT / "resources/Dashboard.html").read_text(encoding="utf-8")
    (folder / "Dashboard.html").write_text(template, encoding="utf-8")
    jobs = json.loads((folder / "dashboard-demo.json").read_bytes())["jobs"]
    from bewerbung.export import embed_jobs
    (folder / "Dashboard-Demo.html").write_text(embed_jobs(template, jobs), encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Workspace(initialize(Path(tmp) / "demo", "Fiktive Person", [], "", "codex", False))
        for job in jobs:
            job.update(identity=job["url"], draft=None, qa=None, description="Fiktive Anzeige zur Erkundung der Übersichten.")
        write(workspace.path("bewerbungen.json"), jobs)
        report(workspace)
        with zipfile.ZipFile(folder / "Beispiel-Uebersichten.zip", "x", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(workspace.path("exports").rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(workspace.path("exports")))
    hashes = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in sorted(folder.iterdir())]
    (folder / "SHA256SUMS.txt").write_bytes(("\n".join(hashes) + "\n").encode())
    return folder


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python scripts/release_assets.py NEUER_RELEASEORDNER")
    print(release_assets(sys.argv[1]))
