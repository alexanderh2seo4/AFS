// Fetch only the published anonymous projection. No credentials or private store.
const KINDS = ['sending', 'hopees', 'hostees', 'families'];
const RECORD_FIELDS = new Set(['id', 'kind', 'chapterId', 'status', 'urgent', 'deadline', 'country', 'sourceUrl', 'city', 'location', 'hasOpenRoles', 'pickedAt']);
const chapterId = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(value);
const timestamp = value => typeof value === 'string' && Number.isFinite(Date.parse(value));
const abortError = () => new DOMException('Anfrage wurde ersetzt.', 'AbortError');

export class DataError extends Error {
  constructor(code) {
    super({timeout:'Das Laden dauert zu lange. Bitte erneut versuchen.', network:'Der Datenstand ist nicht erreichbar. Prüfe die Internetverbindung.', unavailable:'Der veröffentlichte Datenstand ist gerade nicht verfügbar. Bitte erneut versuchen.', invalid:'Der veröffentlichte Datenstand ist unvollständig oder ungültig.', changed:'Der Datenstand wird gerade aktualisiert. Bitte erneut laden.'}[code] || 'Daten konnten nicht geladen werden.');
    this.name = 'DataError';
    this.code = code;
  }
}

export async function readJSON(url, {signal, timeoutMs = 12000, fetchImpl = globalThis.fetch} = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort();
  if (signal?.aborted) throw abortError();
  signal?.addEventListener('abort', cancel, {once:true});
  const timer = setTimeout(() => {timedOut = true; controller.abort();}, timeoutMs);
  try {
    const response = await fetchImpl(url, {signal:controller.signal, cache:'no-store', credentials:'omit', referrerPolicy:'no-referrer'});
    if (!response.ok) throw new DataError('unavailable');
    if (!response.headers.get('content-type')?.toLowerCase().includes('application/json')) throw new DataError('invalid');
    try { return await response.json(); }
    catch (error) { if (controller.signal.aborted) throw error; throw new DataError('invalid'); }
  } catch (error) {
    if (signal?.aborted) throw abortError();
    if (timedOut) throw new DataError('timeout');
    if (error instanceof DataError) throw error;
    throw new DataError('network');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}

export function latestRequest() {
  let current;
  return {
    begin() { current?.abort(); current = new AbortController(); return current; },
    cancel() { current?.abort(); current = null; },
    isCurrent(request) { return current === request && !request.signal.aborted; }
  };
}

function validateManifest(data) {
  if (!data || data.version !== 1 || !timestamp(data.updatedAt) || !Array.isArray(data.chapters) || !data.chapters.length) throw new DataError('invalid');
  const ids = new Set();
  for (const chapter of data.chapters) {
    if (!chapterId(chapter.id) || ['all','unassigned'].includes(chapter.id) || typeof chapter.name !== 'string' || !chapter.name || ids.has(chapter.id)) throw new DataError('invalid');
    ids.add(chapter.id);
  }
  if (data.defaultChapterId != null && !ids.has(data.defaultChapterId)) throw new DataError('invalid');
  if (data.generation != null && !/^[a-f0-9]{64}$/.test(data.generation)) throw new DataError('invalid');
  return data;
}

function validateChapter(data, chapter, manifest) {
  if (!data || data.chapter !== chapter || !data.records || typeof data.records !== 'object') throw new DataError('invalid');
  if (data.updatedAt !== manifest.updatedAt || manifest.generation && data.generation !== manifest.generation) throw new DataError('changed');
  const ids = new Set(manifest.chapters.map(c => c.id));
  for (const kind of KINDS) {
    if (!Array.isArray(data.records[kind])) throw new DataError('invalid');
    const seen = new Set();
    for (const record of data.records[kind]) {
      if (!record || Object.keys(record).some(k => !RECORD_FIELDS.has(k)) || !/^[a-f0-9]{20}$/.test(record.id) || record.kind !== kind || seen.has(record.id)) throw new DataError('invalid');
      if(record.hasOpenRoles!==undefined&&(kind!=='sending'||typeof record.hasOpenRoles!=='boolean'))throw new DataError('invalid');
      if(record.pickedAt!==undefined&&(kind!=='sending'||record.status!=='assigned'||!/^\d{4}-\d{2}-\d{2}$/.test(record.pickedAt)||!Number.isFinite(Date.parse(record.pickedAt))||new Date(record.pickedAt).toISOString().slice(0,10)!==record.pickedAt))throw new DataError('invalid');
      if (chapter === 'all' ? !(ids.has(record.chapterId) || kind === 'sending' && record.chapterId === 'unassigned') : record.chapterId !== chapter) throw new DataError('invalid');
      seen.add(record.id);
    }
  }
  return data;
}

export function publicDataStore(base, options = {}) {
  const root = new URL('data/', base);
  let manifest = null, epoch = 0, refreshRequest = 0;
  let chapterCache = new Map(), placesPromise = null;
  const read = (file, version, signal) => {
    const url = new URL(file, root);
    if (version) url.searchParams.set('v', version.generation || version.updatedAt);
    return readJSON(url, {...options, signal});
  };
  return {
    get manifest() { return manifest; },
    async refresh({signal} = {}) {
      const request = ++refreshRequest;
      const next = validateManifest(await read('manifest.json', null, signal));
      if (request !== refreshRequest || signal?.aborted) throw abortError();
      manifest = next; epoch++; chapterCache = new Map(); placesPromise = null;
      return manifest;
    },
    async records(kind, chapter, {signal} = {}) {
      if (!manifest || !KINDS.includes(kind) || chapter !== 'all' && !manifest.chapters.some(c => c.id === chapter)) throw new DataError('invalid');
      const version = manifest, capturedEpoch = epoch, cache = chapterCache;
      // Cache completed documents only: cancelled requests must not poison retries.
      let data = cache.get(chapter);
      if (!data) data = validateChapter(await read('chapters/' + encodeURIComponent(chapter) + '.json', version, signal), chapter, version);
      if (capturedEpoch !== epoch || signal?.aborted) throw abortError();
      cache.set(chapter, data);
      return {records:data.records[kind], updatedAt:data.updatedAt, kind, chapter};
    },
    async availableChapterIds({signal} = {}) {
      const capturedEpoch = epoch;
      await this.records('sending', 'all', {signal});
      if (capturedEpoch !== epoch || signal?.aborted) throw abortError();
      const data = chapterCache.get('all');
      return Object.fromEntries(KINDS.map(kind => [kind, [...new Set(data.records[kind].map(record => record.chapterId))]]));
    },
    async places({signal} = {}) {
      if (!manifest) throw new DataError('invalid');
      const capturedEpoch = epoch, version = manifest;
      // Shared read is not owned by one keystroke's cancellation signal.
      if (!placesPromise) placesPromise = read('places.json', version).then(data => {
        if (!Array.isArray(data?.places)) throw new DataError('invalid');
        if (version.generation && data.generation !== version.generation) throw new DataError('changed');
        const chapters = new Set(version.chapters.map(c => c.id));
        if (data.places.some(row => !Array.isArray(row) || row.length !== 6 || typeof row[0] !== 'string' || typeof row[1] !== 'string' || !row[1] || row[2] !== null && !chapters.has(row[2]) || !Number.isFinite(row[3]) || Math.abs(row[3]) > 90 || !Number.isFinite(row[4]) || Math.abs(row[4]) > 180 || !/^\d{5}$/.test(row[5]))) throw new DataError('invalid');
        return data.places;
      }).catch(error => { if (capturedEpoch === epoch) placesPromise = null; throw error; });
      const rows = await placesPromise;
      if (capturedEpoch !== epoch || signal?.aborted) throw abortError();
      return rows;
    }
  };
}
