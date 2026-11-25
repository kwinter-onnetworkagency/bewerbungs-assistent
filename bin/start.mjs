#!/usr/bin/env node
import * as fs from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createInterface } from 'node:readline/promises'
import { parseArgs } from 'node:util'

const source = fileURLToPath(new URL('../', import.meta.url))
const modes = ['chatgpt', 'claude', 'claude-code', 'codex']
function install(target, mode, name, portfolio) {
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
    const choice = portfolio ? 'Ja' : 'Nein'
    const instructions = fs.readFileSync(path.join(source, 'resources/ASSISTENT.txt'), 'utf8')
      + '\nPortfolio-Auswahl im Wizard: ' + choice + '. Im Interview berücksichtigen.\n'
    let portfolioGuide = ''
    if (portfolio) {
      const folder = path.join(dest, 'portfolio/public')
      fs.mkdirSync(folder, {recursive: true, mode: 0o700})
      const safeName = name.trim().replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      const template = fs.readFileSync(path.join(source, 'resources/Portfolio.html'), 'utf8')
      put('portfolio/public/index.html', template.replaceAll('__NAME__', () => safeName))
      portfolioGuide = '\n' + fs.readFileSync(path.join(source, 'resources/PORTFOLIO.txt'), 'utf8')
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
    put('workspace.json', JSON.stringify({schema_version: 1, assistant: mode, portfolio, created_at: new Date().toISOString()}, null, 2))
    put('.gitignore', '*\n')
    const next = mode === 'codex' ? 'Öffne diesen Ordner in Codex und schreibe $interview.'
      : mode === 'claude-code' ? 'Öffne diesen Ordner in Claude Code und schreibe /interview.'
      : 'Lege ein privates Chat-Projekt an. Kopiere integration/PROJEKTANWEISUNG.txt in die Projektanweisungen, lade resources/INTERVIEW.md hoch und schreibe /interview.'
    put('START_HIER.md', '# Persönlicher Bewerbungsordner\n\n' + next + '\n\nAnleitung: docs/INSTALLATION.md\n' + portfolioGuide)
    console.log('Eingerichtet: ' + dest + '\n' + next + portfolioGuide)
  } catch (error) {
    fs.rmSync(dest, {recursive: true, force: true})
    throw error
  }
}
function inside(candidate, base) {
  const rel = path.relative(base, candidate)
  return rel === '' || (!path.isAbsolute(rel) && rel !== '..' && !rel.startsWith('..' + path.sep))
}
async function main() {
  const {values} = parseArgs({options: {hilfe: {type:'boolean'}, help: {type:'boolean', short:'h'}, version: {type:'boolean'}, ziel: {type:'string'}, assistent: {type:'string'}, name: {type:'string'}, portfolio: {type:'string'}}})
  if (values.version) return console.log(JSON.parse(fs.readFileSync(path.join(source,'package.json'))).version)
  if (values.help || values.hilfe) return console.log('Bewerbungs-Assistent einrichten\nOhne Optionen startet der Dialog. Alternativ: --assistent chatgpt|claude|claude-code|codex --name NAME --ziel NEUER_ORDNER [--portfolio ja|nein]\nIm Assistenten mit /interview beginnen, in Codex mit $interview.')
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
    const answer = (values.portfolio ?? (guided && process.stdin.isTTY
      ? await ask('Möchtest du auch ein persönliches Portfolio erstellen? [j/N]: ') : '')).toLowerCase()
    if (!['', 'n', 'nein', 'no', 'j', 'ja', 'y', 'yes'].includes(answer))
      throw Error('Bitte antworte mit ja oder nein.')
    install(dest, mode, name, ['j', 'ja', 'y', 'yes'].includes(answer))
  } finally { rl.close() }
}
main().catch(error => { console.error(error.code === 'EEXIST' ? 'Ziel existiert bereits. Bitte einen neuen Ordner wählen.' : error.message); process.exitCode = 1 })
