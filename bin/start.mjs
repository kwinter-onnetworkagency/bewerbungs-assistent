#!/usr/bin/env node
import * as fs from 'node:fs'
import {spawnSync} from 'node:child_process'
import { homedir } from 'node:os'
import path from 'node:path'
import { domainToASCII, fileURLToPath } from 'node:url'
import { createInterface } from 'node:readline/promises'
import { parseArgs } from 'node:util'

const source = fileURLToPath(new URL('../', import.meta.url))
const modes = ['chatgpt', 'claude', 'claude-code', 'codex']
const domainRoutes = JSON.parse(fs.readFileSync(path.join(source, 'resources/domainwege.json'), 'utf8'))
function domainGuide(route, input) {
  const guide = domainRoutes[route] ?? ''
  const wish = (input ?? '').trim().normalize('NFC')
  if (!wish) return guide
  const labels = wish.split('.')
  const ascii = domainToASCII(wish)
  const validLabel = /^[\p{L}\p{N}](?:[\p{L}\p{N}-]*[\p{L}\p{N}])?$/u
  if (route !== 'onnetwork' || labels.length < 2 || !labels.every(label => validLabel.test(label))
      || !/^\p{L}./u.test(labels.at(-1)) || !ascii || ascii.length > 253
      || ascii.split('.').some(label => label.length > 63)) {
    throw Error('Für die Agenturbestellung bitte nur eine Wunschdomain mit Endung eingeben, z. B. beispiel.de.')
  }
  const form = 'https://customer.onnetwork.agency/portal/domains/new'
  return guide.replace(form, form + '?domain=' + encodeURIComponent(wish))
}

