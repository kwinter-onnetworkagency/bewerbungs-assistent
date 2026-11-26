"""Private Vorbereitung für das persönliche berufliche Netzwerkprofil."""
from hashlib import sha256
from pathlib import Path
from .core import identifier, now, read, text, write, write_bytes


def register(commands):
    p = commands.add_parser("linkedin", help="Freigegebene Profilfakten mit einem bereitgestellten Profiltext vergleichen")
    p.add_argument("--fakt", action="append", required=True)
    p.add_argument("--sprache", choices=("de", "en"), default="de")
    p.add_argument("--bestand", type=Path, help="Optional selbst bereitgestellter Profiltext als UTF-8-Datei")
    p = commands.add_parser("empfehlung", help="Den belegten Stand einer persönlichen LinkedIn-Empfehlung nachhalten")
    p.add_argument("id", type=identifier, help="Selbst gewählte Kennung für den privaten Vorgang")
    p.add_argument("--stand", choices=("geplant", "angefragt", "erhalten", "gegeben"), required=True)
    p.add_argument("--kontakt", required=True)
    p.add_argument("--beleg", type=Path)


def run(a, w):
    if a.command not in {"linkedin", "empfehlung"}:
        return False
    with w.locked():
        folder = w.path("unterlagen", "netzwerkprofil")
        folder.mkdir(mode=0o700, exist_ok=True)
        if a.command == "empfehlung":
            recipient = text(a.kontakt, "Kontakt", 200)
            path = w.path(folder, "empfehlungen.json")
            events = read(path) if path.exists() else []
            if any(e["id"] == a.id and e["kontakt"] != recipient for e in events):
                raise ValueError("Kennung gehört bereits zu einem anderen Kontakt.")
            if a.stand != "geplant" and not a.beleg:
                raise ValueError("Für diesen Stand einen geprüften Beleg angeben.")
            entry = dict(id=a.id, kontakt=recipient, stand=a.stand, beleg=w.evidence(a.beleg) if a.beleg else None)
            if not any(all(e[k] == v for k, v in entry.items()) for e in events):
                write(path, [*events, dict(entry, erfasst=now())])
            print(path)
            return True
        profile = w.profile()
        lookup = {f["id"]: f for f in profile["facts"]}
        existing = ""
        if a.bestand:
            if a.bestand.is_symlink() or not a.bestand.is_file() or a.bestand.stat().st_size > 500000:
                raise ValueError("Eigenen Profiltext als reguläre UTF-8-Datei bis 500 kB angeben.")
            existing = a.bestand.read_text(encoding="utf-8-sig")
        normalized = " ".join(existing.casefold().split())
        paragraphs = [f"# LinkedIn-Profil · {profile['name']} ({a.sprache})", ""]
        if profile["target_roles"]:
            paragraphs += ["Zielrollen für den Profil-Slogan: " + ", ".join(profile["target_roles"]), ""]
        for fid in dict.fromkeys(a.fakt):
            fact = lookup.get(fid)
            if not fact:
                raise ValueError("Unbekannte Fakten-ID: " + fid)
            statement = fact["text"] if fact.get("language", "de") == a.sprache else fact.get("translations", {}).get(a.sprache)
            if not statement:
                raise ValueError("Freigegebene Übersetzung fehlt: " + fid)
            label = "wörtlich vorhanden" if " ".join(statement.casefold().split()) in normalized else (
                "Formulierung vergleichen" if a.bestand else "für den Entwurf ausgewählt")
            paragraphs += [f"## {fid} · {label}", "", statement, ""]
        paragraphs += ["## Redaktionelle Prüfung", "",
                       "Profil-Slogan, Info-Abschnitt, Stationen und Kenntnisse anhand dieser Auswahl formulieren. "
                       "Sinngemäße Übereinstimmungen und die persönlichen Freigaben vor der Übernahme prüfen."]
        if a.bestand:
            paragraphs += ["", "Verglichener Ausgangstext (SHA-256): " + sha256(existing.encode()).hexdigest()]
        content = ("\n".join(paragraphs) + "\n").encode()
        path = w.path(folder, f"Profil-{a.sprache}-{sha256(content).hexdigest()[:16]}.md")
        write_bytes(path, content)
        print(path)
        return True
