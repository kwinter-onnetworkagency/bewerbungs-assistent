import argparse
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
import zipfile

from bewerbung.core import Workspace, write
from bewerbung.documents import W, convert_pdf, docx, prepare, render, save, save_fitted
from bewerbung.setup import initialize
from bewerbung.unterlagentext import check_file, check_text, register, run


class UnterlagenTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        root = initialize(self.root / 'privat', 'Beispielperson', ['Planung'], 'Modellstadt', 'codex', False)
        self.w = Workspace(root)
        profile = self.w.profile()
        profile['facts'] = [
            {'id': 'berichte', 'kind': 'achievement', 'text': 'Berichte erstellt.', 'source': 'eigene Angabe',
             'keywords': ['Berichte'], 'translations': {'en': 'Prepared reports.'}},
            {'id': 'plaene', 'kind': 'achievement', 'text': 'Planung vereinheitlicht.', 'source': 'eigene Angabe',
             'keywords': ['Planung'], 'translations': {'en': 'Standardised planning.'}},
            {'id': 'seminar', 'kind': 'education', 'text': 'Seminar abgeschlossen.', 'source': 'eigene Angabe',
             'translations': {'en': 'Completed a course.'}},
        ]
        profile['preferences'] = {'salary': 'privates Gehaltsziel', 'contact': 'kontakt@example.org'}
        write(self.w.path('profil.json'), profile)
        job, _ = self.w.add('Musterbetrieb', 'Planung', 'https://example.org/stellen/1', 'Wir suchen Erfahrung in Planung.', 'A15')
        self.jid = job['id']
        self.w.draft(self.jid, 'Guten Tag,\n\nich freue mich über den Kontakt.\n\nFreundliche Grüße\nBeispielperson', ['plaene'])
        parser = argparse.ArgumentParser()
        register(parser.add_subparsers(dest='command'))
        self.parse = parser.parse_args

    def test_cv_localization_selection_and_privacy(self):
        de = prepare(self.w, 'lebenslauf', job_id=self.jid)
        en = prepare(self.w, 'lebenslauf', job_id=self.jid, language='en', fact_ids=['seminar', 'plaene'])
        self.assertLess(de.paragraphs.index('Planung vereinheitlicht.'), de.paragraphs.index('Berichte erstellt.'))
        self.assertIn('Target position: Planung, Musterbetrieb', en.paragraphs)
        self.assertIn('Completed a course.', en.paragraphs)
        self.assertIn('Education', en.paragraphs)
        self.assertNotIn('Prepared reports.', en.paragraphs)
        self.assertFalse(any('privates' in p or 'eigene Angabe' in p for p in en.paragraphs))
        for ids in [['fehlt'], ['plaene', 'plaene']]:
            with self.assertRaises(ValueError):
                prepare(self.w, 'lebenslauf', fact_ids=ids)
        profile = self.w.profile()
        profile['facts'][0].pop('translations')
        write(self.w.path('profil.json'), profile)
        with self.assertRaisesRegex(ValueError, 'bestätigte Fassung'):
            prepare(self.w, 'lebenslauf', language='en')
        profile['facts'][0].update(language='en', text='Produced reports.')
        write(self.w.path('profil.json'), profile)
        self.assertIn('Produced reports.', prepare(self.w, 'lebenslauf', language='en').paragraphs)

    def test_letter_preserves_source_and_checks_references(self):
        letter = prepare(self.w, 'anschreiben', job_id=self.jid, letter_date='2026-05-22', recipient=['Personalteam'])
        self.assertIn('22.05.2026', letter.paragraphs)
        self.assertIn('Personalteam', letter.paragraphs)
        self.assertIn('Bewerbung als Planung (Referenz: A15)', letter.paragraphs)
        self.assertIn('ich freue mich über den Kontakt.', letter.paragraphs)
        self.assertEqual(letter.fact_ids, ['plaene'])
        with self.assertRaisesRegex(ValueError, 'Briefdatum'):
            prepare(self.w, 'anschreiben', job_id=self.jid, letter_date='2026-02-31')
        profile = self.w.profile()
        profile['facts'] = profile['facts'][:1]
        write(self.w.path('profil.json'), profile)
        with self.assertRaisesRegex(ValueError, 'Faktenverweise'):
            prepare(self.w, 'anschreiben', job_id=self.jid)

    def test_docx_roundtrip_structure_and_failures(self):
        document = prepare(self.w, 'lebenslauf')
        path = render(self.w)
        original = path.read_bytes()
        self.assertIn('Abschnittsüberschriften', check_file(path, document))
        self.assertEqual(render(self.w).stem, 'lebenslauf-v2')
        without_headings = self.root / 'ohne.docx'
        docx(without_headings, document.paragraphs)
        with self.assertRaisesRegex(ValueError, 'gegliedert'):
            check_file(without_headings, document)
        with self.assertRaisesRegex(ValueError, 'existiert'):
            docx(path, ['Neu'])
        self.assertEqual(original, path.read_bytes())
        wrong = self.root / 'anders.docx'
        docx(wrong, document.paragraphs[::-1], headings=document.headings)
        with self.assertRaisesRegex(ValueError, 'Lesereihenfolge'):
            check_file(wrong, document)
        damaged = self.root / 'defekt.docx'
        damaged.write_bytes(b'kein zip')
        with self.assertRaisesRegex(ValueError, 'nicht lesbar'):
            check_file(damaged, document)
        with self.assertRaises(ValueError):
            docx(self.root / 'ungueltig.docx', ['AB\x01CD'])
        self.assertFalse((self.root / 'ungueltig.docx').exists())

    def test_job_metadata_must_match_even_when_content_does(self):
        document = prepare(self.w, 'lebenslauf', job_id=self.jid)
        other = self.root / 'vertauscht.docx'
        docx(other, document.paragraphs, headings=document.headings, subject='andere-stelle')
        with self.assertRaisesRegex(ValueError, 'Stellen-ID'):
            check_file(other, document)
        with zipfile.ZipFile(save(self.w, document)) as package:
            self.assertNotIn('privates Gehaltsziel', ''.join(package.read(n).decode() for n in package.namelist()))

    def test_cli_text_checks_and_ats(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run(self.parse(['anschreiben', self.jid]), self.w)
            run(self.parse(['textpruefung', 'anschreiben', '--stelle', self.jid]), self.w)
            run(self.parse(['ats-pruefung', 'anschreiben', f'dokumente/{self.jid}-anschreiben.docx', '--stelle', self.jid]), self.w)
        self.assertIn('ATS-Lesetest bestanden', output.getvalue())
        self.assertIn('Verwendete Fakten-IDs: plaene', output.getvalue())
        self.assertFalse(run(argparse.Namespace(command='bericht'), self.w))
        for language, bad in [('de', 'Guten Tag,\nIch arbeite dort.'), ('en', 'Dear team,\ni work here.'),
                              ('de', 'Guten Tag,\nmein Name ist {{VORNAME}}.'), ('de', 'Unsichtbar\u200b hier')]:
            self.w.draft(self.jid, bad, ['plaene'])
            document = prepare(self.w, 'anschreiben', job_id=self.jid, language=language)
            with self.assertRaisesRegex(ValueError, 'Textprüfung'):
                check_text(document)
        self.w.draft(self.jid, 'Dear team,\nThank you for your time.', ['plaene'])
        check_text(prepare(self.w, 'anschreiben', job_id=self.jid, language='en'))
        self.w.draft(self.jid, 'Guten Tag,\nIhre Ausschreibung interessiert mich.', ['plaene'])
        check_text(prepare(self.w, 'anschreiben', job_id=self.jid))

    def test_pdf_rejects_wrong_page_format_subject_or_flattened_heading(self):
        document = prepare(self.w, 'lebenslauf', job_id=self.jid)
        path = self.root / 'pruefling.pdf'
        path.write_bytes(b'%PDF-')
        text = '\n'.join(document.paragraphs) + '\n\f'
        info = f'Page   1 size: 595.28 x 841.89 pts (A4)\nSubject: {self.jid}\n'
        heading = document.paragraphs[min(document.headings)]
        for body, metadata, error in [(text, info.replace('595.28', '700'), 'Seitenformat'),
                                      (text, info.replace(self.jid, 'falsch'), 'Stellen-ID'),
                                      (text.replace(heading + '\n', heading + ' '), info, 'Überschrift|überschrift'),
                                      (text.replace(heading + '\n', heading + '\n\f'), info, 'isoliert')]:
            processes = [subprocess.CompletedProcess([], 0, body.encode()), subprocess.CompletedProcess([], 0, metadata)]
            with (patch('bewerbung.unterlagentext.shutil.which', return_value='lokal'),
                  patch('bewerbung.unterlagentext.subprocess.run', side_effect=processes),
                  self.assertRaisesRegex(ValueError, error)):
                check_file(path, document)

    def test_station_pagination_and_profile_sections(self):
        profile = self.w.profile()
        profile['facts'].extend([
            {'id': 'station', 'kind': 'experience', 'text': 'Planung, Musterbetrieb\n2022 bis 2024\nBerichte geplant.',
             'source': 'Eigene Notiz'},
            {'id': 'amt', 'kind': 'volunteering', 'text': 'Veranstaltung betreut.', 'source': 'Eigene Notiz'},
        ])
        write(self.w.path('profil.json'), profile)
        doc = prepare(self.w, 'lebenslauf', page_two='amt', portfolio='https://example.org/portfolio')
        with zipfile.ZipFile(save(self.w, doc)) as z:
            root = ET.fromstring(z.read('word/document.xml'))
        paras = root.findall(f'.//{{{W}}}p')
        pins = [p.find(f'{{{W}}}pPr/{{{W}}}keepNext') is not None for p in paras]
        index = doc.paragraphs.index('Planung, Musterbetrieb')
        self.assertEqual(pins[index:index+3], [True, True, False])
        self.assertEqual(doc.paragraphs[doc.page_break], 'Ehrenamt')
        self.assertIn('Portfolio: https://example.org/portfolio', doc.paragraphs)
        with self.assertRaisesRegex(ValueError, 'gewählten Fassung'):
            prepare(self.w, 'lebenslauf', fact_ids=['plaene'], page_two='amt')
        with self.assertRaisesRegex(ValueError, 'Design'):
            prepare(self.w, 'lebenslauf', photo='foto.png')
        with self.assertRaisesRegex(ValueError, 'PNG- oder JPEG'):
            prepare(self.w, 'lebenslauf', layout='design', photo='fehlt.png')
        with self.assertRaisesRegex(ValueError, 'Arbeitsordner'):
            prepare(self.w, 'lebenslauf', layout='design', photo='../fremd.png')

    @unittest.skipUnless(all(shutil.which(x) for x in ('magick', 'soffice', 'pdftotext', 'pdfimages', 'pdfinfo')),
                         'Bildaufbereitung und PDF-Werkzeuge optional')
    def test_design_photo_signature_and_two_pdf_pages(self):
        source = self.w.path('unterlagen', 'beispiel.png')
        subprocess.run(['magick', '-size', '50x40', 'xc:gray', '-set', 'comment', 'PRIVATE-BILDNOTIZ', str(source)], check=True)
        before = source.read_bytes()
        self.assertIn(b'PRIVATE-BILDNOTIZ', before)
        args = ['lebenslauf', '--sprache', 'en', '--layout', 'design', '--foto', 'unterlagen/beispiel.png',
                '--seite-2-ab', 'seminar', '--einpassen']
        with contextlib.redirect_stdout(io.StringIO()):
            run(self.parse(args), self.w)
        path = self.w.path('dokumente', 'lebenslauf-en-design.docx')
        doc = prepare(self.w, 'lebenslauf', language='en', layout='design', photo='unterlagen/beispiel.png', page_two='seminar')
        with zipfile.ZipFile(path) as z:
            self.assertNotIn(b'PRIVATE-BILDNOTIZ', z.read('word/media/image.png'))
        self.assertIn('A4', check_file(path, doc))
        self.assertIn('2 Seite(n)', check_file(path.with_suffix('.pdf'), doc))
        # Gleiches Design und Text bei fehlendem Foto darf die Foto-Prüfung nicht bestehen.
        plain = prepare(self.w, 'lebenslauf', language='en', layout='design', page_two='seminar')
        with self.assertRaisesRegex(ValueError, 'PDF-Bild'):
            check_file(convert_pdf(save(self.w, plain)), doc)
        self.w.draft(self.jid, 'Dear team,\nThank you for your time.\nBest regards,', ['plaene'])
        letter = prepare(self.w, 'anschreiben', job_id=self.jid, layout='design', language='en', signature=source, letter_date='2026-06-15')
        self.assertEqual(letter.paragraphs[-1], 'Beispielperson')
        signed, pages, _ = save_fitted(self.w, letter)
        self.assertEqual(pages, 1)
        self.assertIn('A4', check_file(signed, letter))
        self.assertIn('1 Seite(n)', check_file(signed.with_suffix('.pdf'), letter))
        self.assertEqual(before, source.read_bytes())

    def test_fitting_retries_compact_and_preserves_old_documents(self):
        doc = prepare(self.w, 'lebenslauf')
        initial = save(self.w, doc)
        original = initial.read_bytes()
        def fake_pdf(path):
            pdf = path.with_suffix('.pdf')
            pdf.write_bytes(b'%PDF-test')
            return pdf
        infos = [subprocess.CompletedProcess([], 0, 'Pages: 3'), subprocess.CompletedProcess([], 0, 'Pages: 2')]
        with (patch('bewerbung.documents.convert_pdf', side_effect=fake_pdf),
              patch('bewerbung.documents.shutil.which', return_value='pdfinfo'),
              patch('bewerbung.documents.subprocess.run', side_effect=infos)):
            fitted, pages, compact = save_fitted(self.w, doc)
        self.assertEqual((pages, compact), (2, True))
        self.assertEqual(initial.read_bytes(), original)
        with zipfile.ZipFile(fitted) as z:
            self.assertIn(b'<w:sz w:val="21"', z.read('word/document.xml'))
        files = set(initial.parent.iterdir())
        with (patch('bewerbung.documents.convert_pdf', side_effect=fake_pdf),
              patch('bewerbung.documents.shutil.which', return_value='pdfinfo'),
              patch('bewerbung.documents.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'Pages: 3')),
              self.assertRaisesRegex(ValueError, 'auch kompakt')):
            save_fitted(self.w, doc)
        self.assertEqual(files, set(initial.parent.iterdir()))

    @unittest.skipUnless(shutil.which('soffice') and shutil.which('pdftotext') and shutil.which('pdfinfo'), 'LibreOffice und Poppler optional')
    def test_real_pdf_reads_selected_content_in_order(self):
        letter = prepare(self.w, 'anschreiben', job_id=self.jid)
        path = convert_pdf(save(self.w, letter))
        self.assertIn('1 Seite(n)', check_file(path, letter))
        cv = prepare(self.w, 'lebenslauf', job_id=self.jid, language='en', page_two='seminar')
        self.assertIn('2 Seite(n)', check_file(convert_pdf(save(self.w, cv)), cv))
        with self.assertRaisesRegex(ValueError, 'Lesereihenfolge'):
            check_file(path, cv)
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'existiert'):
            convert_pdf(path.with_suffix('.docx'))
        self.assertEqual(original, path.read_bytes())
        with patch('bewerbung.unterlagentext.shutil.which', return_value=None), self.assertRaisesRegex(ValueError, 'Poppler'):
            check_file(path, letter)

    @unittest.skipUnless(shutil.which('soffice') and shutil.which('pdftotext') and shutil.which('pdfinfo'), 'LibreOffice und Poppler optional')
    def test_pdf_page_budget(self):
        self.w.draft(self.jid, '\n'.join('Längerer bestätigter Text.' for _ in range(120)), ['plaene'])
        letter = prepare(self.w, 'anschreiben', job_id=self.jid)
        with self.assertRaisesRegex(ValueError, 'maximal 1'):
            check_file(convert_pdf(save(self.w, letter)), letter)


if __name__ == '__main__':
    unittest.main()