function install(target, mode, name, portfolio, route, guide, quiet = false) {
  if (!modes.includes(mode)) throw Error('Wähle chatgpt, claude, claude-code oder codex.')
  if (!name.trim() || [...name].length > 200 || /[\x00-\x1f]/.test(name)) throw Error('Bitte einen gültigen Profilnamen angeben.')
  const homeRelative = target.startsWith("~/") || (process.platform === "win32" && target.startsWith("~\\"))
  const dest = path.resolve(target === "~" ? homedir() : homeRelative ? path.join(homedir(), target.slice(2)) : target)
  for (let parent = dest; ; parent = path.dirname(parent)) {
    if (fs.lstatSync(parent, { throwIfNoEntry: false })?.isSymbolicLink() && parent === dest)
      throw Error('Als Ziel bitte einen neuen Ordner wählen.')
    if (fs.existsSync(parent)) {
      const real = fs.realpathSync(parent)
      if (inside(real, fs.realpathSync(source))) throw Error('Bitte einen Ordner außerhalb des Programms wählen.')
      for (let p = real; ; p = path.dirname(p)) {
        if (fs.lstatSync(path.join(p, '.git'), {throwIfNoEntry: false})) throw Error('Bitte einen Ordner außerhalb von Git wählen.')
        if (p === path.dirname(p)) break
      }
      break
    }
    if (parent === path.dirname(parent)) break
  }
  fs.mkdirSync(path.dirname(dest), {recursive: true, mode: 0o700})
  fs.mkdirSync(dest, {mode: 0o700}) // Exclusive: never adopt or overwrite an existing workspace.
  try {
    for (const dir of ['belege', 'unterlagen', 'dokumente', 'exports', 'integration'])
      fs.mkdirSync(path.join(dest, dir), {mode: 0o700})
    for (const entry of ['bewerbung', 'start.py', 'docs', 'resources', 'LICENSE'])
      fs.cpSync(path.join(source, entry), path.join(dest, entry), {recursive: true, filter: p => path.basename(p) !== '__pycache__'})
    const put = (file, value) => fs.writeFileSync(path.join(dest, file), value, {mode: 0o600})
    const choice = '\nPortfolio-Auswahl im Wizard: ' + (portfolio ? 'Ja' : 'Nein') + '. Im Interview berücksichtigen.\n'
    const instructions = fs.readFileSync(path.join(source, 'resources/ASSISTENT.txt'), 'utf8')
      + choice + (route ? "\nDomainweg: " + guide + "\n" : "")
    let portfolioGuide = ''
    if (portfolio) {
      const folder = path.join(dest, 'portfolio/public')
      fs.mkdirSync(folder, {recursive: true, mode: 0o700})
      const safeName = name.trim().replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      const template = fs.readFileSync(path.join(source, 'resources/Portfolio.html'), 'utf8')
      put('portfolio/public/index.html', template.replaceAll('__NAME__', () => safeName))
      portfolioGuide = '\n' + fs.readFileSync(path.join(source, 'resources/PORTFOLIO.txt'), 'utf8')
      if (route) portfolioGuide += '\n' + guide + '\n'
    }
    put('integration/PROJEKTANWEISUNG.txt', instructions)
    if (mode === 'claude-code' || mode === 'codex') {
      put(mode === 'codex' ? 'AGENTS.md' : 'CLAUDE.md', instructions)
      fs.cpSync(path.join(source, 'resources/skills'), path.join(dest, mode === 'codex' ? '.agents' : '.claude', 'skills'), {recursive: true})
    }
    const profile = JSON.parse(fs.readFileSync(path.join(source, 'examples/profil-vorlage.json'), 'utf8'))
    profile.name = name.trim()
    put('profil.json', JSON.stringify(profile, null, 2) + '\n')
    fs.copyFileSync(path.join(source,'resources/Dashboard.html'), path.join(dest,'exports/Dashboard.html'))
    put('bewerbungen.json', '[]\n')
    put('workspace.json', JSON.stringify({schema_version: 1, assistant: mode, portfolio, domainweg: route, created_at: new Date().toISOString()}, null, 2))
    put('.gitignore', '*\n')
    const next = mode === 'codex' ? 'Öffne diesen Ordner in Codex und schreibe $interview.'
      : mode === 'claude-code' ? 'Öffne diesen Ordner in Claude Code und schreibe /interview.'
      : 'Lege ein privates Chat-Projekt an. Kopiere integration/PROJEKTANWEISUNG.txt in die Projektanweisungen, lade resources/INTERVIEW.md hoch und schreibe /interview.'
    put('START_HIER.md', '# Persönlicher Bewerbungsordner\n\n' + next + '\n\nAnleitung: docs/INSTALLATION.md\n' + portfolioGuide)
    if (!quiet) console.log('Eingerichtet: ' + dest + '\n' + next + portfolioGuide)
  } catch (error) {
    fs.rmSync(dest, {recursive: true, force: true})
    throw error
  }
}
function inside(candidate, base) {
  const rel = path.relative(base, candidate)
  return rel === '' || (!path.isAbsolute(rel) && rel !== '..' && !rel.startsWith('..' + path.sep))
}
// Ein Update arbeitet auf einer privaten Kopie. Erst nach vollständigem Vergleich wird das neue Ziel sichtbar.
function privatePath(input) {
  if (!input?.trim()) throw Error('Privaten Quell- und neuen Zielordner angeben.')
  const value = input === '~' ? homedir() : /^~[/\\]/.test(input) ? path.join(homedir(),input.slice(2)) : input
  const absolute = path.resolve(value)
  for (let p=absolute; ; p=path.dirname(p)) {
    const stat=fs.lstatSync(p,{throwIfNoEntry:false})
    if (stat?.isSymbolicLink()) throw Error('Symbolische Verknüpfung im Ordnerpfad. Den tatsächlichen privaten Pfad angeben.')
    if (stat && fs.lstatSync(path.join(p,'.git'),{throwIfNoEntry:false})) throw Error('Update nur außerhalb von Git.')
    if (p === path.dirname(p)) break
  }
  if (inside(absolute,fs.realpathSync(source))) throw Error('Update nur außerhalb des Programms.')
  return absolute
}

function inventory(root) {
  const result = new Map()
  function walk(folder) {
    for (const entry of fs.readdirSync(path.join(root,folder))) {
      if (folder === '' && entry === '.write-lock') continue
      if (entry.toLowerCase() === '.git') throw Error('Verschachteltes Git-Repository im Arbeitsordner.')
      const rel=path.join(folder,entry)
      const stat=fs.lstatSync(path.join(root,rel), {bigint:true})
      if (!stat.isFile() && !stat.isDirectory()) throw Error('Verknüpfung oder Sonderdatei im bisherigen Ordner: '+rel)
      result.set(rel, {dir:stat.isDirectory(), fingerprint:[stat.dev,stat.ino,stat.size,stat.mtimeNs,stat.ctimeNs].join(':')})
      if (stat.isDirectory()) walk(rel)
    }
  }
  walk('')
  return result
}

