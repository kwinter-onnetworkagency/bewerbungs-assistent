"""Öffentliche Stellenquellen, lokale Passungsprüfung und belegte Gehaltsangaben."""
import base64
from datetime import date, datetime, timezone
from decimal import Decimal
from difflib import unified_diff
import hashlib
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


STRUCTURE = ("titel", "senioritaet", "ort", "sprache", "gehalt", "erfahrung", "musskriterium")
STOP_WORDS = set("""aber als also am an and are at auf aus bei bieten by das dem den der des die du durch ein eine
einem einen einer eines erfahrung erfahrungen experience for from fuer für haben has im in ist it
job kann mit nach oder of on our position role seeking sie sind sowie suchen that the to und uns unser unsere
unserem unseren unserer unter von we welche werden who wie wir with wird you your zum zur""".split())


def tokens(value):
    return {w for w in re.findall(r"[^\W_]+", value.casefold()) if len(w) >= 3 and not w.isdigit() and w not in STOP_WORDS}


def assessment_source(profile, job):
    prefs = profile.get("preferences", {})
    relevant = {k: v for k, v in prefs.items() if k in ("seniority", "salary", "work_model", "mobility", "must_haves", "exceptions")}
    basis = [job["description"], job["role"], profile.get("location"), profile["facts"], relevant, profile["target_roles"]]
    return hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def record_structure(workspace, a):
    quote_text = text(a.anzeige, "Anzeigenpassage")
    reason = text(a.grund, "Abgleich und Grundlage")
    name = text(a.name or a.kriterium, "Kriterium", 180)
    years = a.gefordert_jahre, a.belegt_jahre
    if any(n is not None for n in years):
        if (a.kriterium != "erfahrung" or not a.fakt or any(n is None or n < 0 for n in years)):
            raise ValueError("Erfahrungsjahre benötigen beide Werte und eine belegte Fakten-ID.")
        calculated = "passt" if years[1] >= years[0] else "luecke"
        if a.urteil and a.urteil not in (calculated, "ausnahme"):
            raise ValueError("Das Urteil widerspricht den angegebenen Erfahrungsjahren.")
        verdict = a.urteil or calculated
    else:
        verdict = a.urteil
    if verdict is None:
        raise ValueError("Prüfurteil oder belegten Jahresvergleich angeben.")
    with workspace.locked():
        jobs = workspace.jobs()
        job = workspace.job(jobs, a.id)
        profile = workspace.profile()
        if " ".join(quote_text.split()) not in " ".join(job["description"].split()):
            raise ValueError("Anzeigenpassage fehlt im aktuellen Originaltext.")
        if set(a.fakt) - {f["id"] for f in profile["facts"]}:
            raise ValueError("Fakten-ID fehlt im Profil.")
        if a.kriterium in ("musskriterium", "erfahrung") and verdict in ("passt", "luecke") and not a.fakt:
            raise ValueError("Belegte Passung oder Lücke benötigt eine passende bestätigte Fakten-ID.")
        row = dict(kriterium=a.kriterium, name=name, urteil=verdict, anzeige=quote_text, grund=reason,
                   fakten=list(dict.fromkeys(a.fakt)), basis=assessment_source(profile, job))
        if years[0] is not None:
            row.update(gefordert_jahre=years[0], belegt_jahre=years[1])
        history = job.setdefault("strukturpruefungen", [])
        previous = next((r for r in reversed(history) if (r["kriterium"], r["name"]) == (a.kriterium, name)), {})
        if any(previous.get(k) != v for k, v in row.items()) or ("gefordert_jahre" in previous) != ("gefordert_jahre" in row):
            history.append(dict(row, erfasst=now()))
            write(workspace.path("bewerbungen.json"), jobs)


