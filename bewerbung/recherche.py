"""Öffentliche Stellenquellen, lokale Passungsprüfung und belegte Gehaltsangaben."""
import base64
from datetime import date, datetime, timezone
from decimal import Decimal
from difflib import unified_diff
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

from .core import identity, keyword_match, now, read, text, url, write

BA = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
ATLAS = "https://rest.arbeitsagentur.de/infosysbub/entgeltatlas/pc/v1/entgelte/"
GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/"
MAX_BYTES = 8 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Auch bei einem Anbieter-Redirect bleiben Zugangsdaten beim ursprünglichen Host.
        return None


def fetch(address, key=None):
    headers = {"Accept": "application/json", "User-Agent": "bewerbungs-assistent"}
    if key:
        headers["X-API-Key"] = key
    try:
        with build_opener(NoRedirect()).open(Request(address, headers=headers), timeout=15) as response:
            raw = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        raise ValueError(f"Anbieter meldet HTTP {exc.code}.") from None
    except OSError:
        raise ValueError("Anbieter nicht erreichbar (Netzwerk, TLS oder Zeitlimit).") from None
    if len(raw) > MAX_BYTES:
        raise ValueError("Anbieterantwort größer als 8 MiB.")
    try:
        return json.loads(raw)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("Anbieter hat kein lesbares JSON geliefert.") from None


def rows(data, field):
    if not isinstance(data, dict) or not isinstance(data.get(field), list):
        raise ValueError("Erwartete Ergebnisliste fehlt: " + field)
    return data[field]


def choice_list(values):
    return list(dict.fromkeys(text(v, "Suchbegriff", 200) for v in values))


def words_match(terms, value):
    return any(all(word in value.casefold() for word in term.casefold().split()) for term in terms)


def list_ba(role, region, args, coverage):
    key = os.environ.get("BA_JOBSUCHE_API_KEY")
    if not key:
        raise ValueError("BA_JOBSUCHE_API_KEY fehlt.")
    for page in range(1, args.seiten + 1):
        params = dict(was=role, page=page, size=25, angebotsart=1, veroeffentlichtseit=args.tage)
        if region:
            params.update(wo=region, umkreis=args.umkreis)
        batch = rows(fetch(BA + "/pc/v6/jobs?" + urlencode(params), key), "ergebnisliste")
        for item in batch:
            if not isinstance(item, dict):
                raise ValueError("BA-Treffer hat ein unbekanntes Format.")
            ref = text(item.get("referenznummer"), "Referenz", 200)
            locations = item.get("stellenlokationen") or []
            places = [str(loc["adresse"].get("ort") or "") for loc in locations
                      if isinstance(loc, dict) and isinstance(loc.get("adresse"), dict)]
            ad = dict(role=text(item.get("stellenangebotsTitel"), "Titel", 500),
                      company=text(item.get("firma"), "Arbeitgeber", 500), location=", ".join(filter(None, places)),
                      reference=ref, url="https://www.arbeitsagentur.de/jobsuche/jobdetail/" + quote(ref, safe=""))
            for field in ("gehaltsspanneVon", "gehaltsspanneBis", "verguetungsangabe"):
                if item.get(field) is not None:
                    ad.setdefault("gehaltsangabe_der_anzeige", {})[field] = item[field]
            if args.details:
                encoded = quote(base64.b64encode(ref.encode()).decode(), safe="")
                try:
                    detail = fetch(BA + "/pc/v4/jobdetails/" + encoded, key)
                    ad["description"] = text(detail.get("stellenangebotsBeschreibung") if isinstance(detail, dict)
                                             else None, "BA-Anzeigentext", 200000)
                except ValueError as exc:
                    coverage.setdefault("detailfehler", []).append({"referenz": ref, "grund": str(exc)})
                    coverage["status"] = "teilweise"
            yield ad
        if len(batch) < 25:
            break
    else:
        coverage.update(status="teilweise", hinweis="Seitenlimit erreicht. Weitere Treffer möglich.")


class AdText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, value):
        self.parts.append(value)