function updateWorkspace(from, target) {
  const old=privatePath(from), dest=privatePath(target)
  if (inside(dest,old) || inside(old,dest)) throw Error('Quelle und Ziel müssen getrennte private Ordner sein.')
  if (fs.lstatSync(dest,{throwIfNoEntry:false})) throw Error('Ziel existiert bereits.')
  if (!fs.lstatSync(old).isDirectory() || !['workspace.json','profil.json','bewerbungen.json','start.py']
      .every(name=>fs.lstatSync(path.join(old,name),{throwIfNoEntry:false})?.isFile())) {
    throw Error('Vollständigen persönlichen Arbeitsordner angeben.')
  }
  const lock=path.join(old,'.write-lock')
  try {fs.mkdirSync(lock,{mode:0o700})} catch(error) {
    if(error.code === 'EEXIST') throw Error('Bisheriger Ordner wird bearbeitet. Vorgänge beenden und erneut versuchen.')
    throw error
  }
  let stageParent, ownsDest=false
  try {
    const original=inventory(old)
    const json=name=>JSON.parse(fs.readFileSync(path.join(old,name),'utf8').replace(/^\uFEFF/,''))
    const meta=json('workspace.json'), profile=json('profil.json'), jobs=json('bewerbungen.json')
    if (meta.schema_version !== 1 || !modes.includes(meta.assistant) || profile.schema_version !== 1 ||
        !Array.isArray(jobs) || profile.export_only || !fs.existsSync(path.join(old,'start.py'))) {
      throw Error('Vollständigen persönlichen Arbeitsordner mit unterstützter Version angeben.')
    }
    fs.mkdirSync(path.dirname(dest),{recursive:true,mode:0o700})
    stageParent=fs.mkdtempSync(path.join(path.dirname(dest),'.bewerbung-update-'))
    const stage=path.join(stageParent,'arbeitsordner')
    install(stage,meta.assistant,profile.name,Boolean(meta.portfolio),meta.domainweg,
            Object.hasOwn(domainRoutes,meta.domainweg) ? domainRoutes[meta.domainweg] : '',true)
    let archive='Update-Abgleich'
    while (original.has(archive) || fs.existsSync(path.join(stage,archive))) archive+='-neu'
    const secured=path.join(stage,archive)
    const tools=new Set(['start.py','bewerbung','resources','docs','LICENSE'])
    const instructions=new Set(['AGENTS.md','CLAUDE.md','.agents','.claude','integration','START_HIER.md'])
    for (const [relative,{dir}] of original) {
      const first=relative.split(path.sep)[0]
      const file=path.join(old,relative)
      const current=path.join(stage,relative)
      const copyTo=tools.has(first) ? path.join(secured,'werkzeug-bisher',relative) : current
      if (dir) {
        fs.mkdirSync(copyTo,{recursive:true,mode:0o700})
        continue
      }
      fs.mkdirSync(path.dirname(copyTo),{recursive:true,mode:0o700})
      if (instructions.has(first) && fs.existsSync(current) &&
          !fs.readFileSync(current).equals(fs.readFileSync(file))) {
        const fresh=path.join(secured,'vorlagen-neu',relative)
        fs.mkdirSync(path.dirname(fresh),{recursive:true,mode:0o700})
        fs.copyFileSync(current,fresh)
      }
      fs.copyFileSync(file,copyTo)
      fs.chmodSync(copyTo,(fs.statSync(file).mode & 0o111) ? 0o700 : 0o600)
    }
    // Auch Änderungen durch Editoren ohne Anwendungssperre erkennen.
    const final=inventory(old)
    if (final.size !== original.size || [...original].some(([k,v])=>final.get(k)?.fingerprint !== v.fingerprint))
      throw Error('Der bisherige Arbeitsordner wurde während der Kopie verändert. Update wiederholen.')
    fs.mkdirSync(dest,{mode:0o700})
    ownsDest=true
    fs.mkdirSync(path.join(dest,'.write-lock'),{mode:0o700})
    const entries=fs.readdirSync(stage).filter(n=>n!=='workspace.json')
    for (const name of [...entries,'workspace.json']) fs.renameSync(path.join(stage,name),path.join(dest,name))
    fs.rmdirSync(path.join(dest,'.write-lock'))
    console.log('Aktualisiert: '+dest+'\nWerkzeuge aktualisiert. Bestehende Chat-Anweisungen und gleichnamige Skills vergleichen: '+path.join(dest,archive))
  } catch(error) {
    if (ownsDest) fs.rmSync(dest,{recursive:true,force:true})
    throw error
  } finally {
    try {if(stageParent) fs.rmSync(stageParent,{recursive:true,force:true})} finally {fs.rmdirSync(lock)}
  }
}

