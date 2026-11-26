'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const { createRequire } = require('node:module');

const hints = {
  vorname: /first.?name|given.?name|vorname/i, nachname: /last.?name|family.?name|surname|nachname/i,
  email: /e.?mail/i, telefon: /telefon|phone|^tel$/i, portfolio: /portfolio|work.samples/i,
  linkedin: /linkedin/i, gehalt: /salary|gehalt|compensation/i, start: /earliest.start|eintritt|available.from/i,
  ort: /wohnort|address.level2|current.city/i, plz: /postleitzahl|postal.code/i,
};
async function discover(target) {
  const controls = target.locator('input:not([type=hidden]), textarea, select');
  const discovered = await controls.evaluateAll(nodes => nodes.map(n => ({
    id: n.id, name: n.name, type: n.type, required: n.required,
    label: Array.from(n.labels || [], l => l.textContent.trim()).join(' '),
    autocomplete: n.autocomplete || '', accept: n.accept || '',
  })));
  for (const field of discovered) {
    const desc = [field.id, field.name, field.autocomplete, field.label].join(' ');
    const matches = Object.keys(hints).filter(k=>hints[k].test(desc));
    field.vorschlag = matches.length === 1 ? matches[0] : null;
  }
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
  const report = {dateien:[], hinweis:'Portalangaben betreffen einzelne Dateien. Die Einreichung prüfst du persönlich.'};
  const dest = path.join(config.output, 'uploads.json');
  const persist = () => {
    fs.writeFileSync(dest + '.tmp', JSON.stringify(report, null, 2), {mode:0o600});
    fs.renameSync(dest + '.tmp', dest);
  };
  const groups = config.uploads.map(group => {
    const entries = group.files.map(file => ({name:file.name, sha256:file.sha256, feld:group.selector, status:'offen'}));
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
    report.fehler = error.message;
    persist();
    throw error;
  }
}

async function fillFields(config, target, atJob, discovered) {
  const explicit = new Set();
  for (const field of config.fields) {
    atJob();
    const input = target.locator(field.selector);
    explicit.add(await input.evaluate(n=>n.id || n.name));
    const type = await input.evaluate(n => n instanceof HTMLTextAreaElement ? 'textarea' :
      n instanceof HTMLSelectElement ? 'select' : n instanceof HTMLInputElement ? n.type : '');
    if (type === 'select') await input.selectOption(field.value);
    else if (['textarea','text','email','tel','number','url','date','search'].includes(type)) await input.fill(field.value);
    else throw Error('Dieses Feld erfordert manuelle Eingabe im Portal.');
  }
  for (const f of discovered) {
    if (!f.vorschlag || !Object.hasOwn(config.personal || {},f.vorschlag) || explicit.has(f.id || f.name) ||
        (!f.id && !f.name) || !['text','email','tel','url','number','textarea','date'].includes(f.type)) continue;
    atJob();
    const attr = f.id ? 'id' : 'name';
    const key = f.id || f.name;
    const escaped = await target.evaluate(value=>CSS.escape(value),key);
    const input = target.locator('['+attr+'='+escaped+']');
    if (await input.count() === 1 && await input.isEditable() && !await input.inputValue())
      await input.fill(config.personal[f.vorschlag]);
  }
}

async function prepare(config, context) {
  const page = await context.newPage();
  await page.goto(config.url, { waitUntil: 'domcontentloaded' });
  if (config.profile) {
    const rl = require('node:readline/promises').createInterface({input:process.stdin,output:process.stdout});
    try {await rl.question('Persönlich anmelden, das richtige Formular öffnen und hier Eingabe drücken. ');}
    finally {rl.close();}
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
      try { frames.push({url:frame.url(), fields:await discover(frame)}); }
      catch { frames.push({url:frame.url(), hinweis:'Rahmen beim Lesen nicht verfügbar.'}); }
    }
  }
  fs.writeFileSync(path.join(config.output, 'felder.json'),
    JSON.stringify({url:page.url(), rahmen_url:config.frame || null, fields:discovered, frames}, null, 2),
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
      await fillFields(config, target, atJob, discovered);
      await fillUploads(config, target, atJob);
      atJob();
    } finally {
      await guard.evaluate(restore=>restore()).catch(()=>{});
      await guard.dispose();
    }
  }
  await page.screenshot({path:path.join(config.output,'vorschau.png'), fullPage:true});
  return page;
}

async function main() {
  const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
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
if(require.main === module) main().catch(e=>{console.error(e.message);process.exitCode=1;});
