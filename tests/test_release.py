import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from public_files import ROOT, checked_files
from package_release import package, require_clean_source


class PublicReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        for source in checked_files():
            dest = self.root / source.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)

    def test_unknown_personal_file_blocks_publication(self):
        self.assertGreater(len(checked_files(self.root)), 20)
        (self.root / "profil.json").write_text('{"name":"Nicht veröffentlichen"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Nicht freigegebene Datei"):
            checked_files(self.root)

    def test_realistic_token_shape_blocks_publication(self):
        (self.root / "README.md").write_text("ghp_" + "x" * 36, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Zugangsdaten"):
            checked_files(self.root)

    def test_nonexample_email_blocks_publication(self):
        (self.root / "README.md").write_text("candidate" + "@" + "private.invalid", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "E-Mail"):
            checked_files(self.root)

    def test_release_manifest_detects_changed_file(self):
        archive = package(Path(self.tmp.name) / "release.zip")
        dest = Path(self.tmp.name) / "unpacked"
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
            self.assertEqual(len(z.namelist()), len(checked_files()) + 1)
        root = dest / "bewerbungs-assistent"
        self.assertGreater(len(checked_files(root)), 20)
        (root / "README.md").write_text("Versehentlich verändert", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Manifest"):
            checked_files(root)

    def test_nested_allowlist_path_is_rejected(self):
        p = self.root / "private" / "docs"
        p.mkdir(parents=True)
        (p / "notizen.md").write_text("Nicht freigegebene interne Notiz")
        with self.assertRaisesRegex(ValueError, "Nicht freigegebene Datei"):
            checked_files(self.root)

    def test_tracked_ignored_folder_is_rejected(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        folder = self.root / ".codex"
        folder.mkdir()
        (folder / "cache.json").write_text("{}")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", ".codex/cache.json"], check=True)
        with self.assertRaisesRegex(ValueError, "getrackte"):
            checked_files(self.root)

    def test_staged_private_content_is_checked_even_if_worktree_cleaned(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        terms = Path(self.tmp.name) / "terms.txt"
        terms.write_text("  unique-private-staged  ", encoding="utf-8-sig")
        doc = self.root / "README.md"
        doc.write_text("unique-private-staged.")
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        doc.write_text("Bereinigter Arbeitsbaum")
        with patch.dict("os.environ", {"BEWERBUNG_PRIVATE_TERMS": str(terms)}):
            with self.assertRaisesRegex(ValueError, "Git-Index"):
                checked_files(self.root)

    def test_release_cli_requires_committed_source(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        with self.assertRaisesRegex(ValueError, "sauberem"):
            require_clean_source(self.root)

    def test_release_cli_rejects_untracked_deliverables(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-qm", "test source"], check=True)
        with self.assertRaisesRegex(ValueError, "Nicht committete Datei"):
            require_clean_source(self.root)

    def test_private_terms_and_contact_patterns_are_rejected(self):
        for value in ["C:" + chr(92) + "Users" + chr(92) + "person" + chr(92),
                      "+" + "49" + " 30 " + "12345678", "DE" + "00" + "0" * 18]:
            (self.root / "README.md").write_text(value)
            with self.assertRaises(ValueError):
                checked_files(self.root)
        terms = Path(self.tmp.name) / "private-terms.txt"
        terms.write_text("unique-private-name")
        (self.root / "README.md").write_text("unique-private-name")
        with patch.dict("os.environ", {"BEWERBUNG_PRIVATE_TERMS": str(terms)}):
            with self.assertRaisesRegex(ValueError, "Privater Prüfbegriff"):
                checked_files(self.root)


if __name__ == "__main__":
    unittest.main()
