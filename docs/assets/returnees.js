const byId = id => document.getElementById(id);
const siteRoot = new URL('../', import.meta.url);
const datasetUrl = new URL('data/returnees.json', siteRoot);
const workbookUrl = new URL('data/returnees.xlsx', siteRoot);
let dataset = null;
let loading = false;

function syncNavigation() {
  document.querySelectorAll?.('.brand')?.forEach(a => { a.href = new URL('./', siteRoot).href; });
  document.querySelectorAll?.('nav a')?.forEach(a => {
    const text = a.textContent?.trim();
    if (text === 'Sending') a.href = new URL('sending/', siteRoot).href;
    else if (text === 'Awayees') a.href = new URL('awayees/', siteRoot).href;
    else if (text === 'Hostees') a.href = new URL('hostees/', siteRoot).href;
    else if (text === 'Gastfamilien') a.href = new URL('families/', siteRoot).href;
    else if (text === 'Returnees') a.href = new URL('returnees/', siteRoot).href;
  });
}

function validDataset(data) {
  if (!data || data.version !== 1 || data.scope !== 'afser-accessible' || !Array.isArray(data.records) || !Array.isArray(data.archiveMonths) || !/^[a-f0-9]{64}$/.test(data.generation || '') || typeof data.updatedAt !== 'string' || !Number.isFinite(Date.parse(data.updatedAt))) return false;
  const ids = new Set();
  for (const row of data.records) {
    if (!row || Object.keys(row).sort().join(',') !== 'allCampsCompleted,id,seminar1Completed,seminar2Completed,year' || !/^[a-f0-9]{20}$/.test(row.id) || ids.has(row.id)) return false;
    if (row.year !== null && (!Number.isInteger(row.year) || row.year < 1900 || row.year > 2100)) return false;
    if (typeof row.seminar1Completed !== 'boolean' || typeof row.seminar2Completed !== 'boolean' || typeof row.allCampsCompleted !== 'boolean' || row.allCampsCompleted !== (row.seminar1Completed && row.seminar2Completed)) return false;
    ids.add(row.id);
  }
  return data.archiveMonths.every(month => typeof month === 'string' && /^20\d{2}-(0[1-9]|1[0-2])$/.test(month)) && data.archiveMonths.join(',') === [...new Set(data.archiveMonths)].sort().join(',');
}

function option(value, label) {
  const item = document.createElement('option');
  item.value = value;
  item.textContent = label;
  return item;
}

function setupYears() {
  const select = byId('year-select');
  const selected = select.value;
  const years = [...new Set(dataset.records.map(row => row.year).filter(Number.isInteger))].sort((a, b) => b - a);
  select.replaceChildren(option('', 'Alle Jahre'), ...years.map(year => option(String(year), String(year))));
  if (years.some(year => String(year) === selected)) select.value = selected;
}

function renderArchives() {
  const wrap = byId('archive-links');
  if (!dataset.archiveMonths.length) {
    wrap.replaceChildren(Object.assign(document.createElement('span'), {textContent:'Noch keine Monats-Sicherung vorhanden.'}));
    return;
  }
  const links = [...dataset.archiveMonths].sort().reverse().map(month => {
    const anchor = document.createElement('a');
    const date = new Date(`${month}-01T12:00:00Z`);
    anchor.href = new URL(`data/returnees/archive/${month}.xlsx`, siteRoot);
    anchor.download = `returnees-${month}.xlsx`;
    anchor.textContent = new Intl.DateTimeFormat('de-DE', {month:'long', year:'numeric', timeZone:'UTC'}).format(date);
    return anchor;
  });
  wrap.replaceChildren(...links);
}

