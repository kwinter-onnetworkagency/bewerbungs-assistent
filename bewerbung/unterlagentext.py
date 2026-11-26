"""Abgleich der aktuellen Unterlagen mit Profil, Stellenbezug und tatsächlich gelesenem Text."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import unicodedata
from xml.etree import ElementTree as ET
import zipfile

from .documents import W, convert_pdf, prepare, save, save_fitted

NS = {'w': W}
KINDS = ('lebenslauf', 'anschreiben')
COMMANDS = (*KINDS, 'textpruefung', 'ats-pruefung')


def register(commands):
    for name, help_text in zip(COMMANDS, (
        'A4-Lebenslauf aus belegten Fakten erstellen', 'Gespeicherten Anschreibenentwurf als A4-Dokument erstellen',
        'Text der gewählten Unterlage gegen ihr Profil prüfen', 'Text und Lesereihenfolge einer DOCX oder PDF abgleichen',
    )):
        parser = commands.add_parser(name, help=help_text)
        if name == 'anschreiben':
            parser.add_argument('id', help='Stellen-ID des Entwurfs')
        else:
            parser.add_argument('--stelle', help='Zielstelle, bei Anschreiben erforderlich')
            parser.add_argument('--fakt', action='append', default=[], help='CV auf diesen Profilfakt beschränken, wiederholbar')
        parser.add_argument('--layout', choices=('ats', 'design'), default='ats')
        parser.add_argument('--kompakt', action='store_true', help='Absatzabstände und Schriftgröße für eine kurze Fassung anpassen')
        if name != 'anschreiben':
            parser.add_argument('--foto', help='Privates PNG/JPEG im Arbeitsordner für den Design-Lebenslauf')
            parser.add_argument('--seite-2-ab', help='Seite zwei ausdrücklich bei dieser Fakten-ID beginnen')
            parser.add_argument('--portfolio-url', help='Selbst bestätigte Portfolio-URL für diese CV-Fassung')
        if name != 'lebenslauf':
            parser.add_argument('--unterschrift', help='Eigenes Unterschriftsbild im Design-Brief')
            parser.add_argument('--datum', help='Briefdatum im Format JJJJ-MM-TT')
            parser.add_argument('--empfaengerzeile', action='append', default=[], help='Bestätigte Abteilung, Person oder Anschrift, wiederholbar')
        parser.add_argument('--sprache', choices=('de', 'en'), default='de')
        if name in KINDS:
            parser.add_argument('--pdf', action='store_true')
            parser.add_argument('--einpassen', action='store_true', help='DOCX und PDF innerhalb des Seitenlimits ausgeben')
        else:
            parser.add_argument('art', choices=KINDS)
        if name == 'ats-pruefung':
            parser.add_argument('datei', help='Lokale DOCX/PDF, relativer Pfad ab dem privaten Arbeitsordner')


def check_text(document):
    for index, line in enumerate(document.paragraphs, 1):
        if any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in line):
            raise ValueError(f'Textprüfung: unsichtbares Steuer- oder Formatzeichen in Absatz {index}.')
        if re.search(r'\{\{[^{}]*\}\}|\[(?:NAME|FIRMA|UNTERNEHMEN|ROLLE|COMPANY|EMPLOYER|POSITION)\]|\b(?:TODO|PLATZHALTER)\b', line, re.I):
            raise ValueError(f'Textprüfung: möglicher Platzhalter in Absatz {index}.')
    if document.kind == 'anschreiben':
        lines = [line.strip() for line in document.paragraphs if line.strip()]
        for salutation, following in zip(lines, lines[1:]):
            if document.language == 'en' and re.match(r'^Dear\s', salutation, re.I) and following[0].islower():
                raise ValueError('Textprüfung: englischen Absatzbeginn nach der Anrede großschreiben.')
            if (document.language == 'de' and re.match(r'^(Sehr geehrt|Guten Tag|Hallo\b|Liebe[rn]?\b)', salutation, re.I)
                    and salutation.endswith(',') and re.match(r'^(Ich|Wir|Mit|Hiermit|Anbei)\b', following)):
                raise ValueError('Textprüfung: deutschen Absatzbeginn nach der Anrede mit Komma prüfen.')


def _words(value):
    return ' '.join(unicodedata.normalize('NFC', value).split())


def _docx_text(path, document):
    try:
        with zipfile.ZipFile(path) as package:
            member = package.getinfo('word/document.xml')
            if member.file_size > 8 * 1024 * 1024:
                raise ValueError('DOCX-Textteil zu groß für die lokale Prüfung.')
            root = ET.fromstring(package.read(member))
            if document.image:
                image = package.getinfo('word/media/image.png')
                if image.file_size != len(document.image[0]) or package.read(image) != document.image[0]:
                    raise ValueError('Eingebettetes Bild weicht von der ausgewählten Fassung ab.')
                relationships = package.getinfo('word/_rels/document.xml.rels')
                if relationships.file_size > 65536:
                    raise ValueError('Unerwartete Bildbeziehungen.')
                rels = ET.fromstring(package.read(relationships))
                pairs = [(r.get('Id'), r.get('Target'), r.get('TargetMode')) for r in rels if r.get('Id') == 'rIdImage']
                if pairs != [('rIdImage', 'media/image.png', None)]:
                    raise ValueError('Bildverweis ist nicht eindeutig in der DOCX eingebettet.')
            metadata = None
            if 'docProps/core.xml' in package.namelist():
                properties = package.getinfo('docProps/core.xml')
                if properties.file_size > 65536:
                    raise ValueError('DOCX-Metadaten sind zu groß.')
                metadata = ET.fromstring(package.read(properties))
    except (zipfile.BadZipFile, KeyError, ET.ParseError, RuntimeError) as exc:
        raise ValueError('DOCX-Hauptdokument ist nicht lesbar.') from exc
    body = root.find('w:body', NS)
    if body is None:
        raise ValueError('DOCX enthält keinen Dokumentkörper.')
    drawings = body.findall('.//w:drawing', NS)
    embeds = body.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
    embedded = [b.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed') for b in embeds]
    if (len(drawings) != int(document.image is not None) or embedded != (['rIdImage'] if document.image else [])):
        raise ValueError('Grafiken entsprechen nicht der gewählten Dokumentfassung.')
    unsupported = ('tbl', 'pict', 'txbxContent', 'altChunk', 'vanish', 'del', 'ins', 'fldSimple', 'instrText',
                   'headerReference', 'footerReference', 'footnoteReference', 'endnoteReference')
    if any(body.find(f'.//w:{tag}', NS) is not None for tag in unsupported):
        raise ValueError('DOCX enthält zusätzliche Textebenen, Tabellen, Felder oder ausgeblendeten Text. Einspaltige Fassung prüfen.')
    sections = body.findall('.//w:sectPr', NS)
    if not sections:
        raise ValueError('DOCX-Seitenformat fehlt.')
    for section in sections:
        size = section.find('w:pgSz', NS)
        columns = section.find('w:cols', NS)
        if (size is None or size.get(f'{{{W}}}w') not in ('11906', '11907') or size.get(f'{{{W}}}h') not in ('16838', '16839')
                or (columns is not None and columns.get(f'{{{W}}}num', '1') != '1')):
            raise ValueError('DOCX benötigt einspaltiges A4-Hochformat.')
    actual, headings, breaks = [], [], []
    for paragraph in body.findall('.//w:p', NS):
        parts = []
        for element in paragraph.iter():
            if element.tag == f'{{{W}}}t':
                parts.append(element.text or '')
            elif element.tag in (f'{{{W}}}br', f'{{{W}}}tab', f'{{{W}}}cr'):
                parts.append(' ')
        line = _words(''.join(parts))
        if line:
            if paragraph.find('w:pPr/w:pageBreakBefore', NS) is not None:
                breaks.append(len(actual))
            actual.append(line)
        level = paragraph.find('w:pPr/w:outlineLvl', NS)
        if level is not None and level.get(f'{{{W}}}val') == '0':
            headings.append(line)
    expected = [_words(line) for line in document.paragraphs if _words(line)]
    if actual != expected:
        raise ValueError('DOCX-Text, Absatzgrenzen oder Lesereihenfolge weichen von der aktuellen Fassung ab.')
    expected_breaks = [] if document.page_break is None else [sum(bool(_words(x)) for x in document.paragraphs[:document.page_break])]
    if breaks != expected_breaks:
        raise ValueError('Der gespeicherte DOCX-Seitenwechsel weicht von der gewählten Fassung ab.')
    if document.layout == 'design' and len(body.findall('.//w:pBdr/w:bottom', NS)) != len(document.headings):
        raise ValueError('DOCX-Abschnittsgestaltung entspricht nicht der Designfassung.')
    if headings != [_words(document.paragraphs[i]) for i in sorted(document.headings)]:
        raise ValueError('DOCX-Abschnittsüberschriften fehlen oder sind falsch gegliedert.')
    if document.job_id:
        subject = metadata.findtext('{http://purl.org/dc/elements/1.1/}subject') if metadata is not None else None
        if subject != document.job_id:
            raise ValueError('Stellen-ID in den DOCX-Metadaten fehlt oder gehört zu einer anderen Stelle.')
    return f'{len(actual)} Textabsätze, {len(headings)} Abschnittsüberschriften, A4'


def _pdf_text(path, document):
    tool = shutil.which('pdftotext')
    if not tool:
        raise ValueError('Für die PDF-Leseprüfung wird pdftotext aus Poppler benötigt.')
    result = subprocess.run([tool, '-enc', 'UTF-8', str(path.resolve()), '-'], capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('PDF-Text kann nicht gelesen werden. Datei und Leseschutz prüfen.')
    text = result.stdout.decode('utf-8')
    if not text.strip():
        raise ValueError('PDF ohne lesbare Textebene.')
    pages = text.rstrip('\r\n').removesuffix('\f').split('\f')
    limit = 1 if document.kind == 'anschreiben' else 2
    if len(pages) > limit:
        raise ValueError(f'PDF hat {len(pages)} Seiten, maximal {limit} für diese Dokumentart.')
    if _words(text) != _words(' '.join(document.paragraphs)):
        raise ValueError('PDF-Text oder Lesereihenfolge weichen von der aktuellen Fassung ab.')
    if document.page_break is not None:
        expected_first = _words(document.paragraphs[document.page_break])
        if len(pages) != 2 or not _words(pages[1]).startswith(expected_first):
            raise ValueError('Der Beginn der zweiten PDF-Seite passt nicht zum gewählten Seitenwechsel.')
    for index in document.headings:
        words = re.escape(_words(document.paragraphs[index])).replace(r'\ ', r'\s+')
        pattern = re.compile(r'^\s*' + words + r'[ \t]*$', re.M)
        matches = [(page, m.end()) for page in pages for m in pattern.finditer(page)]
        if not matches:
            raise ValueError('PDF-Abschnittsüberschrift ist nicht als eigene Zeile lesbar.')
        if not any(page[end:].strip() for page, end in matches):
            raise ValueError('PDF-Abschnittsüberschrift steht isoliert am Seitenende.')
    info = shutil.which('pdfinfo')
    if not info:
        raise ValueError('Für PDF-Seitenformat und Stellen-ID wird pdfinfo aus Poppler benötigt.')
    metadata = subprocess.run([info, '-f', '1', '-l', str(len(pages)), str(path.resolve())],
                              capture_output=True, encoding='utf-8', errors='replace', timeout=60,
                              env={**os.environ, 'LC_ALL': 'C'})
    sizes = re.findall(r'^Page\s+\d+ size:\s+([\d.]+) x ([\d.]+) pts', metadata.stdout, re.M)
    if metadata.returncode or len(sizes) != len(pages) or any(
            abs(float(w) - 595.28) > 1 or abs(float(h) - 841.89) > 1 for w, h in sizes):
        raise ValueError('PDF-Seitenformat ist nicht durchgehend A4-Hochformat oder nicht lesbar.')
    subject = re.search(r'^Subject:[ \t]*(.*)$', metadata.stdout, re.M)
    if document.job_id and (not subject or subject.group(1).strip() != document.job_id):
        raise ValueError('Stellen-ID in den PDF-Metadaten fehlt oder gehört zu einer anderen Stelle.')
    if document.image:
        images = shutil.which('pdfimages')
        if not images:
            raise ValueError('Zur Bildprüfung wird pdfimages aus Poppler benötigt.')
        listed = subprocess.run([images, '-list', str(path.resolve())], capture_output=True, text=True, timeout=60)
        if listed.returncode or not re.search(r'^\s*\d+\s+\d+\s+image\s+', listed.stdout, re.M):
            raise ValueError('Die gewählte Designfassung enthält kein nachweisbares PDF-Bild.')
    return f'{len(pages)} Seite(n), {len(document.headings)} lesbare Abschnittsüberschriften, A4'


def check_file(path, document):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Prüfdatei fehlt oder überschreitet 32 MiB.')
    if path.suffix.lower() == '.docx':
        return _docx_text(path, document)
    if path.suffix.lower() == '.pdf':
        return _pdf_text(path, document)
    raise ValueError('Als Prüfdatei sind DOCX und PDF zulässig.')


def run(args, workspace):
    if args.command not in COMMANDS:
        return False
    kind = args.command if args.command in KINDS else args.art
    document = prepare(workspace, kind, job_id=getattr(args, 'id', None) or getattr(args, 'stelle', None),
                       language=args.sprache, fact_ids=getattr(args, 'fakt', []), letter_date=getattr(args, 'datum', None),
                       recipient=getattr(args, 'empfaengerzeile', []), layout=args.layout, compact=args.kompakt,
                       photo=getattr(args, 'foto', None), signature=getattr(args, 'unterschrift', None),
                       page_two=getattr(args, 'seite_2_ab', None), portfolio=getattr(args, 'portfolio_url', None))
    if args.command in KINDS:
        if args.einpassen:
            path, pages, compact = save_fitted(workspace, document)
            print(path)
            print(path.with_suffix('.pdf'))
            print(f"Gemessen: {pages} Seite(n), Satz: {'kompakt' if compact else 'normal'}.")
            return True
        path = save(workspace, document)
        print(path)
        if args.pdf:
            print(convert_pdf(path))
    elif args.command == 'textpruefung':
        check_text(document)
        print('Textprüfung bestanden. Verwendete Fakten-IDs: ' + ', '.join(document.fact_ids))
        print('Aussagen, Quellen, Übersetzungen und Stellenbezug bitte selbst gegenlesen.')
    else:
        check_text(document)
        result = check_file(workspace.root / args.datei, document)
        print('ATS-Lesetest bestanden: ' + result + '. Text und Reihenfolge entsprechen der gewählten Fassung.')
    return True