def list_board(board, terms, region, details):
    # Erst Treffer filtern, danach bei Bedarf genau deren Volltexte holen.
    endpoint = GREENHOUSE + board + "/jobs"
    for item in rows(fetch(endpoint), "jobs"):
        if not isinstance(item, dict):
            raise ValueError("Greenhouse-Treffer hat ein unbekanntes Format.")
        role = text(item.get("title"), "Titel", 500)
        location = item.get("location") or {}
        place = location.get("name") if isinstance(location, dict) else None
        place = place if isinstance(place, str) else ""
        if not words_match(terms, role) or region and region.casefold() not in place.casefold():
            continue
        ref = item.get("id")
        if type(ref) is not int or ref <= 0:
            raise ValueError("Greenhouse-Stellen-ID fehlt.")
        ad = dict(role=role, board=board, reference=str(ref), location=place, url=url(item.get("absolute_url")))
        if details:
            try:
                detail = fetch(endpoint + "/" + str(ref))
                markup = text(detail.get("content") if isinstance(detail, dict) else None, "Anzeigentext", 500000)
                parser = AdText()
                parser.feed(unescape(markup) if "&lt;" in markup and "<" not in markup else markup)
                parser.close()
                ad["description"] = text(" ".join(" ".join(parser.parts).split()), "Anzeigentext", 200000)
            except ValueError as exc:
                ad["detailfehler"] = str(exc)
        yield ad


def indeed_import(path, terms, region):
    data = read(path)
    if not isinstance(data, list):
        raise ValueError("Indeed-Datei muss eine JSON-Liste sein.")
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("Indeed-Treffer muss ein Objekt sein.")
        role = text(entry.get("role"), "Titel", 500)
        place = text(entry["location"], "Ort", 500) if entry.get("location") else ""
        if not words_match(terms, role) or region and region.casefold() not in place.casefold():
            continue
        source = url(entry.get("indeed_url"))
        host = urlsplit(source).hostname
        if not any(host == domain or host.endswith("." + domain) for domain in ("indeed.com", "indeed.de", "indeed.co.uk")):
            raise ValueError("indeed_url braucht einen Indeed-Host.")
        retrieved = date.fromisoformat(text(entry.get("gesehen_am"), "Abrufdatum", 10))
        if retrieved > date.today():
            raise ValueError("Abrufdatum des Imports liegt in der Zukunft.")
        ad = dict(role=role, company=text(entry.get("company"), "Arbeitgeber", 500), location=place,
                  url=url(entry.get("url") or source), indeed_url=source, gesehen_am=retrieved.isoformat())
        for field in ("anforderungen", "arbeitsmodell", "gehaltsangabe_der_anzeige", "description"):
            if entry.get(field) is not None:
                ad[field] = text(entry[field], field, 200000 if field == "description" else 20000)
        yield ad


def changes(previous, current):
    compared = {}
    for key in ("role", "description", "location", "anforderungen", "arbeitsmodell", "gehaltsangabe_der_anzeige"):
        if key not in previous or key not in current or previous[key] == current[key]:
            continue
        if key == "description":
            old, new = str(previous[key]), str(current[key])
            if " ".join(old.split()) == " ".join(new.split()):
                continue
            compared[key] = {"differenz": "\n".join(unified_diff(old.splitlines(), new.splitlines(),
                             fromfile="vorher", tofile="jetzt", lineterm=""))}
        else:
            compared[key] = {"vorher": previous[key], "jetzt": current[key]}
    return compared


def latest_fields(job):
    state = {key: job[key] for key in ("role", "description")}
    for observation in job.get("anzeigenstaende", []):
        state.update(observation["angaben"])
    return state


def save_observation(workspace, jid, status, source, reason, fields, take=False):
    source = url(source)
    reason = text(reason, "Gelesene Arbeitgeberaussage oder beobachteter Zugangsfehler")
    if take and (status != "offen" or "description" not in fields):
        raise ValueError("Nur einen bestätigten offenen Volltext als aktuelle Anzeige übernehmen.")
    if status == "zugang_offen" and fields:
        raise ValueError("Bei einem Zugangsfehler sind neue Anzeigenangaben unbelegt.")
    with workspace.locked():
        jobs = workspace.jobs()
        job = workspace.job(jobs, jid)
        before = latest_fields(job)
        row = dict(zustand=status, quelle=source, beleg=reason, angaben=fields)
        history = job.setdefault("anzeigenstaende", [])
        if not history or any(history[-1].get(k) != v for k, v in row.items()):
            row.update(zeit=now(), aenderungen=changes(before, fields))
            history.append(row)
        if take and job["description"] != fields["description"]:
            history[-1].setdefault("ersetzter_volltext", job["description"])
            job["description"] = fields["description"]
            job["qa"] = None
            if job["status"] == "vorbereitet":
                job["status"] = "recherche"
        write(workspace.path("bewerbungen.json"), jobs)
        return history[-1]


