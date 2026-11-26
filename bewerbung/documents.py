"""Einspaltige A4-Unterlagen aus dem lokalen Profil und gespeicherten Entwürfen."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
import zipfile

from .core import keyword_match, text, url

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
SECTIONS = {
    'profile': ('Profil und belegte Erfahrung', 'Profile and experience'),
    'strength': ('Stärken mit Praxisbeispielen', 'Strengths in practice'),
    'experience': ('Berufserfahrung', 'Professional experience'),
    'achievement': ('Projekte und Ergebnisse', 'Projects and achievements'),
    'skill': ('Kenntnisse', 'Skills'),
    'education': ('Ausbildung', 'Education'),
    'certificate': ('Zertifikate und Weiterbildung', 'Certifications and training'),
    'volunteering': ('Ehrenamt', 'Volunteering'),
    'language': ('Sprachen', 'Languages'),
}


@dataclass
class Document:
    stem: str
    paragraphs: list[str]
    headings: set[int]
    fact_ids: list[str]
    language: str
    author: str
    job_id: str
    kind: str
    layout: str = 'ats'
    compact: bool = False
    keep_next: set[int] = field(default_factory=set)
    page_break: int | None = None
    image: tuple[bytes, int, int] | None = None
    image_position: int = 0
    date_index: int | None = None


def prepare(workspace, kind, *, job_id=None, language='de', fact_ids=(), letter_date=None, recipient=(),
            layout='ats', compact=False, photo=None, signature=None, page_two=None, portfolio=None):
    if language not in ('de', 'en') or kind not in ('lebenslauf', 'anschreiben'):
        raise ValueError('Sprache oder Dokumentart unbekannt.')
    if kind != 'anschreiben' and (letter_date or recipient):
        raise ValueError('Datum und Empfängerzeilen sind nur für Anschreiben vorgesehen.')
    if layout not in ('ats', 'design'):
        raise ValueError('Layout muss ats oder design sein.')
    if ((photo and kind != 'lebenslauf') or (signature and kind != 'anschreiben')
            or ((photo or signature) and layout != 'design')):
        raise ValueError('Foto nur für den Design-Lebenslauf und Unterschrift nur für den Design-Brief verwenden.')
    if kind != 'lebenslauf' and (page_two or portfolio):
        raise ValueError('Seitenwechsel und Portfolio-Link sind nur für Lebensläufe vorgesehen.')
    profile = workspace.profile()
    job = workspace.job(workspace.jobs(), job_id) if job_id else None
    contact = profile.get('preferences', {}).get('contact') or ''
    paragraphs = [profile['name'], *profile['location'].splitlines(), *contact.splitlines()]
    if portfolio:
        paragraphs.append('Portfolio: ' + url(portfolio))
    headings, keep_next = set(), set()
    page_break = date_index = None
    stem = (job_id + '-' if job else '') + kind + ('-en' if language == 'en' else '')
    if layout == 'design':
        stem += '-design'
    facts = {f['id']: f for f in profile['facts']}
    if kind == 'anschreiben':
        if not job or not job.get('draft'):
            raise ValueError('Anschreiben benötigt eine Stelle mit gespeichertem Entwurf.')
        if fact_ids:
            raise ValueError('Für Anschreiben gelten die Fakten-IDs des gespeicherten Entwurfs.')
        selected = job['draft'].get('fact_ids')
        if not isinstance(selected, list) or not selected or any(not isinstance(i, str) or i not in facts for i in selected):
            raise ValueError('Faktenverweise des Entwurfs fehlen oder sind im Profil nicht mehr vorhanden.')
        paragraphs += ['', job['company']]
        for line in recipient:
            paragraphs.extend(text(line, 'Empfängerzeile', 300).splitlines())
        if letter_date:
            try:
                stamp = date.fromisoformat(letter_date)
            except ValueError:
                raise ValueError('Briefdatum im Format JJJJ-MM-TT angeben.') from None
            if stamp.isoformat() != letter_date:
                raise ValueError('Briefdatum im Format JJJJ-MM-TT angeben.')
            date_index = len(paragraphs) + 1
            paragraphs += ['', stamp.strftime('%d.%m.%Y') if language == 'de' else stamp.isoformat()]
        paragraphs.append('')
        headings.add(len(paragraphs))
        prefix = 'Application for ' if language == 'en' else 'Bewerbung als '
        subject = prefix + job['role']
        if job.get('reference'):
            label = 'Reference' if language == 'en' else 'Referenz'
            subject += f" ({label}: {job['reference']})"
        paragraphs += [subject, '', *text(job['draft']['text'], 'Entwurf', 30000).splitlines()]
    else:
        selected = list(fact_ids) if fact_ids else list(facts)
        if not selected or len(set(selected)) != len(selected) or any(i not in facts for i in selected):
            raise ValueError('Lebenslauf benötigt vorhandene, eindeutige Fakten-IDs aus dem Profil.')
        if job:
            prefix = 'Target position: ' if language == 'en' else 'Zielposition: '
            paragraphs += [prefix + job['role'] + ', ' + job['company']]
            if not fact_ids:
                hits = keyword_match(profile, job['description'])['matched_fact_ids']
                selected.sort(key=lambda i: i not in hits)
        groups = defaultdict(list)
        for fid in selected:
            fact = facts[fid]
            native = fact.get('language', 'de')
            if native not in ('de', 'en'):
                raise ValueError(f'Fakt {fid}: Ausgangssprache muss de oder en sein.')
            if native == language:
                wording = fact['text']
            else:
                translations = fact.get('translations', {})
                wording = translations.get(language) if isinstance(translations, dict) else None
                if not wording:
                    raise ValueError(f'Fakt {fid}: bestätigte Fassung für {language} fehlt (translations.{language}).')
            group = fact.get('kind', 'profile')
            group = group if isinstance(group, str) and group in SECTIONS else 'profile'
            groups[group].append((fid, text(wording, 'Faktentext').splitlines()))
        for group, labels in SECTIONS.items():
            if group in groups:
                paragraphs.append('')
                headings.add(len(paragraphs))
                heading = len(paragraphs)
                paragraphs.append(labels[1 if language == 'en' else 0])
                for index, (fid, entries) in enumerate(groups[group]):
                    first = len(paragraphs)
                    if fid == page_two:
                        page_break = heading if index == 0 else first
                    # Kurze mehrzeilige Stationen zusammenhalten; bei langen wenigstens den Titel.
                    keep_next.update(range(first, first + min(len(entries) - 1, 7 if len(entries) <= 8 else 1)))
                    paragraphs.extend(entries)
        if page_two and page_break is None:
            raise ValueError('Fakt für Seite zwei muss in der gewählten Fassung enthalten sein.')
    position = 0
    if signature:
        if paragraphs[-1].strip() != profile['name']:
            paragraphs.append(profile['name'])
        position = len(paragraphs) - 1
    image = _picture(workspace, photo or signature, signature=bool(signature)) if photo or signature else None
    return Document(stem, paragraphs, headings, selected, language, profile['name'], job_id or '', kind,
                    layout, compact, keep_next, page_break, image, position, date_index)


def _picture(workspace, source, *, signature):
    path = workspace.path(source)
    if not path.is_file() or not 0 < path.stat().st_size <= 12 * 1024 * 1024:
        raise ValueError('Bild als private PNG- oder JPEG-Datei bis 12 MiB bereitstellen.')
    with path.open('rb') as handle:
        magic = handle.read(8)
    codec = 'png' if magic == b'\x89PNG\r\n\x1a\n' else 'jpeg' if magic.startswith(b'\xff\xd8\xff') else None
    if not codec:
        raise ValueError('Foto und Unterschrift müssen PNG oder JPEG sein.')
    binary = shutil.which('magick')
    if not binary:
        raise ValueError('Für die Bildaufbereitung wird ImageMagick (magick) benötigt.')
    # Bits aus dem gewählten Bild einlesen; Dateiname und Originalmetadaten gelangen nicht in das DOCX.
    result = subprocess.run([binary, '-limit', 'memory', '128MiB', '-limit', 'map', '256MiB',
                             '-limit', 'disk', '256MiB', '-limit', 'thread', '1', codec + ':-[0]',
                             '-auto-orient', '-resize', '500x500>', '-strip',
                             '-define', 'png:exclude-chunk=all', 'png:-'],
                            input=path.read_bytes(), capture_output=True, timeout=45)
    data = result.stdout
    if result.returncode or not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) < 24:
        raise ValueError('Bild konnte nicht als PNG oder JPEG gelesen werden.')
    width, height = struct.unpack('>II', data[16:24])
    if not 0 < width <= 500 or not 0 < height <= 500:
        raise ValueError('Ungültige Bildmaße.')
    scale = min(1440000 / width, (500000 if signature else 1250000) / height)
    return data, int(width * scale), int(height * scale)


def _drawing(width, height):
    return (f'<w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
            f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><wp:extent cx="{width}" cy="{height}"/>'
            '<wp:docPr id="1" name="Bild"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="Bild"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="rIdImage"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            '</wp:inline></w:drawing></w:r>')


def _save_new(path, data):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Dokument existiert bereits. Anderen Dateinamen verwenden.') from None
    try:
        with os.fdopen(fd, 'wb') as target:
            target.write(data)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def docx(path, paragraphs, *, headings=(), language='de', author='', subject='', layout='ats',
         compact=False, keep_next=(), page_break=None, image=None, image_position=0, date_index=None):
    body = []
    for index, line in enumerate(paragraphs):
        if image and index == image_position:
            align = 'right' if index == 0 else 'left'
            body.append(f'<w:p><w:pPr><w:keepNext/><w:jc w:val="{align}"/></w:pPr>{_drawing(*image[1:])}</w:p>')
        heading = index in headings
        style = '<w:keepNext/>' if heading or index in keep_next else ''
        style += '<w:keepLines/>'
        if index == page_break:
            style += '<w:pageBreakBefore/>'
        if layout == 'design' and heading:
            style += '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="2" w:color="38576A"/></w:pBdr>'
        if compact:
            style += '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
        elif layout == 'design':
            style += '<w:spacing w:after="50"/>'
        if index == date_index:
            style += '<w:jc w:val="right"/>'
        if heading:
            style += '<w:outlineLvl w:val="0"/>'
        run = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>' if layout == 'design' else ''
        if heading or index == 0:
            run += '<w:b/>'
            if layout == 'design':
                run += '<w:color w:val="244559"/>'
        size = 21 if compact else 22
        if index == 0:
            size = 36 if layout == 'design' else 32
        run += f'<w:sz w:val="{size}"/>'
        run += '<w:lang w:val="' + ('en-US' if language == 'en' else 'de-DE') + '"/>'
        body.append(f'<w:p><w:pPr>{style}</w:pPr><w:r><w:rPr>{run}</w:rPr><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>')
    document = (f'<w:document xmlns:w="{W}"><w:body>' + ''.join(body) +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>')
    content = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
               '<Default Extension="xml" ContentType="application/xml"/>'
               '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
               '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>')
    metadata = ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>{escape(author)}</dc:creator>'
                f'<dc:subject>{escape(subject)}</dc:subject></cp:coreProperties>')
    try:
        ET.fromstring(document)
        ET.fromstring(metadata)
    except (ET.ParseError, UnicodeError):
        raise ValueError('Unzulässiges Zeichen im Dokumenttext.') from None
    if image:
        content = content.replace('</Types>', '<Default Extension="png" ContentType="image/png"/></Types>')
    data = BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, xml in [('word/document.xml', document), ('[Content_Types].xml', content), ('_rels/.rels', rels), ('docProps/core.xml', metadata)]:
            archive.writestr(name, xml.encode('utf-8'))
        if image:
            archive.writestr('word/media/image.png', image[0])
            archive.writestr('word/_rels/document.xml.rels',
                             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                             '<Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                             'Target="media/image.png"/></Relationships>')
    _save_new(Path(path), data.getvalue())


def _next_path(workspace, stem):
    version = 1
    while True:
        name = stem if version == 1 else f'{stem}-v{version}'
        out = workspace.path('dokumente', name + '.docx')
        if not out.exists() and not workspace.path('dokumente', name + '.pdf').exists():
            return out
        version += 1


def _render_file(path, document, compact):
    docx(path, document.paragraphs, headings=document.headings, language=document.language,
         author=document.author, subject=document.job_id, layout=document.layout, compact=compact,
         keep_next=document.keep_next, page_break=document.page_break, image=document.image,
         image_position=document.image_position, date_index=document.date_index)


def save(workspace, document):
    with workspace.locked():
        out = _next_path(workspace, document.stem)
        _render_file(out, document, document.compact)
    return out


def save_fitted(workspace, document):
    info = shutil.which('pdfinfo')
    if not info:
        raise ValueError('Zum Einpassen wird pdfinfo aus Poppler benötigt.')
    budget = 1 if document.kind == 'anschreiben' else 2
    with tempfile.TemporaryDirectory() as temp:
        for compact in ([True] if document.compact else [False, True]):
            doc = Path(temp) / ('kompakt.docx' if compact else 'normal.docx')
            _render_file(doc, document, compact)
            pdf = convert_pdf(doc)
            result = subprocess.run([info, str(pdf)], capture_output=True, text=True, timeout=60,
                                    env={**os.environ, 'LC_ALL': 'C'})
            pages = re.search(r'^Pages:\s+(\d+)\s*$', result.stdout, re.M)
            if result.returncode or not pages:
                raise ValueError('Seitenzahl zur Einpassung konnte nicht gemessen werden.')
            if 0 < int(pages[1]) <= budget:
                with workspace.locked():
                    out = _next_path(workspace, document.stem)
                    _save_new(out, doc.read_bytes())
                    try:
                        _save_new(out.with_suffix('.pdf'), pdf.read_bytes())
                    except BaseException:
                        out.unlink()
                        raise
                return out, int(pages[1]), compact
    raise ValueError(f'Die vollständige Fassung überschreitet auch kompakt {budget} Seite(n). Faktenauswahl oder Brieftext kürzen.')


def render(workspace, jid=None):
    """Bestehende Schnittstelle für deutsche Standardunterlagen."""
    return save(workspace, prepare(workspace, 'anschreiben' if jid else 'lebenslauf', job_id=jid))


def office_binary():
    binary = shutil.which('soffice') or shutil.which('libreoffice')
    candidates = [Path('/Applications/LibreOffice.app/Contents/MacOS/soffice'),
                  Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'LibreOffice/program/soffice.exe']
    return binary or next((str(p) for p in candidates if p.is_file()), None)


def convert_pdf(path):
    path = Path(path).resolve()
    target = path.with_suffix('.pdf')
    if target.exists() or target.is_symlink():
        raise ValueError('PDF existiert bereits. Anderen Dateinamen verwenden.')
    binary = office_binary()
    if not binary:
        raise ValueError(f'DOCX gespeichert: {path}. Für PDF LibreOffice lokal installieren oder in Word als PDF exportieren.')
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp).resolve()
        converted = folder / target.name
        result = subprocess.run([binary, '-env:UserInstallation=' + (folder / 'profile').as_uri(), '--headless',
                                 '--convert-to', 'pdf', '--outdir', str(folder), str(path)], capture_output=True, timeout=120)
        if result.returncode or not converted.is_file():
            raise ValueError('PDF-Konvertierung fehlgeschlagen. DOCX bleibt erhalten.')
        data = converted.read_bytes()
        if not data.startswith(b'%PDF-'):
            raise ValueError('Konvertierung lieferte keine PDF-Datei.')
        _save_new(target, data)
    return target