def experience_checks(profile, job):
    fields = profile.get("preferences", {}).get("erfahrungsfelder", {})
    if not isinstance(fields, dict):
        raise ValueError("erfahrungsfelder benötigt Namen mit zugehörigen Begriffen.")
    results = []
    for name, terms in fields.items():
        if not isinstance(terms, list) or not choice_list(terms):
            raise ValueError("Ein Erfahrungsfeld benötigt mindestens einen Begriff.")
        terms_re = "|".join(re.escape(term) for term in terms)
        years = rf"(\d{{1,2}})\+?\s+(?:Jahre[n]?|years?)\s+(?:(?:mit|in|of)\s+)?(?:{terms_re})\b"
        def collect(value, prefix):
            matches = []
            for sentence in re.split(r"[.!?;\n]", value):
                if re.search(r"\b(?:kein\w*|nicht|wünschenswert|höchstens|optional|preferred|not|pluspunkt)\b", sentence, re.I):
                    continue
                matches.extend((int(m[1]), m[0]) for m in re.finditer(prefix + years, sentence, re.I))
            return matches
        requested = collect(job["description"], r"\b(?:mindestens|minimum of|at least)\s+")
        if not requested:
            continue
        required, phrase = max(requested)
        proofs = [(years, f["id"]) for f in profile["facts"] for years, _ in collect(f["text"], r"(?<![\w.,])")]
        proven = max((n for n, _ in proofs), default=None)
        verdict = "offen" if proven is None else ("passt" if proven >= required else "luecke")
        results.append(dict(kriterium="erfahrung", name=name, urteil=verdict, aktuell=True, anzeige=phrase,
                            grund="Vergleich ausdrücklich genannter Mindest- und belegter Erfahrungsjahre.",
                            geforderte_basis="ausdrueckliche_mindestanforderung", gefordert_jahre=required,
                            belegt_jahre=proven, fakten=[fid for n, fid in proofs if n == proven], automatisch=True))
    return results


def structure(profile, job, title_hit):
    configured = profile.get("preferences", {}).get("strukturgewichte", {})
    if (not isinstance(configured, dict) or configured.keys() - set(STRUCTURE) or
            any(type(n) is not int or not 0 <= n <= 100 for n in configured.values())):
        raise ValueError("strukturgewichte benötigt bekannte Faktoren mit ganzzahligen Gewichten von 0 bis 100.")
    weights = {k: configured.get(k, 1) for k in STRUCTURE}
    scores = {"titel": 100 if title_hit else 0} if profile["target_roles"] else {}
    result = []
    source = assessment_source(profile, job)
    latest = {(r["kriterium"], r["name"]): r for r in job.get("strukturpruefungen", [])}
    for item in experience_checks(profile, job):
        latest.setdefault(("erfahrung", item["name"]), dict(item, basis=source))
    for factor in STRUCTURE[1:]:
        values = []
        for (key, _), row in latest.items():
            if key != factor:
                continue
            fresh = source == row["basis"]
            verdict = row["urteil"] if fresh else "offen"
            result.append({**{k: v for k, v in row.items() if k != "basis"}, "urteil": verdict, "aktuell": fresh})
            if verdict != "offen":
                values.append(0 if verdict == "luecke" else 100)
        if values:
            scores[factor] = sum(values) / len(values)
    denominator = sum(weights[k] for k in scores)
    value = round(sum(scores[k] * weights[k] for k in scores) / denominator) if denominator else None
    unknown = [k for k in STRUCTURE if weights[k] and k not in scores]
    return dict(wert=value, gewichte=weights, faktorwerte=scores, offen=unknown, pruefungen=result)


