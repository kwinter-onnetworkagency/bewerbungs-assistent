"""Persönliche Gesprächsmappen, vCards und Kalendereinträge im Arbeitsordner."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .core import identifier, read, text, url, write, write_bytes


def register(commands):
    contact = commands.add_parser('kontakt', help='Bestätigten beruflichen Kontakt als private vCard sichern')
    contact.add_argument('id', help='Stellen-ID')
    contact.add_argument('--name', required=True, help='Anzeigename der Kontaktperson')
    contact.add_argument('--email', required=True, help='Bestätigte berufliche E-Mail-Adresse')
    for field in ('vorname', 'nachname', 'funktion', 'abteilung', 'strasse', 'plz', 'stadt', 'region', 'land', 'website'):
        contact.add_argument('--' + field)
    for field in ('telefon', 'mobil', 'fax'):
        contact.add_argument('--' + field, action='append', default=[], help='Berufliche Nummer, wiederholbar')
    meeting = commands.add_parser('termin', help='Bestätigten Gesprächstermin als private Kalenderdatei sichern')
    meeting.add_argument('id', help='Stellen-ID')
    meeting.add_argument('--runde', required=True, help='Dauerhafte Runden-ID, z. B. fachrunde')
    for field in ('start', 'ende'):
        meeting.add_argument('--' + field, required=True, help='ISO-Zeitpunkt mit UTC-Versatz')
    meeting.add_argument('--quelle', required=True, help='Für die Kalenderbeschreibung freigegebene Bezeichnung der Einladung')
    meeting.add_argument('--zeitzone', help='Optionale zusätzliche Ortszeitprüfung, z. B. Europe/Berlin')
    meeting.add_argument('--ort', help='Bestätigter Ort oder Besprechungslink')
    meeting.add_argument('--vormerkung', action='store_true', help='Ausdrückliche persönliche Vormerkung eines Terminvorschlags')
    meeting.add_argument('--kalender', help='Eindeutiger Name des Zielkalenders für --mac')
    for parser in (contact, meeting):
        parser.add_argument('--aktualisieren', action='store_true', help='Bekannten Kontakt oder Termin mit gleicher UID aktualisieren')
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--mac', action='store_true', help='Datensatz in der lokalen macOS-App anlegen und zurücklesen')
        mode.add_argument('--oeffnen', action='store_true', help='Diese Datei ausdrücklich an das gewählte Standardprogramm übergeben')
    pack = commands.add_parser('gespraechsmappe', help='Private Vor- und Nachbereitung für eine einzelne Gesprächsrunde')
    pack.add_argument('id', help='Stellen-ID')
    pack.add_argument('--runde', required=True)
    pack.add_argument('--fakt', required=True, action='append', help='Für diese Runde bestätigte Fakten-ID, wiederholbar')
    pack.add_argument('--notiz', action='append', default=[], help='Titel einer vorhandenen Gesprächsnotiz zur Stelle, wiederholbar')


def _single(value, label, limit=500):
    value = text(value, label, limit)
    if any(unicodedata.category(c) in {'Cc', 'Cs'} or c in '\u2028\u2029' for c in value):
        raise ValueError(f'{label} muss in einer Zeile stehen.')
    return value


def _escape(value):
    return value.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,')


def _card(lines):
    """Physische Zeilen auf 75 UTF-8-Oktette einschließlich Fortsetzungsleerzeichen falten."""
    result = []
    for line in lines:
        part, length = [], 0
        for char in line:
            size = len(char.encode('utf-8'))
            if length + size > 75:
                result.append(''.join(part))
                part, length = [' '], 1
            part.append(char)
            length += size
        result.append(''.join(part))
    return ('\r\n'.join(result) + '\r\n').encode('utf-8')


def _lines(path):
    return path.read_bytes().decode('utf-8').replace('\r\n ', '').splitlines()


def _uid(workspace, identity):
    created = read(workspace.path('workspace.json')).get('created_at', '')
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'urn:bewerbungs-assistent:{created}:{identity}'))


def _round(workspace, job, key):
    return workspace.path('gespraeche', job['id'], 'runde-' + identifier(key))


def contact(workspace, job, args):
    name = _single(args.name, 'Kontaktname')
    email = _single(args.email, 'E-Mail-Adresse', 254)
    if not re.fullmatch(r"[^\s@,:;<>\\]+@[^\s@,:;<>\\]+\.[^\s@,:;<>\\]+", email):
        raise ValueError('Bitte eine einzelne berufliche E-Mail-Adresse angeben.')
    key = _uid(workspace, 'kontakt:' + email.casefold())
    uid = 'UID:urn:uuid:' + key
    # Einige Adressbücher ignorieren FN beim Namensimport. Ungeteilten Anzeigenamen beibehalten.
    given = args.vorname or (name if not args.nachname else '')
    family = args.nachname or ''
    parts = [_escape(_single(v, 'Namensbestandteil')) if v else '' for v in (family, given)]
    lines = ['BEGIN:VCARD', 'VERSION:4.0', uid, 'FN:' + _escape(name), 'N:' + ';'.join([*parts, '', '', '']),
             'ORG:' + _escape(_single(job['company'], 'Unternehmen')), 'EMAIL:' + _escape(email)]
    if args.abteilung:
        lines[-2] += ';' + _escape(_single(args.abteilung, 'Abteilung'))
    for label, numbers in [('work', args.telefon), ('cell', args.mobil), ('fax', args.fax)]:
        for number in dict.fromkeys(numbers):
            lines.append(f'TEL;TYPE={label};VALUE=text:' + _escape(_single(number, 'Telefonnummer')))
    for field, value in [('TITLE:', args.funktion)]:
        if value:
            lines.append(field + _escape(_single(value, field)))
    if any((args.strasse, args.stadt, args.region, args.plz, args.land)):
        address = (None, None, args.strasse, args.stadt, args.region, args.plz, args.land)
        lines.append('ADR;TYPE=work:' + ';'.join(_escape(_single(v, 'Adressfeld')) if v else '' for v in address))
    if args.website:
        lines.append('URL:' + url(_single(args.website, 'Website', 2000)))
    lines.append('END:VCARD')
    data = _card(lines)
    output = workspace.path('kontakte', key + '.vcf')
    output.parent.mkdir(mode=0o700, exist_ok=True)
    if output.exists():
        if output.read_bytes() == data:
            return output
        if uid not in _lines(output) or not args.aktualisieren:
            raise ValueError('Kontakt mit dieser Adresse ist bereits vorhanden. Angaben prüfen und ggf. --aktualisieren verwenden.')
    write_bytes(output, data)
    return output


def _timestamp(value, zone):
    if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)', value):
        raise ValueError('Zeitpunkt braucht Datum, Uhrzeit und UTC-Versatz, z. B. 2027-03-15T10:00+01:00.')
    stamp = datetime.fromisoformat(value)
    if zone and (stamp.astimezone(zone).utcoffset() != stamp.utcoffset()):
        raise ValueError('Ortszeit und UTC-Versatz stimmen mit der angegebenen Zeitzone nicht überein.')
    return stamp.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def meeting(workspace, job, args):
    try:
        zone = ZoneInfo(args.zeitzone) if args.zeitzone else None
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Zeitzone unbekannt oder lokale Zeitzonendaten fehlen. Geprüften UTC-Versatz verwenden.') from None
    start, end = _timestamp(args.start, zone), _timestamp(args.ende, zone)
    if start >= end:
        raise ValueError('Das Gespräch muss nach dem Beginn enden.')
    folder = _round(workspace, job, args.runde)
    uid = 'UID:' + _uid(workspace, 'termin:' + job['id'] + ':' + args.runde)
    title = _single(f"{job['company']}, {job['role']}, {args.runde}", 'Termintitel', 1000)
    if args.vormerkung:
        title = 'Vormerkung · ' + title
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Bewerbungs-Assistent//DE', 'BEGIN:VEVENT', uid,
             'DTSTART:' + start, 'DTEND:' + end, 'SUMMARY:' + _escape(title),
             'DESCRIPTION:' + _escape(_single(args.quelle, 'Einladungsquelle')), 'CLASS:PRIVATE']
    if args.vormerkung:
        lines.append('STATUS:TENTATIVE')
    if args.ort:
        lines.append('LOCATION:' + _escape(_single(args.ort, 'Ort', 2000)))
    tail = ['END:VEVENT', 'END:VCALENDAR']
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = workspace.path(folder, 'Termin.ics')
    sequence = 0
    if output.exists():
        previous = _lines(output)
        revisions = [row.partition(':')[2] for row in previous if row.startswith('SEQUENCE:')]
        stamps = [row for row in previous if row.startswith('DTSTAMP:')]
        if (uid not in previous or len(revisions) != 1 or not re.fullmatch(r'[0-9]{1,9}', revisions[0])
                or len(stamps) != 1 or not re.fullmatch(r'DTSTAMP:\d{8}T\d{6}Z', stamps[0])):
            raise ValueError('Vorhandene Kalenderdatei lässt sich dieser Runde nicht sicher zuordnen.')
        content = [row for row in previous if not row.startswith(('DTSTAMP:', 'SEQUENCE:'))]
        if lines + tail == content:
            return output
        if not args.aktualisieren:
            raise ValueError('Termin hat abweichende Angaben. Bestätigte Änderung mit --aktualisieren übernehmen.')
        sequence = int(revisions[0]) + 1
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    write_bytes(output, _card(lines + ['DTSTAMP:' + stamp, f'SEQUENCE:{sequence}'] + tail))
    return output


def _evidence(workspace, note):
    proof = note.get('evidence')
    if not proof:
        return ''
    if not isinstance(proof, dict) or not isinstance(proof.get('file'), str):
        raise ValueError('Ungültiger Nachweisverweis in der Gesprächsnotiz.')
    key = proof.get('sha256', '')
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{64}', key):
        raise ValueError('Ungültiger Nachweisverweis in der Gesprächsnotiz.')
    rel = Path(proof['file'])
    if rel.parent != Path('belege') or rel.stem != key:
        raise ValueError('Nachweisverweis liegt außerhalb der privaten Belegsammlung.')
    path = workspace.path(rel)
    if not path.is_file():
        raise ValueError('Gesicherter Notizbeleg fehlt.')
    with path.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != key:
            raise ValueError('Gesicherter Notizbeleg wurde verändert.')
    return 'Lokaler Beleg (SHA-256): ' + key


def _practice(job, facts):
    lines = ['Übung vor dem Gespräch', '',
             '1. Kurzbriefing: Welches Ziel hat diese Runde? Welche drei Aussagen sollen in Erinnerung bleiben?',
             f"2. Stelle dich in 90 Sekunden für die Rolle {job['role']} vor. Nenne einen Grund und ein belegtes Beispiel."]
    for fact in facts:
        lines += ['', 'Praxisbeispiel ' + fact['id'], fact['text'], 'Quelle: ' + fact['source'],
                  'Situation und Aufgabe:', 'Dein eigener Beitrag:', 'Ergebnis laut Quelle:', 'Bezug zur Anforderung:']
    lines += ['', '3. Fallübung: Wähle eine Aufgabe aus der Anzeige. Wie würdest du beginnen? '
              'Welche Informationen fehlen und woran lässt sich der Erfolg erkennen?',
              '4. Welche zwei Fragen möchtest du den Gesprächspartnern stellen?',
              '5. Bitte im Rollenspiel um jeweils eine Frage. Beantworte sie, bevor du Feedback einholst.']
    return lines


def folder_for_round(workspace, job, args):
    folder = _round(workspace, job, args.runde)
    known = {f['id']: f for f in workspace.profile()['facts']}
    ids = list(dict.fromkeys(args.fakt))
    if not ids or any(fid not in known for fid in ids):
        raise ValueError('Mindestens einen vorhandenen Profilfakt ausdrücklich für die Runde auswählen.')
    facts = [known[fid] for fid in ids]
    latest = {n['title']: n for n in job.get('notes', []) if n['kind'] == 'gespraech'}
    titles = list(dict.fromkeys(args.notiz or ([args.runde] if args.runde in latest else [])))
    lines = [f"Gesprächsrunde {args.runde}", job['company'], job['role'], '', 'Stellenanzeige', job['url'],
             'Stand der Erfassung: ' + job['checked_at'], job['description'], '', 'Terminstand']
    calendar = workspace.path(folder, 'Termin.ics')
    if calendar.exists():
        fields = dict(row.split(':', 1) for row in _lines(calendar) if ':' in row)
        expected_uid = _uid(workspace, 'termin:' + job['id'] + ':' + args.runde)
        if fields.get('UID') != expected_uid:
            raise ValueError('Kalenderdatei gehört nicht zu dieser Gesprächsrunde.')
        lines.append('Kalenderdatei: Termin.ics')
        for label, field in [('Beginn', 'DTSTART'), ('Ende', 'DTEND')]:
            stamp = datetime.strptime(fields.get(field, ''), '%Y%m%dT%H%M%SZ')
            lines.append(f'{label}: {stamp:%d.%m.%Y %H:%M} UTC')
        for label, field in [('Quelle', 'DESCRIPTION'), ('Ort', 'LOCATION')]:
            if field in fields:
                value = re.sub(r'\\([\\;,])', r'\1', fields[field])
                lines.append(f'{label}: {value}')
    else:
        lines.append('Offen. Bestätigten Termin aus der Einladung ergänzen.')
    lines += ['', 'Ausgewählte Gesprächsnotizen']
    if not titles:
        lines.append('Offen. Gesprächspartner, Format und Sprache anhand der Einladung klären.')
    for title in titles:
        if title not in latest:
            raise ValueError('Gesprächsnotiz für diese Stelle nicht gefunden: ' + title)
        note = latest[title]
        lines += ['', title, 'Erfasst: ' + note['recorded_at'], note['content']]
        lines.extend('Quelle: ' + link for link in note.get('sources', []))
        evidence = _evidence(workspace, note)
        if evidence:
            lines.append(evidence)
    lines += ['', *_practice(job, facts)]
    data = ('\n'.join(lines) + '\n').encode('utf-8')
    fingerprint = hashlib.sha256(data).hexdigest()[:20]
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    prep = workspace.path(folder, 'Vorbereitung-' + fingerprint + '.txt')
    if prep.exists() and prep.read_bytes() != data:
        raise ValueError('Vorbereitungsfassung wurde manuell bearbeitet. Eigene Fassung separat sichern und umbenennen.')
    if not prep.exists():
        write_bytes(prep, data)
    follow = workspace.path(folder, 'Nachbereitung.txt')
    if not follow.exists():
        followup = (f"Nachbereitung {args.runde}\n{job['company']}, {job['role']}\n\n"
                    "Tatsächliches Datum und Teilnehmende:\n\nAussagen der Gesprächspartner (wer sagte was?):\n\n"
                    "Beobachtungen und eigene Einschätzung:\n\nBestätigte Entscheidungen und Beleg:\n\n"
                    "Offene Fragen:\n\nVereinbarte Aufgaben, Zuständige und Fristen:\n\n"
                    "Nächste Runde und Terminstand:\n")
        write_bytes(follow, followup.encode('utf-8'))
    return prep, follow


def native_request(args, w, job):
    if args.command == 'kontakt':
        fields = {'firstName': args.vorname or (args.name if not args.nachname else ''),
                  'lastName': args.nachname or '', 'organization': job['company'],
                  'jobTitle': args.funktion, 'department': args.abteilung}
        phones = [{'label': label, 'value': number} for label, numbers in
                  [('work', args.telefon), ('mobile', args.mobil), ('work fax', args.fax)]
                  for number in dict.fromkeys(numbers)]
        address = {k: v for k, v in [('street', args.strasse), ('city', args.stadt), ('state', args.region),
                                      ('zip', args.plz), ('country', args.land)] if v}
        return {'kind': 'contact', 'email': args.email.strip(),
                'fields': {k: v.strip() for k, v in fields.items() if v}, 'phones': phones,
                'address': address, 'website': args.website}
    title = f"{job['company']}, {job['role']}, {args.runde}"
    return {'kind': 'event', 'calendar': _single(args.kalender, 'Zielkalender'),
            'uid': _uid(w, 'termin:' + job['id'] + ':' + args.runde),
            'title': ('Vormerkung · ' if args.vormerkung else '') + title,
            'start': datetime.fromisoformat(args.start).astimezone(timezone.utc).isoformat(),
            'end': datetime.fromisoformat(args.ende).astimezone(timezone.utc).isoformat(),
            'description': args.quelle.strip(), 'location': (args.ort or '').strip(),
            'status': 'tentative' if args.vormerkung else 'confirmed'}


def sync_native(args, w, job, path):
    request = native_request(args, w, job)
    statefile = w.path(path.with_suffix('.native.json'))
    state = read(statefile) if statefile.exists() else {}
    payload = dict(request, previous=state.get('native_id'), update=args.aktualisieren)
    if state.get('calendar') and state['calendar'] != request.get('calendar'):
        raise ValueError('Bereits einem anderen Kalender zugeordnet. Bestehenden Eintrag zuerst prüfen.')
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    if state.get('pending') and state['pending'] != fingerprint:
        raise ValueError('Frühere Übernahme offen. Zuerst den ursprünglichen Aufruf wiederholen und den Bestand prüfen.')
    state.update(pending=fingerprint, calendar=request.get('calendar'))
    write(statefile, state)
    adapter = Path(__file__).resolve().parents[1] / 'resources' / 'native-termine.js'
    child = subprocess.run(['osascript', '-l', 'JavaScript', str(adapter)], input=json.dumps(payload), text=True,
                           capture_output=True, timeout=120)
    if child.returncode:
        raise ValueError('Native Übernahme offen. ' + child.stderr.strip()[:600])
    reply = json.loads(child.stdout)
    if not isinstance(reply, dict) or reply.get('verified') is not True or not isinstance(reply.get('id'), str) or not reply['id']:
        raise ValueError('Rücklesen fehlgeschlagen. Ursprüngliche Übernahme vor einem neuen Eintrag prüfen.')
    write(statefile, {'native_id': reply['id'], 'calendar': request.get('calendar'), 'fingerprint': fingerprint,
                      'verified_at': datetime.now(timezone.utc).isoformat()})


def run(args, workspace):
    if args.command not in ('kontakt', 'termin', 'gespraechsmappe'):
        return False
    if getattr(args, 'mac', False):
        if sys.platform != 'darwin':
            raise ValueError('Die native Übernahme benötigt macOS. VCF und ICS sind plattformübergreifend verfügbar.')
        if args.command == 'termin' and not args.kalender:
            raise ValueError('--mac braucht einen ausdrücklich benannten --kalender.')
    elif getattr(args, 'kalender', None):
        raise ValueError('--kalender gilt für die native Übernahme mit --mac.')
    with workspace.locked():
        job = workspace.job(workspace.jobs(), args.id)
        if args.command == 'gespraechsmappe':
            for path in folder_for_round(workspace, job, args):
                print(path)
            return True
        path = contact(workspace, job, args) if args.command == 'kontakt' else meeting(workspace, job, args)
        if args.mac:
            sync_native(args, workspace, job, path)
    print(path)
    if args.mac:
        print('Nativer Datensatz zurückgelesen und zugeordnet.')
    if args.oeffnen:
        if sys.platform == 'win32':
            os.startfile(str(path))
        else:
            launcher = 'open' if sys.platform == 'darwin' else 'xdg-open'
            if subprocess.run([launcher, str(path)]).returncode:
                raise ValueError('Datei gespeichert. Öffne sie mit deinem Kalender- oder Kontakteprogramm.')
    return True
