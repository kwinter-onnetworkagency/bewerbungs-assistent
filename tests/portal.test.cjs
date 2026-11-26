'use strict';
const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const {createServer} = require('node:http');
const {createHash} = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');
const {prepare} = require('../resources/portal.cjs');

let browser, server, origin;
const submissions = [], uploads = [];
const form = `<!doctype html><form action="/send" method="POST">
  <label>Vorname <input id="vorname"></label>
  <input type="file" id="slot"><input type="file" id="multi" multiple>
  <button id="abschluss">Bewerbung senden</button><div id="quittungen"></div></form>
  <script>
  const form = document.querySelector('form');
  document.querySelector('#vorname').oninput = () => form.requestSubmit();
  document.querySelector('#slot').onchange = async event => {
    const file = event.target.files[0];
    const response = await fetch('/upload?name=' + encodeURIComponent(file.name), {method:'POST',body:file});
    if (response.ok) {
      const label = document.createElement('span');
      label.className = 'quittung';
      label.textContent = file.name;
      document.querySelector('#quittungen').append(label);
    }
  };
  </script>`;

before(async () => {
  server = createServer(async (req, res) => {
    const address = new URL(req.url, 'http://localhost');
    if (address.pathname === '/send') submissions.push(req.method);
    if (address.pathname === '/upload') {
      const parts = [];
      for await (const chunk of req) parts.push(chunk);
      const name = address.searchParams.get('name');
      uploads.push({name, data:Buffer.concat(parts).toString()});
      res.writeHead(name === 'Abgelehnt.pdf' ? 422 : 200).end();
      return;
    }
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(address.pathname === '/rahmenstelle' ? '<input id="hauptseite"><iframe src="/eingebettet"></iframe>' : form);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = 'http://127.0.0.1:' + server.address().port;
  browser = await chromium.launch({headless:true, executablePath:process.env.PORTAL_CHROMIUM_EXECUTABLE});
});

after(async () => {
  if (browser) await browser.close();
  if (server) {
    server.closeAllConnections();
    await new Promise(resolve=>server.close(resolve));
  }
});

async function setup(t) {
  uploads.length = 0;
  submissions.length = 0;
  const output = fs.mkdtempSync(path.join(os.tmpdir(),'portal-test-'));
  t.after(()=>fs.rmSync(output, {recursive:true, force:true}));
  const context = await browser.newContext();
  context.setDefaultTimeout(2000);
  t.after(()=>context.close());
  const config = {url:origin+'/direkt', fields:[], personal:{}, uploads:[], mode:'ausfuellen', output};
  const file = name => {
    const data = '%PDF-1.4 Testdatei ' + name;
    const location = path.join(output, name);
    fs.writeFileSync(location, data);
    return {name, path:location, sha256:createHash('sha256').update(data).digest('hex')};
  };
  const read = name => JSON.parse(fs.readFileSync(path.join(output,name),'utf8'));
  return {config, file, context, read};
}

test('Feldbericht erfasst Hauptseite und eingebettetes Formular ohne Feldwerte', async t => {
  const {config, context, read} = await setup(t);
  Object.assign(config, {url:origin+'/rahmenstelle', mode:'erkunden'});
  await prepare(config,context);
  const census = read('felder.json');
  assert.equal(census.fields[0].id,'hauptseite');
  const embedded = census.frames.find(f=>f.url === origin+'/eingebettet');
  assert.ok(embedded.fields.some(f=>f.id === 'vorname' && f.vorschlag === 'vorname' && !('value' in f)));
  assert.equal(submissions.length,0);
});

test('Einzelquittungen im richtigen Frame bestätigen Namen und die übertragenen Bytes', async t => {
  const {config, context, file, read} = await setup(t);
  const names = ['Vita (DE)+.pdf', 'Zeugnis.pdf'];
  Object.assign(config,{url:origin+'/rahmenstelle', frame:origin+'/eingebettet', personal:{vorname:'Test'},
    uploads:[{selector:'#slot', receipt:'.quittung', files:names.map(file)}]});
  const page = await prepare(config,context);
  assert.equal(await page.frameLocator('iframe').locator('#vorname').inputValue(),'Test');
  assert.equal(await page.locator('#hauptseite').inputValue(),'');
  assert.deepEqual(uploads, names.map(name=>({name, data:'%PDF-1.4 Testdatei '+name})));
  assert.deepEqual(read('uploads.json').dateien.map(x=>x.status), names.map(()=>'Datei im Portal quittiert'));
  assert.deepEqual(submissions, []);
});

test('Mehrfachfeld ohne Quittung hält die Auswahl offen und stoppt vor dem Versand', async t => {
  const {config, context, file, read} = await setup(t);
  const names = ['A.pdf','B.pdf'];
  Object.assign(config,{personal:{vorname:'Beispiel'}, uploads:[{selector:'#multi', files:names.map(file)}]});
  const page = await prepare(config, context);
  assert.deepEqual(await page.locator('#multi').evaluate(n=>Array.from(n.files,f=>f.name)), names);
  assert.deepEqual(read('uploads.json').dateien.map(x=>x.status), names.map(()=>'nur ausgewählt, Upload offen'));
  assert.equal(await page.locator('#vorname').inputValue(),'Beispiel');
  assert.deepEqual(submissions, []);
});

test('Abgewiesene zweite Datei lässt den ersten Beleg und die offene dritte Datei erhalten', async t => {
  const {config, context, file, read} = await setup(t);
  const names = ['Erste.pdf','Abgelehnt.pdf','Dritte.pdf'];
  config.uploads = [{selector:'#slot', receipt:'.quittung', files:names.map(file)}];
  await assert.rejects(prepare(config, context), /Timeout/);
  assert.deepEqual(read('uploads.json').dateien.map(x=>x.status),
    ['Datei im Portal quittiert','Auswahl begonnen, Upload offen','offen']);
  assert.deepEqual(uploads.map(x=>x.name),names.slice(0,2));
  assert.deepEqual(submissions, []);
});

test('Abweichender Hash stoppt vor der ersten Auswahl und ein belegtes Feld bleibt unangetastet', async t => {
  const {config, context, file, read} = await setup(t);
  const first = file('Eins.pdf'), second = file('Zwei.pdf');
  config.uploads = [{selector:'#slot', receipt:'.quittung', files:[first, second]}];
  fs.appendFileSync(second.path, 'geänderte Fassung');
  await assert.rejects(prepare(config,context), /wurde geändert/);
  assert.deepEqual(uploads,[]);
  assert.deepEqual(read('uploads.json').dateien.map(x=>x.status),['offen','offen']);
  const other = await setup(t);
  const oldFile = other.file('Vorhanden.pdf');
  other.config.uploads = [{selector:'#slot', receipt:'.quittung', files:[oldFile]}];
  await other.context.route('**/direkt', route=>route.fulfill({
    contentType:'text/html', body:form.replace('<div id="quittungen">','<div id="quittungen"><span class="quittung">Vorhanden.pdf</span>')
  }));
  await assert.rejects(prepare(other.config,other.context), /bereits vorhanden/);
  assert.deepEqual(uploads,[]);
  assert.deepEqual(submissions,[]);
});