def search(workspace, args):
    terms = choice_list(args.begriff or workspace.profile()["target_roles"])
    if not terms:
        raise ValueError("Mindestens einen --begriff oder eine Zielrolle angeben.")
    boards = list(dict.fromkeys(args.greenhouse))
    if any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", b) for b in boards):
        raise ValueError("Board-Kennung aus der Greenhouse-URL angeben.")
    if not 1 <= args.seiten <= 20 or not 0 <= args.umkreis <= 200 or not 1 <= args.tage <= 100:
        raise ValueError("Seiten 1 bis 20, Tage 1 bis 100 und Umkreis 0 bis 200 km angeben.")
    known = {key: j for j in workspace.jobs() for key in (identity(j["url"]), j["identity"], *j.get("identity_aliases", []))}
    previous = {}
    for saved in sorted(workspace.path("exports").glob("Suchlauf-*.json")):
        for ad in rows(read(workspace.path(saved)), "treffer"):
            previous.setdefault(identity(ad["url"]), {}).update({k: ad[k] for k in (
                "role", "description", "location", "gehaltsangabe_der_anzeige", "arbeitsmodell", "anforderungen") if k in ad})
    found = {}
    coverage = []

    def collect(source, getter, **info):
        status = dict(quelle=source, status="abgerufen", treffer=0, **info)
        coverage.append(status)
        try:
            for ad in getter(status):
                key = identity(ad["url"])
                if key not in found:
                    found[key] = dict(**ad, bekannt=key in known, fundstellen=[])
                else:
                    for field in ("description", "anforderungen", "arbeitsmodell", "gehaltsangabe_der_anzeige"):
                        if field in ad:
                            found[key].setdefault(field, ad[field])
                # Unterschiedliche Fundquellen, Referenzen und Angaben zur selben URL erhalten.
                provenance = {k: v for k, v in ad.items() if k in ("indeed_url", "gesehen_am", "reference", "board")}
                link = {"quelle": source, "url": ad["url"], **info, **provenance}
                if link not in found[key]["fundstellen"]:
                    found[key]["fundstellen"].append(link)
                if ad.get("detailfehler"):
                    status["status"] = "teilweise"
                status["treffer"] += 1
        except (OSError, ValueError) as exc:
            status.update(status="teilweise" if status["treffer"] else "fehlgeschlagen", grund=str(exc))

    for term in terms:
        collect("BA", lambda status: list_ba(term, args.ort, args, status), begriff=term)
    for board in boards:
        collect("Greenhouse", lambda _: list_board(board, terms, args.ort, args.details), board=board)
    if not boards:
        coverage.append(dict(quelle="Greenhouse", status="kein Board gewählt"))
    if args.indeed_datei:
        collect("Indeed", lambda _: indeed_import(args.indeed_datei, terms, args.ort), zugang="Dateiimport")
    else:
        coverage.append(dict(quelle="Indeed", status="kein Suchergebnis importiert"))
    for index, ad in enumerate(found.values(), 1):
        ad["nummer"] = index
        key = identity(ad["url"])
        if key in known:
            basis = {**latest_fields(known[key]), **previous.get(key, {})}
            ad["aenderungen"] = changes(basis, ad)
            ad["vergleich_mit"] = known[key]["id"]
    report = dict(abgerufen_am=now(), begriffe=terms, ort=args.ort, abdeckung=coverage, treffer=list(found.values()))
    matched = {known[key]["id"] for key in found if key in known}
    report["nicht_wiedergefunden"] = sorted({j["id"] for j in known.values()} - matched)
    with workspace.locked():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = workspace.path("exports", "Suchlauf-" + stamp + ".json")
        if path.exists():
            raise ValueError("Namenskollision im Sucharchiv. Suchlauf erneut starten.")
        write(path, report)
    for status in coverage:
        print(f"{status['quelle']} {status.get('begriff') or status.get('board', '')}: {status['status']}"
              + (f" ({status['treffer']} Treffer)" if 'treffer' in status else "")
              + ("; " + status["grund"] if "grund" in status else ""))
    for ad in report["treffer"][:10]:
        print(f"{ad['nummer']}. {ad['role']} | {ad.get('company') or ad.get('board') or ''} | {ad['url']}")
        if ad.get("aenderungen"):
            print("   Änderungen zur bekannten Anzeige: " + ", ".join(ad["aenderungen"]))
    print(f"{len(found)} unterschiedliche Treffer. Bericht: {path}")
    return path