async function main() {
  if (process.argv[2] === 'aktualisieren') {
    const {values}=parseArgs({args:process.argv.slice(3),options:{von:{type:'string'},ziel:{type:'string'}}})
    updateWorkspace(values.von,values.ziel)
    return
  }
  if (['run', 'ausfuehren'].includes(process.argv[2])) {
    const candidates = process.platform === 'win32' ? [['py','-3'],['python']] : [['python3'],['python']];
    for (const [binary,...prefix] of candidates) {
      const probe = spawnSync(binary,[...prefix,'-c','import sys; sys.exit(sys.version_info < (3,11))']);
      if (probe.status !== 0) continue;
      const result = spawnSync(binary,[...prefix,path.join(source,'start.py'),...process.argv.slice(3)],{stdio:'inherit'});
      if (result.error) throw result.error;
      process.exitCode = result.status ?? 1;
      return;
    }
    throw Error('Für lokale Arbeitsbefehle Python ab 3.11 installieren. Die Chataktionen sind ohne lokale Installation nutzbar.');
  }
  const {values} = parseArgs({options: {hilfe: {type:'boolean'}, help: {type:'boolean', short:'h'}, version: {type:'boolean'}, ziel: {type:'string'}, assistent: {type:'string'}, name: {type:'string'}, portfolio: {type:'string'}, domainweg: {type:'string'}, wunschdomain: {type:'string'}}})
  if (values.version) return console.log(JSON.parse(fs.readFileSync(path.join(source,'package.json'))).version)
  if (values.help || values.hilfe) return console.log('Bewerbungs-Assistent einrichten\nOhne Optionen startet der Dialog. Alternativ: --assistent chatgpt|claude|claude-code|codex --name NAME --ziel NEUER_ORDNER [--portfolio ja|nein] [--domainweg vorhanden|onnetwork|cloudflare|spaeter] [--wunschdomain beispiel.de]\nIm Assistenten mit /interview beginnen, in Codex mit $interview. Lokale Befehle: run --ordner PRIVATER_ORDNER --help. Update: aktualisieren --von ALTER_ORDNER --ziel NEUER_ORDNER.')
  const rl = createInterface({input: process.stdin, output: process.stdout})
  const defaultTarget = path.join(homedir(), 'Bewerbungen', 'Mein-Bewerbungsprojekt')
  try {
    const ask = async question => {
      if (!process.stdin.isTTY) throw Error('Ohne interaktives Terminal bitte --assistent, --name und --ziel angeben.')
      return (await rl.question(question)).trim()
    }
    const mode = values.assistent ?? ((await ask('Wo möchtest du arbeiten? chatgpt, claude, claude-code oder codex [chatgpt]: ')) || 'chatgpt')
    const name = values.name ?? await ask('Wie möchtest du im Profil heißen? ')
    const dest = values.ziel ?? ((await ask('Neuer privater Ordner [' + defaultTarget + ']: ')) || defaultTarget)
    if (!dest.trim()) throw Error('Bitte einen neuen Zielordner angeben.')
    const guided = [values.name, values.ziel, values.assistent].some(value => value === undefined)
    const interactive = guided && process.stdin.isTTY
    const yesNo = async (given, prompt, fallback) => {
      let answer = given
      while (true) {
        if (answer === undefined && !interactive) return fallback
        answer = (answer ?? await ask(prompt)).trim().toLowerCase()
        if (!answer && given === undefined) return fallback
        if (['j', 'ja', 'y', 'yes'].includes(answer)) return true
        if (['n', 'nein', 'no'].includes(answer)) return false
        if (given !== undefined) throw Error('Bitte antworte mit ja oder nein.')
        console.log('Bitte antworte mit ja oder nein.')
        answer = undefined
      }
    }
    const portfolio = await yesNo(values.portfolio, 'Möchtest du auch ein persönliches Portfolio erstellen? [J/n]: ', true)
    let route = values.domainweg ?? null
    if (route !== null && (!portfolio || !Object.hasOwn(domainRoutes, route)))
      throw Error('Bitte einen gültigen Domainweg mit aktivem Portfolio wählen.')
    if (portfolio && route === null && interactive) {
      if (await yesNo(undefined, 'Besitzt du eine eigene Domain? [j/N]: ', false)) route = 'vorhanden'
      else {
        const options = new Map([['1', 'onnetwork'], ['2', 'cloudflare'], ['3', 'spaeter']])
        while (!route) {
          const pick = await ask('Wie möchtest du starten? 1 Domain bei on:NetworkAgency registrieren, 2 bei Cloudflare registrieren, 3 kostenlose pages.dev-Adresse [3]: ')
          route = options.get(pick || '3')
          if (!route) console.log('Bitte wähle 1, 2 oder 3.')
        }
      }
    }
    let guide
    if (values.wunschdomain === undefined && interactive && route === 'onnetwork') {
      while (true) {
        const wish = await ask('Welche Wunschdomain soll im Bestellformular stehen? (optional, z. B. beispiel.de): ')
        try {
          guide = domainGuide(route, wish)
          break
        } catch (error) {
          console.log(error.message)
        }
      }
    } else {
      guide = domainGuide(route, values.wunschdomain)
    }
    install(dest, mode, name, portfolio, route, guide)
  } finally { rl.close() }
}
main().catch(error => { console.error(error.code === 'EEXIST' ? 'Ziel existiert bereits. Bitte einen neuen Ordner wählen.' : error.message); process.exitCode = 1 })
