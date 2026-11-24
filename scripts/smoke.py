"""Nicht den Arbeitsbaum installieren: einen echten frischen Lieferumfang prüfen."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from package_release import package


def main():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        archive = package(base / "download.zip")
        download = base / "download"
        with zipfile.ZipFile(archive) as z:
            z.extractall(download)
        source = download / "bewerbungs-assistent"
        check = subprocess.run([sys.executable, str(source / "scripts" / "check_public.py")], cwd=source,
                               capture_output=True, text=True, timeout=30)
        assert check.returncode == 0, check.stdout + check.stderr
        manifest = json.loads((source / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
        for item in manifest["files"]:
            assert hashlib.sha256((source / item["file"]).read_bytes()).hexdigest() == item["sha256"]
        target = base / "Mein persönlicher Ordner"
        def call(*args, root=target):
            result = subprocess.run([sys.executable, str(root / "start.py"), *args], cwd=root,
                                    capture_output=True, text=True, encoding="utf-8", timeout=30)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            return result.stdout
        call("einrichten", "--ziel", str(target), "--name", "Alex Beispiel", "--rolle", "Projektmanager", "--assistent", "codex", root=source)
        assert (target / "AGENTS.md").is_file()
        assert not (target / ".git").exists()
        call("fakt", "--id", "projekt-1", "--text", "Ein internes Projekt koordiniert.", "--quelle", "Fiktives Testprofil", "--stichwort", "Projektkoordination")
        description = target / "anzeige.txt"
        description.write_text("Fiktive Anzeige: Projektkoordination und Anforderungen abstimmen.", encoding="utf-8")
        output = call("stelle", "--firma", "Beispiel GmbH", "--rolle", "Projektmanager", "--url", "https://jobs.example.com/123", "--textdatei", str(description))
        jid = output.split()[0]
        call("bewerten", jid, "--score", "80", "--grund", "Test mit belegtem Projekt, Gehalt offen")
        proof = target / "bestaetigung.txt"
        proof.write_text("Fiktiver Einreichungsbeleg zur eindeutigen Stelle 123.", encoding="utf-8")
        call("ereignis", jid, "--status", "beworben", "--datum", "2026-01-15", "--beleg", str(proof), "--grund", "Fiktiver Beleg selbst zugeordnet", "--message-id", "receipt@example.com")
        call("lebenslauf")
        call("bericht")
        call("chat-export")
        call("pruefen")
        state = json.loads((target / "bewerbungen.json").read_text(encoding="utf-8"))
        assert state[0]["status"] == "beworben" and state[0]["score_manual"] == 80
        with zipfile.ZipFile(target / "exports" / "chat-projekt.zip") as z:
            assert len(z.namelist()) == 4
            assert not any("belege" in name or name.endswith(".eml") for name in z.namelist())
        assert (target / "exports" / "BERICHT.md").is_file()
    print("CLEAN INSTALL SMOKE OK")


if __name__ == "__main__":
    main()
