'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { createRequire } = require('node:module');

const reportType = 'portal_vorbereitung';
const hints = {
  vorname: ['vorname','first name','given name'], nachname: ['nachname','familienname','last name','surname','family name'],
  email: ['email','e-mail','email address','e-mail-adresse','e-mail adresse'],
  telefon: ['telefon','telefonnummer','phone','phone number'], portfolio: ['portfolio','portfolio url'],
  linkedin: ['linkedin','linkedin url','linkedin profil'], ort: ['wohnort','current city'], plz: ['postleitzahl','plz','postal code'],
};
const autocompleteKeys = {'given-name':'vorname','family-name':'nachname',email:'email',tel:'telefon','address-level2':'ort','postal-code':'plz'};
function sourceRef(raw) {
  try {
    const uri = new URL(raw);
    const anchor = createHash('sha256').update(raw).digest('hex').slice(0,12);
    return /^(http|https):$/.test(uri.protocol) ? uri.origin + '/… #' + anchor : '(eingebetteter Inhalt)';
  } catch {return '(unbekannt)';}
}

async function discover(target) {
  const controls = target.locator('input:not([type=hidden]), textarea, select');
  const discovered = await controls.evaluateAll(nodes => nodes.map(n => ({
    selektor: (() => {
      const value = n.id ? '#'+CSS.escape(n.id) : n.name ? '[name='+CSS.escape(n.name)+']' : null;
      return value && n.ownerDocument.querySelectorAll(value).length === 1 ? value : null;
    })(),
    id: n.id, name: n.name, type: n.type, required: n.required,
    label: Array.from(n.labels || [], l => l.textContent.trim()).join(' ') || n.getAttribute('aria-label') || '',
    context: [n.getAttribute('aria-labelledby'), n.getAttribute('aria-label'),
      ...Array.from(n.closest('form')?.querySelectorAll('fieldset') || []).filter(f=>f.contains(n))
        .map(f=>f.querySelector(':scope > legend')?.textContent),
      n.closest('section')?.querySelector('h1,h2,h3,h4')?.textContent,
      ...Array.from((n.getAttribute('aria-labelledby') || '').split(/\s+/), id=>n.ownerDocument.getElementById(id)?.textContent),
      ...Array.from((function*(el){while(el){yield el;el=el.parentElement;}})(n), el=>el.id+' '+el.className)
    ].filter(Boolean).join(' '),
    autocomplete: n.autocomplete || '', accept: n.accept || '',
  })));
  for (const field of discovered) {
    const label = field.label.toLowerCase().trim().replace(/[ *:]+$/g,'').trim();
    const token = field.autocomplete.toLowerCase().trim();
    const otherPerson = /notfall|emergency|referen|referee|third.party|dritt|ansprechperson|ansprechpartner|contact.person|supervisor|manager.?contact/i;
    const byLabel = Object.keys(hints).find(k=>hints[k].includes(label));
    const byToken = autocompleteKeys[token];
    const excluded = otherPerson.test([field.label,field.context,field.id,field.name,token].join(' '));
    field.vorschlag = !excluded && (!label || byLabel) && !(byLabel && byToken && byLabel !== byToken)
      ? byLabel || byToken || null : null;
    delete field.context;
  }
  const counts = new Map();
  for (const field of discovered) if (field.vorschlag) counts.set(field.vorschlag,(counts.get(field.vorschlag) || 0)+1);
  for (const field of discovered) if (counts.get(field.vorschlag) > 1) field.vorschlag=null;
  return discovered;
}

function checkedFile(file) {
  const buffer = fs.readFileSync(file.path);
  if (createHash('sha256').update(buffer).digest('hex') !== file.sha256) {
    throw Error('Uploadfassung wurde geändert: ' + file.name);
  }
  return {name:file.name, mimeType:'application/pdf', buffer};
}

