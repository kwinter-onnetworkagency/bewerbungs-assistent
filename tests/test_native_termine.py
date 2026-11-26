import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bewerbung import termine
from bewerbung.core import Workspace, read, write


ADAPTER = Path(termine.__file__).resolve().parents[1] / 'resources' / 'native-termine.js'


class NativeTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        write(self.root / 'workspace.json', {'schema_version': 1, 'created_at': 'Test'})
        write(self.root / 'bewerbungen.json', [])
        self.w = Workspace(self.root)
        self.jid = self.w.add('Beispielbetrieb', 'Disposition', 'https://example.org/a', 'Beispielaufgaben')[0]['id']
        self.parser = argparse.ArgumentParser()
        termine.register(self.parser.add_subparsers(dest='command'))
        self.event = ['termin', self.jid, '--runde', 'fachrunde', '--quelle', 'Terminvorschlag', '--vormerkung',
                      '--start', '2027-10-31T02:30+02:00', '--ende', '2027-10-31T02:30+01:00',
                      '--zeitzone', 'Europe/Berlin', '--mac', '--kalender', 'Bewerbungen']

    def call(self, args, runner):
        requests = []
        def mock(cmd, **kwargs):
            self.assertEqual(cmd[:3], ['osascript', '-l', 'JavaScript'])
            requests.append(json.loads(kwargs['input']))
            return runner(requests[-1])
        with patch('bewerbung.termine.sys.platform', 'darwin'), patch('bewerbung.termine.subprocess.run', side_effect=mock):
            with redirect_stdout(StringIO()):
                termine.run(self.parser.parse_args(args), self.w)
        return requests

    @staticmethod
    def verified(record):
        return subprocess.CompletedProcess([], 0, '{"verified": true, "id": "app-id"}', '')

    def test_vormerkung_timezone_and_native_readback(self):
        first, = self.call(self.event, self.verified)
        self.assertEqual((first['start'], first['end']), ('2027-10-31T00:30:00+00:00', '2027-10-31T01:30:00+00:00'))
        self.assertEqual((first['status'], first['calendar'], first['previous']), ('tentative', 'Bewerbungen', None))
        again, = self.call(self.event, self.verified)
        self.assertEqual(again['previous'], 'app-id')
        self.assertNotIn('attendee', again)
        ics = next(self.root.rglob('*.ics')).read_text()
        self.assertIn('STATUS:TENTATIVE', ics)
        self.assertNotIn('ATTENDEE', ics)
        self.assertEqual(self.w.jobs()[0]['status'], 'recherche')

    def test_contacts_have_multiple_phones_fax_department_and_address(self):
        args = ['kontakt', self.jid, '--name', 'Probekontakt', '--email', 'test@example.org', '--mac',
                '--telefon', '123', '--telefon', '456', '--mobil', '789', '--fax', '100', '--abteilung', 'Team A',
                '--funktion', 'Koordination', '--stadt', 'Bonn', '--plz', '50000']
        q, = self.call(args, self.verified)
        self.assertEqual(q['fields']['department'], 'Team A')
        self.assertEqual([p['label'] for p in q['phones']], ['work', 'work', 'mobile', 'work fax'])
        self.assertEqual(q['address'], {'city': 'Bonn', 'zip': '50000'})
        vcard = next(self.root.rglob('*.vcf')).read_text()
        self.assertIn('ORG:Beispielbetrieb;Team A', vcard)
        self.assertIn('TEL;TYPE=fax;VALUE=text:100', vcard)

    def test_failed_readback_never_records_success_or_retargets_pending_work(self):
        with self.assertRaisesRegex(ValueError, 'Rücklesen'):
            self.call(self.event, lambda _: subprocess.CompletedProcess([], 0, '{"verified":false}', ''))
        state = read(next(self.root.rglob('*.native.json')))
        self.assertNotIn('verified_at', state)
        with self.assertRaisesRegex(ValueError, 'anderen Kalender'):
            self.call(self.event[:-1] + ['Anderer Kalender'], self.verified)
        self.call(self.event, self.verified)
        self.assertIn('verified_at', read(next(self.root.rglob('*.native.json'))))
        with self.assertRaisesRegex(ValueError, '--kalender'):
            self.call(self.event[:-2], self.verified)

    @unittest.skipUnless(shutil.which('node'), 'Node.js für simulierte Adapterprüfung')
    def test_js_adapter_duplicate_preflight_update_and_readback_use_in_memory_store(self):
        probe = r"""
const {synchronize}=require(process.argv[1]);
const assert=require('node:assert/strict');
const q={kind:'event',uid:'round',title:'Fachrunde',calendar:'Test',start:'2027-03-01T10:00Z',
         end:'2027-03-01T10:30Z',description:'Beleg',location:'',status:'tentative'};
const snapshot={id:'native',title:q.title,start:Date.parse(q.start),end:Date.parse(q.end),description:q.description,
 location:q.location,status:q.status,mark:q.uid,external:false};
let data=[],writes=0;
const store={find:()=>structuredClone(data),create(){writes++;data=[snapshot];return snapshot.id;},
 update(){writes++;data=[snapshot];return snapshot.id;}};
assert.deepEqual(synchronize(q,store),{id:'native',verified:true});
synchronize({...q,previous:'native'},store);assert.equal(writes,1);
data=[snapshot,snapshot];assert.throws(()=>synchronize(q,store),/Mehrere/);assert.equal(writes,1);
data=[{...snapshot,mark:'',title:'Ähnlicher Termin'}];assert.throws(()=>synchronize({...q,update:true},store),/Zuordnung/);
data=[{...snapshot,external:true}];assert.throws(()=>synchronize({...q,previous:'native',update:true},store),/Teilnehmenden/);
data=[{...snapshot,location:'alt'}];synchronize({...q,previous:'native',update:true},store);assert.equal(writes,2);
data=[];assert.throws(()=>synchronize({...q,previous:'missing'},store),/fehlt/);
assert.throws(()=>synchronize(q,{find(){return [];},create(){return 'id';}}),/Rücklesen/);
const c={kind:'contact',fields:{firstName:'Test',department:'Team'},email:'test@example.org',phones:[{label:'work fax',value:'123'}],address:{city:'Bonn'},website:''};
const contact={id:'cid',fields:c.fields,emails:['TEST@example.org'],phones:[{label:'_$!<WorkFAX>!$_',value:'123'}],addresses:[{city:'Bonn',country:'DE'}]};
const book={find:()=>[contact],create(){throw Error('unexpected');},update(){throw Error('unexpected');}};
assert.equal(synchronize(c,book).id,'cid');
assert.throws(()=>synchronize({...c,fields:{firstName:'Andere Person'},update:true},book),/Zuordnung/);
"""
        subprocess.run(['node', '-e', probe, str(ADAPTER)], check=True, capture_output=True, timeout=10)

    @unittest.skipUnless(sys.platform == 'darwin', 'AppleScript-Compiler nur unter macOS verfügbar')
    def test_jxa_compiles_without_accessing_calendar_or_contacts(self):
        subprocess.run(['/usr/bin/osacompile', '-l', 'JavaScript', '-o', str(self.root / 'adapter.scpt'), str(ADAPTER)],
                       check=True, capture_output=True, timeout=25)
