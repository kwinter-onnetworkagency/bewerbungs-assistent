import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
const launcher = fileURLToPath(new URL('../bin/start.mjs', import.meta.url))
const commands = ['interview','stellensuche','anschreiben','rueckmeldung','bericht','dashboard','gehalt','gespraech']
function setup(dest, mode) {
  return spawnSync(process.execPath, [launcher, '--assistent', mode, '--ziel', dest, '--name', 'Testperson'], {encoding: 'utf8'})
}
test('Vier Einstiege erzeugen nutzbare Kurzbefehle in einem neuen persönlichen Ordner', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'bewerbung-npx-'))
  t.after(() => fs.rmSync(root, {recursive:true,force:true}))
  for (const mode of ['chatgpt','claude','claude-code','codex']) {
    const dest = path.join(root, 'Privater Ordner ' + mode)
    const result = setup(dest, mode)
    assert.equal(result.status, 0, result.stderr)
    assert.ok(fs.existsSync(path.join(dest,'exports/Dashboard.html')))
    assert.equal(JSON.parse(fs.readFileSync(path.join(dest,'workspace.json'))).portfolio, null)
    assert.ok(!fs.existsSync(path.join(dest,'portfolio')))
    const instructions = fs.readFileSync(path.join(dest,'integration/PROJEKTANWEISUNG.txt'),'utf8')
    for (const name of commands) {
      assert.ok(instructions.includes('/' + name + ' '))
      if (mode === 'claude-code' || mode === 'codex') {
        const skill = fs.readFileSync(path.join(dest, mode === 'codex' ? '.agents':'.claude','skills',name,'SKILL.md'),'utf8')
        assert.ok(skill.split(/\r?\n/).includes('name: ' + name))
      }
    }
    assert.equal(JSON.parse(fs.readFileSync(path.join(dest,'profil.json'))).name,'Testperson')
    assert.notEqual(setup(dest,mode).status,0)
    assert.equal(JSON.parse(fs.readFileSync(path.join(dest,'profil.json'))).name,'Testperson')
    const checked = spawnSync(process.platform === 'win32' ? 'python' : 'python3', ['start.py','pruefen'], {cwd:dest,encoding:'utf8'})
    assert.equal(checked.status,0,checked.stderr)
    assert.match(checked.stdout,/Profil gültig/)
  }
  fs.mkdirSync(path.join(root,'.git'))
  const forbidden = path.join(root,'nested','data')
  assert.notEqual(setup(forbidden,'chatgpt').status,0)
  assert.ok(!fs.existsSync(forbidden))
})

test('Tilde im Ziel bezeichnet den persönlichen Benutzerordner', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bewerbung-home-'))
  t.after(() => fs.rmSync(root, {recursive:true, force:true}))
  const result = spawnSync(process.execPath, [launcher, '--assistent','chatgpt','--name','Testperson','--ziel','~/Meine Bewerbung'], {
    cwd:root, env:{...process.env, HOME:root, USERPROFILE:root}, encoding:'utf8'
  })
  assert.equal(result.status,0,result.stderr)
  assert.ok(fs.existsSync(path.join(root,'Meine Bewerbung','profil.json')))
  assert.ok(!fs.existsSync(path.join(root,'~')))
})

test('Portfolio nur auf Wunsch, mit lokalem Uploadordner und Cloudflare-Anleitung', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'portfolio-'))
  t.after(() => fs.rmSync(root, {recursive:true, force:true}))
  for (const answer of ['ja', 'nein']) {
    const dest = path.join(root, answer)
    const run = spawnSync(process.execPath, [launcher, '--assistent', 'codex', '--name', 'A & B <Test> $&',
      '--ziel', dest, '--portfolio', answer], {encoding:'utf8'})
    assert.equal(run.status, 0, run.stderr)
    const optedIn = answer === 'ja'
    assert.equal(JSON.parse(fs.readFileSync(path.join(dest,'workspace.json'))).portfolio, optedIn)
    assert.equal(fs.existsSync(path.join(dest,'portfolio')), optedIn)
    assert.equal(run.stdout.includes('Nameserver'), optedIn)
    if (optedIn) {
      const folder = path.join(dest,'portfolio/public')
      assert.deepEqual(fs.readdirSync(folder), ['index.html'])
      assert.match(fs.readFileSync(path.join(folder,'index.html'),'utf8'), /A &amp; B &lt;Test&gt; \$&amp;/)
    }
  }
})