async function fillUploads(config, target, atJob) {
  if (!config.uploads.length) return;
  const report = {typ:reportType, dateien:[], hinweis:'Portalangaben betreffen einzelne Dateien. Die Einreichung prüfst du persönlich.'};
  const dest = path.join(config.output, 'uploads.json');
  const persist = () => {
    fs.writeFileSync(dest + '.tmp', JSON.stringify(report, null, 2), {mode:0o600});
    fs.renameSync(dest + '.tmp', dest);
  };
  const groups = config.uploads.map(group => {
    const entries = group.files.map(file => ({typ:reportType, name:file.name, sha256:file.sha256, feld:group.selector, status:'offen'}));
    report.dateien.push(...entries);
    return {group, entries};
  });
  persist();
  try {
    // Alle Gruppen vor der ersten Auswahl prüfen. Beim tatsächlichen Lesen erneut hashen.
    for (const {group} of groups) for (const file of group.files) checkedFile(file);
    for (const {group, entries} of groups) {
      atJob();
      const input = target.locator(group.selector);
      const slot = await input.evaluate(n => n instanceof HTMLInputElement && n.type === 'file'
        ? {multiple:n.multiple, occupied:n.files.length > 0} : null);
      if (!slot || slot.occupied) throw Error('Uploadfeld fehlt, ist unklar oder bereits belegt.');
      if (!group.receipt) {
        if (group.files.length > 1 && !slot.multiple) {
          throw Error('Einzeldateifeld mit mehreren Dateien: Quittungsselektor für die Einzeluploads angeben.');
        }
        const payloads = group.files.map(checkedFile);
        entries.forEach(e => { e.status = 'Auswahl begonnen, Upload offen'; });
        persist();
        await input.setInputFiles(payloads);
        atJob();
        entries.forEach(e => { e.status = 'nur ausgewählt, Upload offen'; });
        persist();
        console.log('Nur ausgewählt, Upload offen: ' + entries.map(e=>e.name).join(', '));
        continue;
      }
      for (const [index, file] of group.files.entries()) {
        atJob();
        const quoted = file.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const receipt = target.locator(group.receipt).filter({hasText:new RegExp('^\\s*' + quoted + '\\s*$')});
        if (await receipt.count()) throw Error('Quittung für ' + file.name + ' bereits vorhanden. Vor Wiederholung prüfen.');
        const payload = checkedFile(file);
        entries[index].status = 'Auswahl begonnen, Upload offen';
        persist();
        await input.setInputFiles(payload);
        await receipt.waitFor({state:'visible'});
        atJob();
        entries[index].status = 'Datei im Portal quittiert';
        persist();
      }
    }
  } catch (error) {
    report.fehler = 'Dateiauswahl oder Quittungsprüfung fehlgeschlagen. Vor Wiederholung persönlich prüfen.';
    persist();
    throw error;
  }
}

