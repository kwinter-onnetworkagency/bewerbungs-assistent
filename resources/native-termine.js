// Ausführung nur bei ausdrücklich gewähltem --mac über osascript -l JavaScript.
// Die Koordination lässt sich ohne laufende macOS-Apps gegen einen Testbestand ausführen.
'use strict';

function phoneLabel(value) {
  return String(value || '').toLowerCase().replace(/[^a-z]/g, '');
}

function matchesContact(request, person) {
  const fields = Object.entries(request.fields).every(([k, v]) => person.fields[k] === v);
  const email = person.emails.some(v => v.toLowerCase() === request.email.toLowerCase());
  const phones = request.phones.every(phone => person.phones.some(p =>
    phoneLabel(p.label) === phoneLabel(phone.label) && p.value === phone.value));
  const address = !Object.keys(request.address).length || person.addresses.some(a =>
    Object.entries(request.address).every(([key, value]) => a[key] === value));
  return fields && email && phones && address && (!request.website || person.website === request.website);
}

function matchesEvent(request, event) {
  return event.title === request.title && event.start === Date.parse(request.start) &&
    event.end === Date.parse(request.end) && event.description === request.description &&
    event.location === request.location && event.status === request.status && event.mark === request.uid &&
    !event.external;
}

function synchronize(request, store) {
  const matches = store.find();
  if (matches.length > 1) throw Error('Mehrere native Kandidaten gefunden. Dubletten persönlich prüfen.');
  const existing = matches[0];
  if (request.previous && (!existing || existing.id !== request.previous)) {
    throw Error('Die bereits geprüfte native ID fehlt oder zeigt auf einen anderen Datensatz.');
  }
  const matchesRequested = request.kind === 'contact' ? matchesContact : matchesEvent;
  let id;
  if (!existing) {
    id = store.create();
  } else if (matchesRequested(request, existing)) {
    id = existing.id;
  } else {
    if (!request.update || (request.previous !== existing.id && !(request.kind === 'event' && existing.mark === request.uid))) {
      throw Error('Ähnlicher oder abweichender Datensatz vorhanden. Zuordnung und Änderungen persönlich prüfen.');
    }
    if (existing.external) throw Error('Termin mit Teilnehmenden oder Wiederholung ausschließlich persönlich bearbeiten.');
    id = store.update(existing.id);
  }
  // Frischer Abruf der App nach dem Speichern; lokale Schreibobjekte liefern keinen Nachweis.
  const result = store.find();
  if (result.length !== 1 || result[0].id !== id || !matchesRequested(request, result[0])) {
    throw Error('Rücklesen nicht eindeutig oder Angaben abweichend. Bestand vor erneutem Versuch prüfen.');
  }
  return {id, verified:true};
}

function calendarStore(q) {
  const app = Application('Calendar');
  const calendars = app.calendars.whose({name:q.calendar})();
  if (calendars.length !== 1 || !calendars[0].writable()) throw Error('Zielkalender nicht eindeutig oder schreibgeschützt.');
  const calendar = calendars[0];
  const marker = 'urn:uuid:' + q.uid;
  const value = x => typeof x === 'string' ? x : '';
  function snapshot(event) {
    const mark = value(event.url());
    return {id:String(event.uid()), title:value(event.summary()), start:event.startDate().getTime(), end:event.endDate().getTime(),
      description:value(event.description()), location:value(event.location()), status:String(event.status()),
      mark:mark === marker ? q.uid : '', external:event.attendees().length > 0 || Boolean(value(event.recurrence()))};
  }
  function byUid(id) {
    const matches = calendar.events.whose({uid:id})();
    if (matches.length !== 1) throw Error('Nativer Termin ist nicht eindeutig.');
    return matches[0];
  }
  return {
    find() {
      const records = new Map();
      const collect = events => events.forEach(item => records.set(String(item.uid()),item));
      if(q.previous) collect(calendar.events.whose({uid:q.previous})());
      collect(calendar.events.whose({url:marker})());
      // Ein manuell importierter Termin kann dieselbe fachliche Identität ohne App-Markierung besitzen.
      const near = calendar.events.whose({summary:q.title})().filter(item => item.startDate().getTime() === Date.parse(q.start));
      collect(near);
      return Array.from(records.values(),snapshot);
    },
    create() {
      const event = app.Event({summary:q.title, startDate:new Date(q.start), endDate:new Date(q.end),
        description:q.description, location:q.location, status:q.status, url:marker});
      calendar.events.push(event);
      return String(event.uid());
    },
    update(id) {
      const e = byUid(id);
      if (snapshot(e).external) throw Error('Fremdteilnehmende oder Terminserie erkannt.');
      const start = new Date(q.start), end = new Date(q.end);
      if (start >= e.endDate()) { e.endDate = end; e.startDate = start; }
      else { e.startDate = start; e.endDate = end; }
      e.summary = q.title; e.location = q.location; e.description = q.description; e.status = q.status;
      return id;
    },
  };
}

