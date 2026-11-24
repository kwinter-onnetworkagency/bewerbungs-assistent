"""Einfache A4-DOCX-Dateien; keine Fremdpakete oder Makros."""
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile


def docx(path, paragraphs):
    for line in paragraphs:
        if any(ord(c) < 32 and c not in "\n\r\t" for c in line):
            raise ValueError("Unzulässiges Steuerzeichen im Dokumenttext.")
    body = "".join('<w:p><w:r><w:t xml:space="preserve">' + escape(line) + '</w:t></w:r></w:p>' for line in paragraphs)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>')
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
               '<Default Extension="xml" ContentType="application/xml"/>'
               '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError("Dokument existiert bereits. Neue Version oder anderen Dateinamen verwenden.")
    with path.open("xb") as f:
        with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
            for name, value in [("[Content_Types].xml", content), ("_rels/.rels", rels), ("word/document.xml", document)]:
                z.writestr(name, value)
    path.chmod(0o600)


def render(workspace, jid=None):
    profile = workspace.profile()
    if jid:
        item = workspace.job(workspace.jobs(), jid)
        if not item.get("draft"):
            raise ValueError("Noch kein Anschreibenentwurf gespeichert.")
        stem = jid + "-anschreiben"
        paragraphs = [profile["name"], profile.get("preferences", {}).get("contact") or "", item["company"], item["role"], ""] + item["draft"]["text"].splitlines()
    else:
        if not profile["facts"]:
            raise ValueError("Lebenslauf benötigt belegte Profilfakten.")
        stem = "lebenslauf"
        paragraphs = [profile["name"], profile.get("location", ""), profile.get("preferences", {}).get("contact") or "", ""]
        labels = {"experience": "Berufserfahrung", "achievement": "Projekte und Ergebnisse", "education": "Ausbildung",
                  "certificate": "Zertifikate und Weiterbildung", "skill": "Kenntnisse", "language": "Sprachen"}
        groups = {}
        for fact in profile["facts"]:
            groups.setdefault(fact.get("kind"), []).append(fact["text"])
        for kind, entries in groups.items():
            paragraphs += [labels.get(kind, "Profil und belegte Erfahrung"), *entries, ""]
    out = workspace.path("dokumente", stem + ".docx")
    version = 2
    while out.exists():
        out = workspace.path("dokumente", f"{stem}-v{version}.docx")
        version += 1
    docx(out, paragraphs)
    return out
