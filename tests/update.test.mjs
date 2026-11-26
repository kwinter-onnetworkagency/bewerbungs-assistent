import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'

const current=fileURLToPath(new URL('../bin/start.mjs',import.meta.url))
const previous=process.env.UPDATE_BASELINE_DIR ? path.join(process.env.UPDATE_BASELINE_DIR,'bin/start.mjs') : current
const cli=(binary,...args)=>spawnSync(process.execPath,[binary,...args],{encoding:'utf8'})
function workspace(t) {
  const base=fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()),'bewerbung-update-test-'))
  t.after(()=>fs.rmSync(base,{recursive:true,force:true}))
  const old=path.join(base,'alt'), target=path.join(base,'neu')
  const installed=cli(previous,'--assistent','codex','--name','Testperson','--ziel',old,'--portfolio','ja')
  assert.equal(installed.status,0,installed.stderr)
  return {base,old,target,update:(dest=target)=>cli(current,'aktualisieren','--von',old,'--ziel',dest)}
}

test('Update übernimmt Originaldaten und eigene Ergänzungen, neue Werkzeuge sind ausführbar',t=>{
  const {old,target,update}=workspace(t)
  const name='Unterlagen-Test.pdf', files={
    ['belege/'+name]:Buffer.from('%PDF-1.4 Nur ein Übernahmetest'),
    'portfolio/public/index.html':'<p>Eigene Portfoliofassung</p>',
    'integration/PROJEKTANWEISUNG.txt':'Meine Chat-Regeln',
    'AGENTS.md':'Eigene Regeln',
    '.agents/skills/stellensuche/SKILL.md':'Eigene Suchregel',
    'resources/Eigene-Vorlage.md':'Behalten',
    'gespraeche/runde-1/Nachbereitung.txt':'Eigens ergänzt',
    'interview.json':'{"status":"in_bearbeitung"}',
    'unbekannter-ordner/eigene-daten.txt':'Benutzerablage',
  }
  for (const [rel,value] of Object.entries(files)) {
    const file=path.join(old,rel);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,value)
  }
  const sourceInfo=fs.readFileSync(path.join(old,'workspace.json'))
  const sourceProfile=fs.readFileSync(path.join(old,'profil.json'))
  const python=process.platform==='win32'?'py':'python3'
  const prefix=process.platform==='win32'?['-3']:[]
  fs.writeFileSync(path.join(old,'anzeige.txt'),'Vollständige synthetische Stellenanzeige.')
  const runOld=spawnSync(python,[...prefix,'start.py','stelle','--firma','Testbetrieb','--rolle','Disposition',
    '--url','https://example.org/vakanz','--textdatei','anzeige.txt'],{cwd:old,encoding:'utf8'})
  assert.equal(runOld.status,0,runOld.stderr)
  const sourceJobs=fs.readFileSync(path.join(old,'bewerbungen.json'))
  const result=update()
  assert.equal(result.status,0,result.stderr)
  for (const [rel,value] of Object.entries(files)) {
    const restored=rel.startsWith('resources/')?'Update-Abgleich/werkzeug-bisher/'+rel:rel
    assert.deepEqual(fs.readFileSync(path.join(target,restored)),Buffer.from(value))
    assert.deepEqual(fs.readFileSync(path.join(old,rel)),Buffer.from(value))
  }
  for(const [rel,data] of [['workspace.json',sourceInfo],['profil.json',sourceProfile],['bewerbungen.json',sourceJobs]]) {
    assert.deepEqual(fs.readFileSync(path.join(target,rel)),data)
  }
  assert.ok(fs.existsSync(path.join(target,'Update-Abgleich/vorlagen-neu/AGENTS.md')))
  assert.ok(fs.existsSync(path.join(target,'Update-Abgleich/vorlagen-neu/.agents/skills/stellensuche/SKILL.md')))
  const probe=spawnSync(python,[...prefix,'start.py','pruefen'],{cwd:target,encoding:'utf8'})
  assert.equal(probe.status,0,probe.stderr)
  assert.match(probe.stdout,/Profil gültig/)
  const help=spawnSync(python,[...prefix,'start.py','--help'],{cwd:target,encoding:'utf8'})
  assert.match(help.stdout,/persona-pruefen/)
  assert.equal(fs.existsSync(path.join(old,'.write-lock')),false)
})

test('Sperre, bestehendes Ziel und Ziel innerhalb der Quelle bleiben unangetastet',t=>{
  const {old,target,update}=workspace(t)
  fs.mkdirSync(path.join(old,'.write-lock'))
  assert.notEqual(update().status,0)
  assert.ok(fs.existsSync(path.join(old,'.write-lock')))
  fs.rmdirSync(path.join(old,'.write-lock'))
  assert.notEqual(update(path.join(old,'kopie')).status,0)
  fs.mkdirSync(target);fs.writeFileSync(path.join(target,'meins'),'behalten')
  assert.notEqual(update().status,0)
  assert.equal(fs.readFileSync(path.join(target,'meins'),'utf8'),'behalten')
})

test('Verschachtelte Repos, Git-Ziel und verknüpfte Daten werden vor der Übernahme abgewiesen',t=>{
  const {base,old,target,update}=workspace(t)
  fs.mkdirSync(path.join(old,'belege/.git'))
  assert.notEqual(update().status,0)
  fs.rmdirSync(path.join(old,'belege/.git'))
  fs.mkdirSync(path.join(base,'repo/.git'),{recursive:true})
  assert.notEqual(update(path.join(base,'repo','ziel')).status,0)
  fs.symlinkSync(base,path.join(old,'fremd'),process.platform==='win32'?'junction':'dir')
  assert.notEqual(update().status,0)
  assert.equal(fs.existsSync(target),false)
  assert.equal(fs.existsSync(path.join(old,'.write-lock')),false)
})

test('Frühere Abgleichordner und benutzereigene Dateien überleben ein weiteres Update',t=>{
  const {base,old,target,update}=workspace(t)
  fs.mkdirSync(path.join(old,'Update-Abgleich'))
  fs.writeFileSync(path.join(old,'Update-Abgleich','Notiz.txt'),'meine Notiz')
  assert.equal(update().status,0)
  const newer=path.join(base,'neuer')
  const result=cli(current,'aktualisieren','--von',target,'--ziel',newer)
  assert.equal(result.status,0,result.stderr)
  assert.equal(fs.readFileSync(path.join(newer,'Update-Abgleich','Notiz.txt'),'utf8'),'meine Notiz')
  assert.ok(fs.existsSync(path.join(newer,'Update-Abgleich-neu-neu/werkzeug-bisher/start.py')))
})
