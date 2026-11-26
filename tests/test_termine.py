import argparse
import contextlib
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bewerbung.core import Workspace, write
from bewerbung.setup import initialize
from bewerbung.termine import register, run


class TermineTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)
        self.w = Workspace(initialize(self.path / 'privat', 'Beispielperson', [], '', 'codex', False))
        profile = self.w.profile()
        profile['facts'] = [{'id': 'projekt', 'text': 'Laborablauf dokumentiert.', 'source': 'Eigenes Protokoll'},
                            {'id': 'intern', 'text': 'Ausgeschlossener Fakt', 'source': 'Privat'}]
        write(self.w.path('profil.json'), profile)
        self.job, _ = self.w.add('Modellbetrieb', 'Laborplanung', 'https://example.org/jobs/labor', 'Analysiere Messreihen.')
        self.job_id = self.job['id']
        parser = argparse.ArgumentParser()
        register(parser.add_subparsers(dest='command'))
        self.parse = parser.parse_args
        self.when = ['termin', self.job_id, '--runde', 'fachrunde', '--quelle', 'Bestätigte Einladung',
                     '--start', '2027-10-31T02:30+02:00', '--ende', '2027-10-31T02:30+01:00']

    def call(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertTrue(run(self.parse(args), self.w))
        return [Path(line) for line in output.getvalue().splitlines()]

    def test_vcard_utf8_crlf_escape_and_repeat(self):
        args = ['kontakt', self.job_id, '--name', 'Ä' * 90 + ', Muster; \\', '--email', 'labor@example.org',
                '--funktion', 'Fachkontakt', '--telefon', '+49 000 000', '--vorname', 'Test',
                '--nachname', 'Beispiel', '--strasse', 'Musterweg 1', '--plz', '00000', '--stadt', 'Musterstadt']
        with patch('bewerbung.termine.subprocess.run') as launch:
            card, = self.call(args)
            blob = card.read_bytes()
            self.assertLessEqual(max(map(len, blob.split(b'\r\n'))), 75)
            self.assertNotIn(b'\n', blob.replace(b'\r\n', b''))
            for line in blob.split(b'\r\n'):
                line.decode()
            value = blob.replace(b'\r\n ', b'').decode()
            self.assertIn('BEGIN:VCARD\r\nVERSION:4.0', value)
            self.assertIn(r'\, Muster\; \\', value)
            self.assertIn('EMAIL:labor@example.org', value)
            self.assertIn('N:Beispiel;Test;;;', value)
            self.assertIn('ADR;TYPE=work:;;Musterweg 1;Musterstadt;;00000;', value)
            self.assertEqual(self.call(args), [card])
            self.assertEqual(card.read_bytes(), blob)
            launch.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'bereits vorhanden'):
            self.call([*args, '--funktion', 'Personalteam'])
        self.call([*args, '--funktion', 'Personalteam', '--aktualisieren'])
        self.assertIn(b'TITLE:Personalteam', card.read_bytes())
        with self.assertRaises(ValueError):
            self.call([*args, '--funktion', 'Team\nEMAIL:fremd@example.org'])
        with self.assertRaises(ValueError):
            self.call([*args, '--email', 'ungueltig'])

    def test_calendar_dst_uid_sequence_and_no_invitations(self):
        try:
            ZoneInfo('Europe/Berlin')
        except ZoneInfoNotFoundError:
            self.skipTest('IANA-Zeitzonendaten optional')
        args = [*self.when, '--zeitzone', 'Europe/Berlin', '--ort', 'Raum A, Platz 1']
        path, = self.call(args)
        data = path.read_text()
        self.assertIn('DTSTART:20271031T003000Z', data)
        self.assertIn('DTEND:20271031T013000Z', data)
        self.assertIn(r'LOCATION:Raum A\, Platz 1', data)
        self.assertIn('CLASS:PRIVATE', data)
        for forbidden in ('ATTENDEE', 'ORGANIZER', 'METHOD:REQUEST'):
            self.assertNotIn(forbidden, data)
        uid = next(line for line in data.splitlines() if line.startswith('UID:'))
        self.assertEqual(self.call(args), [path])
        self.assertEqual(path.read_text(), data)
        newer = [*args, '--ende', '2027-10-31T03:00+01:00']
        with self.assertRaisesRegex(ValueError, 'aktualisieren'):
            self.call(newer)
        self.call([*newer, '--aktualisieren'])
        self.assertIn('SEQUENCE:1', path.read_text())
        self.assertIn(uid, path.read_text())
        for key, value in [('--start', '2027-03-28T02:30+01:00'), ('--start', '2027-10-31T04:00+01:00'),
                           ('--ende', '2027-10-31T02:30'), ('--zeitzone', 'Ungültig/Ort')]:
            with self.assertRaises(ValueError):
                self.call([*args, key, value])
        self.assertEqual(self.w.job(self.w.jobs(), self.job_id)['status'], 'recherche')

    def test_round_notes_current_versions_sources_and_originals(self):
        proof = self.path / 'beleg.txt'
        proof.write_text('Inhalt der vertraulichen Originalnachricht')
        self.w.add_note(self.job_id, 'gespraech', 'Fachfragen', 'Alte Frage.')
        self.w.add_note(self.job_id, 'gespraech', 'Fachfragen', 'Thema Messfehler.',
                        ['https://example.org/team'], evidence=proof)
        self.w.add_note(self.job_id, 'gespraech', 'Andere Runde', 'Nur für Leitungsgespräch.')
        args = ['gespraechsmappe', self.job_id, '--runde', 'fachrunde', '--fakt', 'projekt', '--notiz', 'Fachfragen']
        first, followup = self.call(args)
        content = first.read_text()
        for wanted in ('Offen.', 'https://example.org/team', 'Lokaler Beleg (SHA-256)', 'Analysiere Messreihen.',
                       'Thema Messfehler.', 'Laborablauf dokumentiert.', 'Eigenes Protokoll', '90 Sekunden'):
            self.assertIn(wanted, content)
        for absent in ('Inhalt der vertraulichen Originalnachricht', 'Alte Frage.', 'Nur für Leitungsgespräch.', 'Ausgeschlossener Fakt'):
            self.assertNotIn(absent, content)
        followup.write_text('Meine tatsächliche Nachbereitung.')
        self.assertEqual(self.call(args), [first, followup])
        self.call(self.when)
        changed, same = self.call(args)
        self.assertNotEqual(first, changed)
        self.assertEqual(first.read_text(), content)
        self.assertIn('Beginn: 31.10.2027 00:30 UTC', changed.read_text())
        self.assertEqual(same.read_text(), 'Meine tatsächliche Nachbereitung.')
        other, other_follow = self.call([*args, '--runde', 'erstkontakt'])
        self.assertNotEqual(other.parent, first.parent)
        self.assertNotIn('Meine tatsächliche Nachbereitung.', other_follow.read_text())
        original = next(self.w.path('belege').glob('*'))
        original.write_text('Manipuliert.')
        with self.assertRaisesRegex(ValueError, 'verändert'):
            self.call(args)

    def test_explicit_native_open_and_invalid_round(self):
        with patch('bewerbung.termine.sys.platform', 'darwin'), patch('bewerbung.termine.subprocess.run') as launch:
            launch.return_value.returncode = 0
            path, = self.call([*self.when, '--oeffnen'])
            launch.assert_called_once_with(['open', str(path)])
        with self.assertRaises(ValueError):
            self.call([*self.when, '--runde', '../fremd'])
        with self.assertRaises(ValueError):
            self.call(['gespraechsmappe', self.job_id, '--runde', 'test', '--fakt', 'fehlt'])
        with self.assertRaises(ValueError):
            self.call(['gespraechsmappe', self.job_id, '--runde', 'test', '--fakt', 'projekt', '--notiz', 'fehlend'])
        self.assertFalse(run(argparse.Namespace(command='pruefen'), self.w))


if __name__ == '__main__':
    unittest.main()