def fit(profile, job):
    match = keyword_match(profile, job["description"])
    roles = profile["target_roles"]
    title_hit = [role for role in roles if words_match([role], job["role"])]
    parts = {}
    ad_terms = tokens(job["description"])
    cv_terms = set()
    for fact in profile["facts"]:
        translations = fact.get("translations")
        translated = (t for t in translations.values() if isinstance(t, str)) if isinstance(translations, dict) else ()
        for phrase in (fact["text"], *fact.get("keywords", []), *translated):
            cv_terms.update(tokens(phrase))
    if ad_terms and cv_terms:
        parts["faktenabgleich"] = round(100 * len(ad_terms & cv_terms) / len(ad_terms))
    skills = {f["id"]: f for f in profile["facts"] if f.get("kind") == "skill"}
    skill_hits = []
    corpus = job["description"].casefold()
    for fid, fact in skills.items():
        terms = fact.get("keywords") or [fact["text"]]
        if any(re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", corpus) for term in terms):
            skill_hits.append(fid)
    if skills:
        parts["kompetenzen_im_text"] = round(100 * len(skill_hits) / len(skills))
    reviewed = structure(profile, job, title_hit)
    if reviewed["wert"] is not None:
        parts["struktur"] = reviewed["wert"]
    weights = {"faktenabgleich": 55, "kompetenzen_im_text": 25, "struktur": 20}
    auto = None
    if "faktenabgleich" in parts or skills:
        auto = round(sum(v * weights[k] for k, v in parts.items()) / sum(weights[k] for k in parts))
    manual = job.get("score_manual")
    if manual is not None and (type(manual) is not int or not 0 <= manual <= 100):
        raise ValueError("Ungültiger gespeicherter manueller Score.")
    return dict(id=job["id"], score=manual if manual is not None else auto, score_manuell=manual,
                begruendung_manuell=job.get("score_reason"), score_automatisch=auto, anteile=parts,
                struktur=reviewed, anzeigenbegriffe_im_cv=sorted(ad_terms & cv_terms),
                anzeigenbegriffe_ohne_worttreffer=sorted(ad_terms - cv_terms),
                zielrollentreffer=title_hit, kompetenztreffer=skill_hits, fakten_treffer=match["matched_fact_ids"],
                fakten_ohne_worttreffer=match["unmatched_fact_ids"], kriterien_zur_pruefung={
                    k: v for k, v in profile.get("preferences", {}).items()
                    if k in ("must_haves", "salary", "mobility", "work_model", "seniority", "exceptions") and v})


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
    weekly = commands.add_parser("wochenlauf", help="Suchlauf mit bestätigten Funden, Passung, Entgeltatlas und Dashboard")
    weekly.add_argument("--plan", type=Path, required=True, help="Persönliche JSON-Datei mit Freigaben und Gehaltsclustern")
    weekly.add_argument("--bericht", help="Vorhandenen Suchlauf aus exports nach der Sichtung weiterverarbeiten")
    for find in (find, weekly):
        find.add_argument("--begriff", action="append", default=[], help="Zielrolle, wiederholbar. Standard: Zielrollen im Profil.")
        find.add_argument("--ort", default="", help="Suchregion, leer für alle Standorte")
        find.add_argument("--greenhouse", action="append", default=[], metavar="BOARD")
        find.add_argument("--indeed-datei", type=Path, help="Geprüfte Indeed-Funde als JSON, Format in docs/RECHERCHE.md")
        find.add_argument("--seiten", type=int, default=1, help="Maximale BA-Seiten pro Begriff")
        find.add_argument("--umkreis", type=int, default=25, help="BA-Radius in km bei Ortsangabe")
        find.add_argument("--tage", type=int, default=14, help="BA-Veröffentlichungsfenster in Tagen")
        find.add_argument("--details", action="store_true", help="Anzeigentexte bei BA und Greenhouse zusätzlich abrufen")
    weekly.set_defaults(details=True)
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
    check = commands.add_parser("strukturcheck", help="Strukturfaktor, Erfahrungslücke oder persönliche Stellenausnahme belegen")
    check.add_argument("id")
    check.add_argument("--kriterium", choices=STRUCTURE[1:], required=True)
    check.add_argument("--name", help="Eine einzelne Anforderung innerhalb des Faktors benennen")
    check.add_argument("--anzeige", required=True, help="Wörtliche Passage der gespeicherten Anzeige")
    check.add_argument("--grund", required=True, help="Persönliche Grundlage der Prüfung oder bewussten Ausnahme")
    check.add_argument("--urteil", choices=("passt", "luecke", "offen", "ausnahme"))
    check.add_argument("--fakt", action="append", default=[])
    check.add_argument("--gefordert-jahre", type=int)
    check.add_argument("--belegt-jahre", type=int)
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


def load_run(workspace, name):
    if not re.fullmatch(r"Suchlauf-[0-9]{8}T[0-9]{12}Z\.json", name):
        raise ValueError("Dateinamen des Suchberichts aus exports angeben.")
    return read(workspace.path("exports", name))


def weekly_run(workspace, args):
    from .export import report as build_dashboard
    plan = read(args.plan)
    if not isinstance(plan, dict) or plan.keys() - {"bestaetigt", "gehaltscluster"}:
        raise ValueError("Wochenplan benötigt die dokumentierten Schlüssel.")
    approved, clusters = {}, plan.get("gehaltscluster", [])
    if not isinstance(clusters, list) or not isinstance(plan.get("bestaetigt", []), list):
        raise ValueError("bestaetigt und gehaltscluster müssen Listen sein.")
    for row in plan.get("bestaetigt", []):
        if not isinstance(row, dict) or set(row) != {"url", "firma", "textdatei", "gesehen_am"}:
            raise ValueError("Jede Freigabe benötigt url, firma, textdatei und gesehen_am.")
        key = identity(row["url"])
        if key in approved or date.fromisoformat(row["gesehen_am"]) > date.today():
            raise ValueError("Doppelte oder zukünftige Sichtung.")
        path = workspace.path(row["textdatei"])
        approved[key] = (text(row["firma"], "Geprüfter Firmenname", 300),
                         text(path.read_text(encoding="utf-8-sig"), "Gelesener Originaltext", 200000),
                         row["gesehen_am"])
    for cluster in clusters:
        if (not isinstance(cluster, dict) or set(cluster) != {"titelbegriffe", "kldb", "region", "niveau"}
                or not isinstance(cluster["titelbegriffe"], list) or not choice_list(cluster["titelbegriffe"])
                or type(cluster["region"]) is not int or cluster["region"] < 1
                or type(cluster["niveau"]) is not int or cluster["niveau"] not in range(1, 5)
                or not isinstance(cluster["kldb"], str) or not re.fullmatch(r"[0-9]{5}", cluster["kldb"])):
            raise ValueError("Ungültiger Gehaltscluster. Titelbegriffe, Berufscode, Region und Niveau prüfen.")
    name = args.bericht or search(workspace, args).name
    found = load_run(workspace, name)
    data = dict(suchbericht=name, stand=now(), abdeckung=found["abdeckung"], bestaetigt=[], ungesichtet=[], gehaltsquellen=[])
    profile = workspace.profile()
    known = {key: job for job in workspace.jobs() for key in (identity(job["url"]), *job.get("identity_aliases", []))}
    market = {}
    for ad in rows(found, "treffer"):
        key = identity(ad["url"])
        job = known.get(key)
        seen = approved.get(key)
        current = ad.get("description")
        checked_text = seen[1] if seen else (job or {}).get("description")
        reason = None
        if not checked_text:
            reason = "Originalanzeige noch nicht bestätigt"
        elif current and " ".join(checked_text.split()) != " ".join(current.split()):
            reason = "Abweichender Volltext benötigt erneute Sichtung"
        elif not seen and ad.get("aenderungen"):
            reason = "Geänderte Anzeigenangaben benötigen erneute Sichtung"
        elif not seen and not current:
            reason = "Aktueller Volltext fehlt"
        elif seen and job and checked_text != job["description"]:
            reason = "Geänderte Anzeige zuerst mit anzeigenstand übernehmen"
        if reason:
            data["ungesichtet"].append(dict(nummer=ad["nummer"], url=ad["url"], grund=reason))
            continue
        if seen:
            company, description, date_seen = seen
            job, _ = workspace.add(company, ad["role"], ad["url"], description, ad.get("reference", ""))
            workspace.add_note(job["id"], "screening", "Bestätigter Wochenfund", f"Original gelesen am {date_seen}.", [ad["url"]])
        score = fit(profile, job)
        record = dict(id=job["id"], url=ad["url"], bewerbungsstatus=job["status"], passung=score, gehaltscluster=[])
        for cluster in clusters:
            if not words_match(cluster["titelbegriffe"], job["role"]):
                continue
            dimensions = (cluster["kldb"], cluster["region"], cluster["niveau"])
            if dimensions not in market:
                try:
                    result = atlas(*dimensions)
                    market[dimensions] = dict(cluster=cluster, status="abgerufen" if result["ergebnisse"] else "leer", daten=result)
                except (ValueError, OSError) as exc:
                    market[dimensions] = dict(cluster=cluster, status="zugang_offen", grund=str(exc))
                data["gehaltsquellen"].append(market[dimensions])
            outcome = market[dimensions]
            record["gehaltscluster"].append(dict(kldb=dimensions[0], region=dimensions[1], niveau=dimensions[2], status=outcome["status"]))
            if outcome["status"] == "abgerufen":
                result = outcome["daten"]
                workspace.add_note(job["id"], "marktvergleich", f"Entgeltatlas {dimensions[0]}, Region {dimensions[1]}, Niveau {dimensions[2]}",
                                   json.dumps(result, ensure_ascii=False, indent=2), [result["quelle"]])
        data["bestaetigt"].append(record)
    build_dashboard(workspace)
    with workspace.locked():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = workspace.path("exports", "Wochenlauf-" + stamp + ".json")
        if dest.exists():
            raise ValueError("Namenskollision im Wochenarchiv. Erneut starten.")
        write(dest, data)
    print(f'{len(data["bestaetigt"])} bestätigte Treffer, {len(data["ungesichtet"])} offen. Quellenabdeckung im Bericht.')
    print(dest)
    print(workspace.path("exports", "Dashboard.html"))
    return dest


def run(args, workspace):
    if args.command == "suchlauf":
        search(workspace, args)
    elif args.command == "wochenlauf":
        weekly_run(workspace, args)
    elif args.command == "suchfund":
        report = load_run(workspace, args.bericht)
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
    elif args.command == "strukturcheck":
        record_structure(workspace, args)
        print("Strukturprüfung gespeichert.")
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