function contactsStore(q) {
  const app = Application('Contacts');
  const string = v => typeof v === 'string' ? v : '';
  function snapshot(p) {
    const fields = {};
    Object.keys(q.fields).forEach(k => {fields[k] = string(p[k]());});
    return {id:String(p.id()), fields, emails:p.emails().map(e=>string(e.value())),
      phones:p.phones().map(phone=>({label:string(phone.label()),value:string(phone.value())})),
      addresses:p.addresses().map(addr=>{
        const values={};
        Object.keys(q.address).forEach(k=>{values[k]=string(addr[k]());});
        return values;
      }),website:string(p.homePage())};
  }
  function apply(p) {
    const known = snapshot(p);
    Object.entries(q.fields).forEach(([k,v])=>{if (known.fields[k] !== v) p[k] = v;});
    if (!known.emails.some(v=>v.toLowerCase() === q.email.toLowerCase())) {
      p.emails.push(app.Email({label:'work',value:q.email}));
    }
    for(const phone of q.phones) if(!known.phones.some(other=>phoneLabel(other.label) === phoneLabel(phone.label) && other.value === phone.value)) {
      p.phones.push(app.Phone(phone));
    }
    if(Object.keys(q.address).length && !known.addresses.some(a=>Object.entries(q.address).every(([k,v])=>a[k] === v))) {
      p.addresses.push(app.Address(Object.assign({label:'work'},q.address)));
    }
    if(q.website && known.website !== q.website) p.homePage=q.website;
    app.save();
    return String(p.id());
  }
  return {
    find() {
      const matches=[];
      for(const p of app.people()) {
        const byEmail = p.emails().some(v=>string(v.value()).toLowerCase() === q.email.toLowerCase());
        // Gleicher Name und gleiche Firma ohne passende E-Mail sind eine ungeklärte Dublette.
        const byName = string(p.firstName()) === (q.fields.firstName || '') &&
          string(p.lastName()) === (q.fields.lastName || '') && string(p.organization()) === q.fields.organization;
        if(byEmail || byName || (q.previous && String(p.id()) === q.previous)) matches.push(snapshot(p));
        if(matches.length > 1) break;
      }
      return matches;
    },
    create() {
      const p=app.Person(q.fields);
      app.people.push(p);
      return apply(p);
    },
    update(id) {
      const candidates=app.people.whose({id:id})();
      if(candidates.length !== 1) throw Error('Native Kontakt-ID fehlt.');
      return apply(candidates[0]);
    },
  };
}

function run() {
  ObjC.import('Foundation');
  const raw = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
  const q = JSON.parse(ObjC.unwrap($.NSString.alloc.initWithDataEncoding(raw,$.NSUTF8StringEncoding)));
  if (!['event','contact'].includes(q.kind)) throw Error('Unbekannter nativer Auftrag.');
  return JSON.stringify(synchronize(q, q.kind === 'event' ? calendarStore(q) : contactsStore(q)));
}

if (typeof module !== 'undefined') module.exports={synchronize};
