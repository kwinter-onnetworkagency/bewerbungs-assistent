import hashlib
import json
from pathlib import Path
import sys
import stat
import zipfile

from public_files import ROOT, checked_files


def package(output):
    output = Path(output).expanduser().absolute()
    if output.suffix != ".zip" or output.resolve().is_relative_to(ROOT):
        raise ValueError("Release-ZIP außerhalb des Quellordners und mit Endung .zip anlegen.")
    files = checked_files()
    prefix = "bewerbungs-assistent"
    entries = []
    with output.open("xb") as f:
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
            for source in files:
                relative = source.relative_to(ROOT).as_posix()
                data = source.read_bytes()
                info = zipfile.ZipInfo(prefix + "/" + relative)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | (source.stat().st_mode & 0o777)) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
                entries.append({"file": relative, "sha256": hashlib.sha256(data).hexdigest()})
            z.writestr(prefix + "/RELEASE-MANIFEST.json", json.dumps({"files": entries}, indent=2))
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python scripts/package_release.py PFAD-AUSSERHALB-DES-REPOS.zip")
    print(package(sys.argv[1]))