function render() {
  if (!dataset) return;
  const selectedYear = byId('year-select').value;
  const showAll = byId('show-all').checked;
  const direction = byId('sort-select').value === 'year-asc' ? 1 : -1;
  const records = dataset.records
    .filter(row => (showAll || !row.allCampsCompleted) && (!selectedYear || String(row.year) === selectedYear))
    .sort((a, b) => {
      if (a.year === null) return b.year === null ? a.id.localeCompare(b.id) : 1;
      if (b.year === null) return -1;
      return direction * (a.year - b.year) || a.id.localeCompare(b.id);
    });
  byId('visible-count').textContent = records.length.toLocaleString('de-DE');
  byId('visible-label').textContent = showAll ? 'Returnees in der Auswahl' : 'Returnees ohne beide AFS-Seminare';
  byId('total-count').textContent = `Insgesamt ${dataset.records.length.toLocaleString('de-DE')} erreichbare Returnees`;
  const updated = new Date(dataset.updatedAt);
  byId('updated-label').textContent = Number.isFinite(updated.valueOf()) ? `Datenstand ${new Intl.DateTimeFormat('de-DE', {dateStyle:'medium', timeStyle:'short'}).format(updated)}` : '';
  byId('connection-label').textContent = 'AFSer-Datenstand';
  byId('connection').classList.add('connected');
  byId('refresh-label').textContent = 'Automatische Prüfung jede Minute; AFSer-Import etwa alle 5 Minuten.';
  const body = byId('returnee-rows');
  if (!records.length) {
    const row = document.createElement('tr'), cell = document.createElement('td');
    cell.colSpan = 5;
    cell.className = 'returnee-empty';
    cell.textContent = 'Keine Returnees entsprechen dieser Auswahl.';
    row.append(cell);
    body.replaceChildren(row);
    return;
  }
  body.replaceChildren(...records.map(record => {
    const row = document.createElement('tr');
    const values = [record.id, record.year === null ? 'Unbekannt' : String(record.year)];
    for (const value of values) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.append(cell);
    }
    for (const complete of [record.seminar1Completed, record.seminar2Completed]) {
      const cell = document.createElement('td');
      const label = document.createElement('span');
      label.className = `camp-status${complete ? ' done' : ''}`;
      label.textContent = complete ? 'Absolviert' : 'Nicht eingetragen';
      cell.append(label);
      row.append(cell);
    }
    const completed = document.createElement('td');
    const label = document.createElement('span');
    label.className = `camp-status${record.allCampsCompleted ? ' done' : ''}`;
    label.textContent = record.allCampsCompleted ? 'Ja' : 'Nein';
    completed.append(label);
    row.append(completed);
    return row;
  }));
}

async function refresh() {
  if (loading) return;
  loading = true;
  try {
    const url = new URL(datasetUrl);
    url.searchParams.set('v', String(Date.now()));
    const response = await fetch(url, {cache:'no-store', credentials:'omit', referrerPolicy:'no-referrer'});
    if (!response.ok || !response.headers.get('content-type')?.toLowerCase().includes('application/json')) throw new Error('Der Returnee-Datenstand ist gerade nicht erreichbar.');
    const next = await response.json();
    if (!validDataset(next)) throw new Error('Der Returnee-Datenstand ist unvollständig oder ungültig.');
    dataset = next;
    byId('download-current').href = workbookUrl.href + `?v=${encodeURIComponent(dataset.generation)}`;
    setupYears();
    renderArchives();
    byId('load-error').hidden = true;
    byId('load-error').textContent = '';
    render();
  } catch (error) {
    byId('connection-label').textContent = 'Datenstand nicht erreichbar';
    byId('connection').classList.remove('connected');
    byId('load-error').textContent = error?.message || 'Returnee-Daten konnten nicht geladen werden.';
    byId('load-error').hidden = false;
    if (!dataset) byId('returnee-rows').innerHTML = '<tr><td colspan="5" class="returnee-empty">Returnee-Daten sind vorübergehend nicht verfügbar.</td></tr>';
  } finally {
    loading = false;
  }
}

byId('year-select').addEventListener('change', render);
byId('show-all').addEventListener('change', render);
byId('sort-select').addEventListener('change', render);
syncNavigation();
refresh();
setInterval(refresh, 60_000);
addEventListener('focus', refresh);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