async function fillFields(config, target, atJob) {
  const completed = [];
  const logPath = path.join(config.output,'befuellte-felder.json');
  const persist = () => {
    fs.writeFileSync(logPath+'.tmp',JSON.stringify({typ:reportType,felder:completed},null,2),{mode:0o600});
    fs.renameSync(logPath+'.tmp',logPath);
  };
  const record = (selector, key) => {
    // Ein frei gewählter Selektor kann eigene Werte oder Adressen enthalten.
    const safe = /^[#.][a-zA-Z0-9_-]+$/.test(selector) || /^\[(?:id|name)=[a-zA-Z0-9_-]+\]$/.test(selector);
    completed.push({selektor:safe ? selector : 'sha256:'+createHash('sha256').update(selector).digest('hex'), schluessel:key});
    persist();
  };
  persist();
  for (const field of config.fields) {
    atJob();
    const input = target.locator(field.selector);
    if (await input.count() !== 1) throw Error('Bestätigter Selektor bezeichnet kein eindeutiges Formularfeld.');
    const previous = await input.inputValue();
    if (previous && previous !== field.value) throw Error('Bestätigtes Feld enthält bereits einen anderen Wert. Persönlich prüfen.');
    const type = await input.evaluate(n => n instanceof HTMLTextAreaElement ? 'textarea' :
      n instanceof HTMLSelectElement ? 'select' : n instanceof HTMLInputElement ? n.type : '');
    if (type === 'select') await input.selectOption(field.value);
    else if (['textarea','text','email','tel','number','url','date','search'].includes(type)) await input.fill(field.value);
    else throw Error('Dieses Feld erfordert manuelle Eingabe im Portal.');
    record(field.selector, field.key || 'explizit');
  }

}

async function prepare(config, context) {
  const page = await context.newPage();
  await page.goto(config.url, { waitUntil: 'domcontentloaded' });
  if (config.profile) {
    console.log('Persönlich anmelden, das richtige Formular öffnen und im Playwright-Inspektor Fortsetzen wählen.');
    await page.pause();
  }
  if (config.frame && !page.frames().some(f => f.url() === config.frame)) {
    await page.waitForEvent('framenavigated', {predicate:f=>f.url() === config.frame});
  }
  const candidates = page.frames().filter(f=>f !== page.mainFrame() && f.url() === config.frame);
  if (config.frame && candidates.length !== 1) throw Error('Geprüfter Formularrahmen fehlt oder ist mehrdeutig.');
  const target = config.frame ? candidates[0] : page;
  // Redirects may lead to a job index, a login, or another vacancy on the same host.
  const destination = new URL(config.url);
  const atJob = () => {
    if (config.frame && target.url() !== config.frame) throw Error("Formularrahmen hat gewechselt.");
    const actual = new URL(page.url());
    if (actual.origin !== destination.origin || actual.pathname !== destination.pathname ||
        actual.search !== destination.search || actual.hash !== destination.hash)
      throw Error('Weiterleitung: die endgültige Formularadresse und die Stelle zuerst im Portalprofil prüfen.');
  };
  const discovered = await discover(target);
  const frames = [];
  if (config.mode === 'erkunden') {
    for (const frame of page.frames().filter(f => f !== page.mainFrame())) {
      try { frames.push({url:sourceRef(frame.url()), fields:await discover(frame)}); }
      catch { frames.push({url:sourceRef(frame.url()), hinweis:'Rahmen beim Lesen nicht verfügbar.'}); }
    }
  }
  fs.writeFileSync(path.join(config.output, 'felder.json'),
    JSON.stringify({typ:reportType,url:sourceRef(page.url()), rahmen_url:config.frame ? sourceRef(config.frame) : null, fields:discovered, frames}, null, 2),
    {flag:'wx', mode:0o600});
  if (config.mode === 'ausfuellen') {
    atJob();
    const guard = await target.evaluateHandle(() => {
      const block = e => { e.preventDefault(); e.stopImmediatePropagation(); };
      document.addEventListener('submit', block, true);
      const native = HTMLFormElement.prototype.submit;
      HTMLFormElement.prototype.submit = function() {};
      return () => {
        document.removeEventListener('submit', block, true);
        HTMLFormElement.prototype.submit = native;
      };
    });
    try {
      await fillFields(config, target, atJob);
      await fillUploads(config, target, atJob);
      atJob();
    } finally {
      await guard.evaluate(restore=>restore()).catch(()=>{});
      await guard.dispose();
    }
  }
  const screenshot = path.join(config.output,'vorschau.png');
  fs.closeSync(fs.openSync(screenshot,'wx',0o600));
  await page.screenshot({path:screenshot, fullPage:true});
  fs.chmodSync(screenshot,0o600);
  return page;
}

async function main() {
  const config = JSON.parse(fs.readFileSync(0, 'utf8'));
  let chromium;
  try { ({chromium} = createRequire(path.join(process.cwd(),'portal-local.cjs'))('playwright')); }
  catch { throw Error('Im persönlichen Ordner Playwright installieren. Siehe docs/PORTAL.md.'); }
  const browser = config.profile ? null : await chromium.launch({headless:config.mode === 'erkunden'});
  const context = browser ? await browser.newContext() : await chromium.launchPersistentContext(config.profile,{headless:false});
  try {
    const page = await prepare(config,context);
    if (config.mode === 'ausfuellen') {
      console.log('Das Formular ist zur persönlichen Prüfung geöffnet. Nach der Prüfung das Browserfenster schließen.');
      await page.waitForEvent('close', {timeout:0}).catch(()=>{});
    }
  } finally {await context.close(); if(browser)await browser.close();}
}
module.exports = {prepare};
if(require.main === module) main().catch(()=>{console.error('Portalvorbereitung fehlgeschlagen. Feldbericht, Browserinstallation und Portalzustand prüfen.');process.exitCode=1;});