def fit(profile, job):
    match = keyword_match(profile, job["description"])
    roles = profile["target_roles"]
    title_hit = [role for role in roles if words_match([role], job["role"])]
    parts = {}
    if match["keyword_score"] is not None:
        parts["faktenabgleich"] = match["keyword_score"]
    skills = {f["id"]: f for f in profile["facts"] if f.get("kind") == "skill"}
    skill_hits = []
    corpus = job["description"].casefold()
    for fid, fact in skills.items():
        terms = fact.get("keywords") or [fact["text"]]
        if any(re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", corpus) for term in terms):
            skill_hits.append(fid)
    if skills:
        parts["kompetenzen_im_text"] = round(100 * len(skill_hits) / len(skills))
    if roles:
        parts["zielrolle_im_titel"] = 100 if title_hit else 0
    weights = {"faktenabgleich": 55, "kompetenzen_im_text": 25, "zielrolle_im_titel": 20}
    auto = None
    if match["keyword_score"] is not None or skills:
        auto = round(sum(v * weights[k] for k, v in parts.items()) / sum(weights[k] for k in parts))
    manual = job.get("score_manual")
    if manual is not None and (type(manual) is not int or not 0 <= manual <= 100):
        raise ValueError("Ungültiger gespeicherter manueller Score.")
    return dict(id=job["id"], score=manual if manual is not None else auto, score_manuell=manual,
                begruendung_manuell=job.get("score_reason"), score_automatisch=auto, anteile=parts,
                zielrollentreffer=title_hit, kompetenztreffer=skill_hits, fakten_treffer=match["matched_fact_ids"],
                fakten_ohne_worttreffer=match["unmatched_fact_ids"], kriterien_zur_pruefung={
                    k: v for k, v in profile.get("preferences", {}).items()
                    if k in ("must_haves", "salary", "mobility", "work_model") and v})


def atlas(kldb, region, level):
    if not re.fullmatch(r"[0-9]{5}", kldb) or region < 1:
        raise ValueError("Fünfstelligen Berufscode und positive Regions-ID angeben.")
    key = os.environ.get("BA_ENTGELTATLAS_API_KEY")
    if not key:
        raise ValueError("BA_ENTGELTATLAS_API_KEY fehlt.")
    address = ATLAS + kldb + "?" + urlencode(dict(l=level, r=region, g=1, a=1, b=1))
    data = fetch(address, key)
    if not isinstance(data, list):
        raise ValueError("Entgeltatlas-Antwort hat ein unbekanntes Format.")
    result = []
    for entry in data:
        if not isinstance(entry, dict) or not {"entgelt", "entgeltQ25", "entgeltQ75"}.intersection(entry):
            raise ValueError("Entgeltatlas-Kennzahlen fehlen.")
        values = {}
        for metric, field in (("Median", "entgelt"), ("Q25", "entgeltQ25"), ("Q75", "entgeltQ75")):
            number = entry.get(field)
            if number is not None and (type(number) not in (int, float) or not float("-inf") < number < float("inf")):
                raise ValueError("Unerwartetes Zahlenformat im Entgeltatlas.")
            values[metric] = {"monat_eur": number, "hochrechnung_jahr_eur": number * 12} if number and number > 0 else None
        result.append({"kennzahlen": values, "quellwerte": {f: entry[f] for f in ("entgelt", "entgeltQ25", "entgeltQ75") if f in entry},
                       "besetzung_laut_quelle": entry.get("besetzung")})
    return dict(quelle=address, kldb=kldb, regions_id=region, anforderungsniveau=level, abrufdatum=date.today().isoformat(),
                basis="Vollzeit, monatlich brutto, alle Geschlechter und Altersgruppen", ergebnisse=result)


def register(commands):
    find = commands.add_parser("suchlauf", help="BA und gewählte Greenhouse-Boards abrufen, Indeed-Funde einlesen")
    find.add_argument("--begriff", action="append", default=[], help="Zielrolle, wiederholbar. Standard: Zielrollen im Profil.")
    find.add_argument("--ort", default="", help="Suchregion, leer für alle Standorte")
    find.add_argument("--greenhouse", action="append", default=[], metavar="BOARD")
    find.add_argument("--indeed-datei", type=Path, help="Geprüfte Indeed-Funde als JSON, Format in docs/RECHERCHE.md")
    find.add_argument("--seiten", type=int, default=1, help="Maximale BA-Seiten pro Begriff")
    find.add_argument("--umkreis", type=int, default=25, help="BA-Radius in km bei Ortsangabe")
    find.add_argument("--tage", type=int, default=14, help="BA-Veröffentlichungsfenster in Tagen")
    find.add_argument("--details", action="store_true", help="Anzeigentexte bei BA und Greenhouse zusätzlich abrufen")
    take = commands.add_parser("suchfund", help="Gelesenen Treffer aus dem Suchbericht in Bewerbungen übernehmen")
    take.add_argument("bericht", help="Dateiname des Suchberichts im Ordner exports")
    take.add_argument("nummer", type=int, help="Treffernummer aus dem Bericht, ab 1")
    take.add_argument("--firma", help="Geprüfter Arbeitgebername, bei Greenhouse-Boards erforderlich")
    take.add_argument("--textdatei", type=Path, help="Gelesener Volltext, wenn im Bericht nur ein Kurztreffer steht")
    observe = commands.add_parser("anzeigenstand", help="Eine geprüfte Änderung, Schließung oder Zugriffslücke zur Stelle dokumentieren")
    observe.add_argument("id")
    observe.add_argument("--zustand", choices=("offen", "geschlossen", "zugang_offen"), required=True)
    observe.add_argument("--quelle", required=True, help="Geprüfter Original-Link")
    observe.add_argument("--beleg", required=True, help="Gelesene Aussage zur Stelle bzw. konkreter Zugangsfehler")
    observe.add_argument("--textdatei", type=Path, help="Gelesener voller Anzeigentext")
    for field in ("anforderungen", "arbeitsmodell", "gehalt"):
        observe.add_argument("--" + field)
    observe.add_argument("--uebernehmen", action="store_true", help="Geprüften neuen Volltext in dieser Stelle verwenden")
    score = commands.add_parser("passung", help="Zielrolle und belegte Fakten mit Anzeigen vergleichen")
    group = score.add_mutually_exclusive_group(required=True)
    group.add_argument("--id")
    group.add_argument("--alle", action="store_true")
    pay = commands.add_parser("entgeltatlas", help="Regionale Bruttomonatswerte direkt bei der BA abrufen")
    pay.add_argument("--kldb", required=True)
    pay.add_argument("--region", type=int, default=1, help="Regions-ID der Quelle, 1 steht für Deutschland")
    pay.add_argument("--niveau", type=int, required=True, choices=range(1, 5))
    pay.add_argument("--id", help="Marktvergleich zusätzlich an dieser gespeicherten Stelle ablegen")
    band = commands.add_parser("gehaltsband", help="Belegte Arbeitgeberangabe mit Bezugsbasis speichern")
    band.add_argument("id")
    band.add_argument("--von")
    band.add_argument("--bis")
    band.add_argument("--zeitraum", required=True, choices=("Stunde", "Monat", "Jahr"))
    band.add_argument("--waehrung", required=True)
    band.add_argument("--basis", required=True, help="Zum Beispiel Fixum, 40 Wochenstunden, brutto")
    band.add_argument("--quelle", required=True, help="Quelle der Arbeitgeberangabe für genau diese Stelle")
    band.add_argument("--stand", required=True, help="Datum der Angabe bzw. Sichtung, JJJJ-MM-TT")


def save_band(workspace, a):
    if not (a.von or a.bis):
        raise ValueError("Mindestens eine belegte Grenze angeben.")
    amounts = {}
    for label, raw in (("von", a.von), ("bis", a.bis)):
        if raw is not None:
            if not re.fullmatch(r"[0-9]{1,9}(?:[.,][0-9]{1,2})?", raw) or Decimal(raw.replace(",", ".")) <= 0:
                raise ValueError("Positive Beträge ohne Tausendertrennzeichen angeben.")
            amounts[label] = Decimal(raw.replace(",", "."))
    if len(amounts) == 2 and amounts["von"] > amounts["bis"]:
        raise ValueError("Untergrenze liegt über der Obergrenze.")
    if not re.fullmatch(r"[a-zA-Z]{3}", a.waehrung):
        raise ValueError("Dreistelligen Währungscode angeben.")
    stamp = date.fromisoformat(a.stand)
    if stamp > date.today():
        raise ValueError("Stand der Angabe liegt in der Zukunft.")
    description = " ".join(f"{k} {v:f}" for k, v in amounts.items())
    workspace.add_note(a.id, "arbeitgeberband", "Gehaltsrahmen des Arbeitgebers",
                       f"{description} {a.waehrung.upper()} pro {a.zeitraum}. {text(a.basis, 'Bezugsbasis')}. Stand {stamp}.",
                       [a.quelle])


def run(args, workspace):
    if args.command == "suchlauf":
        search(workspace, args)
    elif args.command == "suchfund":
        if not re.fullmatch(r"Suchlauf-[0-9]{8}T[0-9]{12}Z\.json", args.bericht):
            raise ValueError("Dateinamen des Suchberichts aus exports angeben.")
        report = read(workspace.path("exports", args.bericht))
        listings = rows(report, "treffer")
        if not 1 <= args.nummer <= len(listings) or not isinstance(listings[args.nummer - 1], dict):
            raise ValueError("Treffernummer fehlt im Bericht.")
        ad = listings[args.nummer - 1]
        company = text(args.firma or ad.get("company"), "Geprüfter Arbeitgebername (--firma)", 300)
        description = args.textdatei.read_text(encoding="utf-8-sig") if args.textdatei else ad.get("description")
        text(description, "Vollständiger Anzeigentext (--textdatei)", 200000)
        sources = rows(ad, "fundstellen")
        links = [url(link[field]) for link in sources if isinstance(link, dict)
                 for field in ("url", "indeed_url") if field in link]
        stamp = text(report.get("abgerufen_am"), "Berichtsdatum", 100)
        provenance = text(json.dumps(sources, ensure_ascii=False, indent=2), "Fundstellen", 50000)
        job, created = workspace.add(company, ad.get("role"), ad.get("url"), description, ad.get("reference", ""))
        workspace.add_note(job["id"], "screening", "Fundstellen im Suchlauf " + stamp, provenance, links)
        print(job["id"] + (" neu erfasst." if created else " bereits erfasst.") + " Fundstellen gespeichert.")
    elif args.command == "anzeigenstand":
        fields = {}
        for key, value in (("anforderungen", args.anforderungen), ("arbeitsmodell", args.arbeitsmodell),
                           ("gehaltsangabe_der_anzeige", args.gehalt)):
            if value is not None:
                fields[key] = text(value, key)
        if args.textdatei is not None:
            fields["description"] = text(args.textdatei.read_text(encoding="utf-8-sig"), "Volltext", 200000)
        print(json.dumps(save_observation(workspace, args.id, args.zustand, args.quelle, args.beleg, fields, args.uebernehmen),
                         ensure_ascii=False, indent=2))
    elif args.command == "passung":
        jobs = workspace.jobs()
        profile = workspace.profile()
        scores = [fit(profile, j) for j in (jobs if args.alle else [workspace.job(jobs, args.id)])]
        scores.sort(key=lambda s: s["score"] if s["score"] is not None else -1, reverse=True)
        print(json.dumps(scores, ensure_ascii=False, indent=2))
    elif args.command == "entgeltatlas":
        result = atlas(args.kldb, args.region, args.niveau)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.id and result["ergebnisse"]:
            workspace.add_note(args.id, "marktvergleich", f"Entgeltatlas {args.kldb}, Region {args.region}, Niveau {args.niveau}",
                               output, [result["quelle"]])
        print(output)
    elif args.command == "gehaltsband":
        save_band(workspace, args)
        print("Gehaltsangabe des Arbeitgebers gespeichert.")
    else:
        return False
    return True
