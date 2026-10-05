import {visibleRecords,hasOpenInterview} from './record-filters.js';
import {latestRequest,publicDataStore} from './data-client.js';
import {DEFAULT_RESIDENCE,findPublicPlaces,searchKey} from './locations.js';
const $ = id => document.getElementById(id);
const root = new URL('../', import.meta.url);
const publicData=publicDataStore(root);
const recordRequests=latestRequest(),bootstrapRequests=latestRequest();
const routes = {
  sending: {eyebrow:'SENDING · HOMEINTERVIEWS', title:'Engagiere dich bei uns!',description:'Finde offene Homeinterviews in unserem Komitee und melde dich direkt auf AFSer an.',unit:'Interviews',list:'Sending-Interviews'},
  awayees: {eyebrow:'SENDING · AWAYEES', title:'Unsere Awayees in der Welt.',description:'Entdecke, in welche Länder unsere Awayees reisen und wo sie gerade sind.',unit:'Sendees',list:'Awayees'},
  hostees: {eyebrow:'HOSTING · HOSTEES', title:'Unsere Hostees aus aller Welt.',description:'Unsere aktiven Gastschüler*innen – anonymisiert und mit direktem Link zu AFSer.',unit:'aktive Hostees',list:'Hostees'},
  families: {eyebrow:'HOSTING · GASTFAMILIEN', title:'Wir geben dem Austausch ein Zuhause.',description:'Entdecke unsere aktiven Gastfamilien und offenen Homeinterviews in unserem Komitee.',unit:'aktive Gastfamilien',list:'Gastfamilien'}
};
const storage = {get(k,session=false){try{return (session?sessionStorage:localStorage).getItem(k)}catch{return null}},set(k,v,session=false){try{(session?sessionStorage:localStorage).setItem(k,v)}catch{}},remove(k,session=false){try{(session?sessionStorage:localStorage).removeItem(k)}catch{}}};
function contactPromptVersion(){return contactConfig.noticeVersion||'initial-v1'}
function hasCurrentContactSubmission(){return !!contactConfig.noticeVersion&&storage.get('afs-contact-submitted-v1')===contactConfig.noticeVersion}
function hasContactDecision(){return hasCurrentContactSubmission()||storage.get('afs-contact-skipped-v1')===contactPromptVersion()}
let locationChosen=false;
let contactConfig={enabled:false,apiBaseUrl:'',purpose:'',retentionText:'',privacyContact:'',noticeVersion:''};
let pendingSubmissionId=null;
const state = {kind:routeFromPath(),chapters:[],records:[],chapter:'',residence:null,selectedPlace:null,updatedAt:null,request:0,placeRequest:0,connected:false,markers:new Map(),chapterData:new Map(),availableChapters:null,manifest:null,placeRows:null};
try {const saved=JSON.parse(storage.get('afs-public-residence')||'null');if(saved&&typeof saved==='object'&&(typeof saved.city==='string'||typeof saved.chapterId==='string')){state.residence=saved;locationChosen=!!saved.city}}catch{}
state.residence||=structuredClone(DEFAULT_RESIDENCE);state.chapter=storage.get('afs-public-chapter')||state.residence.chapterId||'';
function routeFromPath(){return location.pathname.split('/').filter(Boolean).findLast(part=>Object.hasOwn(routes,part))||'sending'}
function element(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function showDialog(id){document.querySelectorAll('dialog[open]').forEach(d=>d.close());$(id).showModal()}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,5000)}
function sourceLink(value){try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='www.afser.de'&&!u.username&&!u.password?u.href:null}catch{return null}}
async function request(path,{signal}={}){const u=new URL(path,'https://local.invalid');if(u.pathname==='/api/chapters'){state.manifest=await publicData.refresh({signal});return {chapters:state.manifest.chapters}}if(u.pathname==='/api/status')return state.manifest;if(u.pathname==='/api/records')return publicData.records(u.searchParams.get('kind'),u.searchParams.get('chapter'),{signal});if(u.pathname==='/api/places'){state.placeRows=await publicData.places({signal});return {places:await findPublicPlaces(u.searchParams.get('q')||'',state.placeRows)}}throw Error('Unbekannte Datenabfrage.')}
let map,layer;
const mobileLayout=matchMedia('(max-width:760px)');
mobileLayout.addEventListener('change',()=>map?.closePopup());
function setMobileView(view){
  document.body.dataset.mobileView=view;
  document.querySelectorAll('[data-mobile-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mobileView===view)));
  if(view==='map'&&map){map.stop();map.invalidateSize({pan:false})}
}
document.querySelectorAll('[data-mobile-view]').forEach(button=>button.onclick=()=>setMobileView(button.dataset.mobileView));
// Remeasure Leaflet when a hidden phone map becomes visible or changes size.
const mapResizeObserver=new ResizeObserver(entries=>{
  if(entries.some(entry=>entry.contentRect.width&&entry.contentRect.height))requestAnimationFrame(()=>map?.invalidateSize({pan:false}));
});
mapResizeObserver.observe($('map-panel'));
function initMap(){if(!globalThis.L){$('map').append(element('p','empty-state','Die Kartenbibliothek konnte nicht geladen werden. Die Liste bleibt verfügbar.'));return}map=L.map('map',{scrollWheelZoom:true,zoomControl:true,maxZoom:13,minZoom:2}).setView([state.residence?.location?.lat||48.1374,state.residence?.location?.lon||11.5755],8);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'© <a href="https://www.openstreetmap.org/copyright" rel="noopener noreferrer" target="_blank">OpenStreetMap</a>'}).addTo(map);layer=L.layerGroup().addTo(map);map.on('popupopen',({popup:detail})=>{const panel=detail.getElement(),mapPanel=$('map-panel'),bounds=mapPanel.getBoundingClientRect(),popupBounds=panel.getBoundingClientRect();mapPanel.append(panel);if(mobileLayout.matches){panel.classList.add('mobile-map-popup')}else{panel.classList.add('desktop-map-popup');const margin=12,left=Math.max(margin,Math.min(popupBounds.left-bounds.left,bounds.width-popupBounds.width-margin)),top=Math.max(margin,Math.min(popupBounds.top-bounds.top,bounds.height-popupBounds.height-margin));panel.style.left=left+'px';panel.style.top=top+'px';panel.style.right='auto';panel.style.bottom='auto'}});map.on('popupclose',()=>document.querySelectorAll('.record-card.selected').forEach(e=>e.classList.remove('selected')))}
function syncNavigation(){document.querySelectorAll?.('.brand')?.forEach(a=>{a.href=new URL('./',root).href});document.querySelectorAll?.('[data-route]')?.forEach(a=>{a.href=new URL(a.dataset.route+'/',root).href;a.classList?.toggle('active',a.dataset.route===state.kind);if(a.dataset.route===state.kind)a.setAttribute?.('aria-current','page');else a.removeAttribute?.('aria-current')});document.querySelectorAll?.('nav a')?.forEach(a=>{const href=a.getAttribute?.('href')||a.href||'';if(!a.dataset?.route&&(href.includes('returnees')||a.textContent?.trim()==='Returnees')){a.href=new URL('returnees/',root).href;a.classList?.remove('active');a.removeAttribute?.('aria-current')}});document.querySelectorAll?.('.contact-form-link, a[href*="Kontaktformular"]')?.forEach(a=>{a.href=new URL('Kontaktformular/',root).href})}
function setRoute(kind,push=false){state.kind=Object.hasOwn(routes,kind)?kind:'sending';const r=routes[state.kind];document.title='AFS Karte · '+(state.kind==='families'?'Gastfamilien':state.kind.charAt(0).toUpperCase()+state.kind.slice(1));$('eyebrow').textContent=r.eyebrow;$('page-title').textContent=r.title;$('page-description').textContent=r.description;$('record-unit').textContent=r.unit;$('list-heading').textContent=r.list;$('urgent-control').hidden=state.kind!=='sending'&&state.kind!=='families';$('urgent-only').checked=false;$('map-top-note').textContent=state.kind==='awayees'?'Nur Gastländer, keine Wohnadressen':'Standorte als ungefähre Bereiche';$('map-legend').hidden=state.kind==='awayees';$('sort-select').hidden=state.kind==='awayees';syncNavigation();if(push)history.pushState({},'',new URL(state.kind+'/',root));configureRecordFilter();populateChapters();clearRecords();setMobileView('map');if(state.connected&&state.chapter)loadRecords()}
function clearRecords(){state.selection=(state.selection||0)+1;recordRequests.cancel();state.request++;state.recordsScope=null;state.updatedAt=null;state.fetchError='';$('updated-label').textContent='';$('data-notice').hidden=true;map?.closePopup();state.records=[];state.markers.clear();layer?.clearLayers();$('record-count').textContent='–';$('urgent-count').hidden=true;$('nearby-section').hidden=true;$('results-list').replaceChildren();$('refresh-button').disabled=!state.connected||!state.chapter;if(!state.connected)renderEmpty('Unser Datenstand','Wir laden die anonymisierten Kartendaten von GitHub.');else if(!state.chapter)renderEmpty('Welches Komitee?','Wähle deinen Wohnort oder unser Komitee, um passende Einträge zu sehen.');}
function renderEmpty(title,copy){const box=element('div','empty-state');box.append(element('div','empty-icon','⌖'),element('h3','',title),element('p','',copy));const btn=element('button','primary',state.chapter?'Aktualisieren':'Komitee auswählen');btn.onclick=!state.connected?loadPublic:!state.chapter?()=>$('chapter-select').focus():reloadPublic;box.append(btn);$('results-list').replaceChildren(box)}
function populateChapters(){
  const makeOption=chapter=>{const option=element('option','',chapter.name);option.value=chapter.id;return option};
  const available=state.availableChapters?.[state.kind];
  const visible=state.chapters.filter(chapter=>available?.includes(chapter.id));
  const placeholder=element('option','','Bitte auswählen');placeholder.value='';
  const all=element('option','','Alle verfügbaren · Deutschland');all.value='all';
  $('chapter-select').replaceChildren(placeholder,all,...visible.map(makeOption));
  $('chapter-select').disabled=!state.connected;
  if(state.connected&&available&&state.chapter&&state.chapter!=='all'&&!visible.some(chapter=>chapter.id===state.chapter)){
    state.chapter='all';storage.set('afs-public-chapter','all');
  }
  $('chapter-select').value=state.chapter;updateScope();
}
async function loadChapterAvailability(signal){
  let available;
  try{available=await publicData.availableChapterIds({signal})}
  catch(error){
    if(error.code!=='changed'||signal?.aborted)throw error;
    const data=await request('/api/chapters',{signal});state.chapters=data.chapters;
    available=await publicData.availableChapterIds({signal});
  }
  if(signal?.aborted)return;
  state.availableChapters=available;
}

function configureRecordFilter(){
  const modes=state.kind==='awayees'?[['active','Im Austausch'],['pending','In Vorbereitung'],['all','Alle aktuellen Sendees']]:[['all','Offen & übernommen'],['open','Nur offen'],['recent','Kürzlich übernommen (30 Tage)'],['assigned','Alle übernommen']];
  $('record-filter-control').hidden=!['sending','awayees'].includes(state.kind);
  $('record-filter').replaceChildren(...modes.map(([value,label])=>{const option=element('option','',label);option.value=value;return option}));
  $('record-filter').value=state.kind==='awayees'?'active':'all';
}
function chapterName(id){return id==='unassigned'?'Komitee noch offen':state.chapters.find(c=>c.id===id)?.name||id||'Komitee noch offen'}
function updateScope(){$('show-all-button').disabled=!state.connected;$('show-all-button').setAttribute('aria-pressed',String(state.chapter==='all'&&!$('urgent-only').checked&&(!$('record-filter')||$('record-filter-control')?.hidden||$('record-filter').value==='all')));$('scope-note').textContent=state.chapter==='all'?'Alle verfügbaren Einträge aus allen Komitees.':state.chapter?'Nur Einträge aus '+chapterName(state.chapter):'Wähle deinen Wohnort oder unser Komitee.';$('residence-label').textContent=state.residence?.city|| (state.residence?.chapterId?chapterName(state.residence.chapterId):'Wo wohnst du?')}
async function showAllAvailable(){
  state.chapter='all';storage.set('afs-public-chapter','all');
  $('chapter-select').value='all';$('urgent-only').checked=false;
  if($('record-filter'))$('record-filter').value='all';
  updateScope();clearRecords();await loadRecords();
}
$('show-all-button').onclick=showAllAvailable;
function connectionState(ok){$('connection-button').classList.toggle('connected',ok);$('connection-label').textContent=ok?'Öffentliche Karte':state.updatedAt?'Zuletzt geladener Stand':'Datenstand laden'}
function fetchFailed(error,hasPrevious){state.fetchError=(error.message||'Daten konnten nicht geladen werden.')+(hasPrevious?' Du siehst weiterhin den zuletzt erfolgreich geladenen Stand.':'');connectionState(false);refreshStatus()}
async function loadPublic(){
  const job=bootstrapRequests.begin();$('refresh-button').disabled=true;
  try{
    const data=await request('/api/chapters',{signal:job.signal});if(!bootstrapRequests.isCurrent(job))return;
    state.chapters=data.chapters;await loadChapterAvailability(job.signal);if(!bootstrapRequests.isCurrent(job))return;state.connected=true;await restoreResidence();if(!bootstrapRequests.isCurrent(job))return;
    populateChapters();connectionState(true);
    if(state.chapter)await loadRecords();else clearRecords();if(!locationChosen&&hasCurrentContactSubmission())openResidence()
  }catch(e){if(!bootstrapRequests.isCurrent(job)||e.name==='AbortError')return;state.connected=false;clearRecords();populateChapters();renderEmpty('Datenstand nicht erreichbar',e.message);fetchFailed(e,false)}
  finally{if(bootstrapRequests.isCurrent(job))$('refresh-button').disabled=!state.connected||!state.chapter}
}
async function reloadPublic(){
  if(!state.connected)return loadPublic();
  const job=bootstrapRequests.begin();recordRequests.cancel();state.request++;$('refresh-button').disabled=true;
  try{
    const data=await request('/api/chapters',{signal:job.signal});if(!bootstrapRequests.isCurrent(job))return;
    state.chapters=data.chapters;await loadChapterAvailability(job.signal);if(!bootstrapRequests.isCurrent(job))return;populateChapters();
    if(state.chapter)await loadRecords();else clearRecords()
  }catch(e){if(!bootstrapRequests.isCurrent(job)||e.name==='AbortError')return;fetchFailed(e,!!state.updatedAt);if(!state.updatedAt){renderEmpty('Datenstand nicht erreichbar',e.message);$('record-count').textContent='–'}}
  finally{if(bootstrapRequests.isCurrent(job))$('refresh-button').disabled=!state.connected||!state.chapter}
}
function refreshStatus(){const time=new Date(state.manifest?.updatedAt),stale=Number.isFinite(time.valueOf())&&Date.now()-time.valueOf()>24*60*60*1000;$('data-notice').hidden=!state.fetchError&&!stale;$('data-notice').textContent=state.fetchError||'Unser veröffentlichter Datenstand ist älter als 24 Stunden. Aktuelle Details findest du auf AFSer.';$('sync-info').textContent='Wir laden den zuletzt auf GitHub veröffentlichten anonymisierten Datenstand. Mit dem lokalen Importer können wir aktualisierte Daten veröffentlichen; unsere Karte bleibt auch ohne ihn erreichbar.';}
async function loadRecords(){
  if(!state.connected||!state.chapter)return;
  const job=recordRequests.begin(),id=++state.request,kind=state.kind,chapter=state.chapter,scope=kind+':'+chapter;
  const hasPrevious=state.recordsScope===scope&&!!state.updatedAt;
  const current=()=>id===state.request&&recordRequests.isCurrent(job)&&state.kind===kind&&state.chapter===chapter;
  if(!hasPrevious){map?.closePopup();layer?.clearLayers();state.markers.clear();state.records=[];state.updatedAt=null;state.recordsScope=null;state.fetchError='';$('updated-label').textContent='';$('data-notice').hidden=true;$('record-count').textContent='…';$('urgent-count').hidden=true;$('nearby-section').hidden=true;$('results-list').replaceChildren(element('div','empty-state','Wir laden die Einträge …'))}
  $('refresh-button').disabled=true;
  try{
    const path='/api/records?'+new URLSearchParams({kind,chapter});let data;
    try{data=await request(path,{signal:job.signal})}
    catch(e){
      if(e.code!=='changed'||!current())throw e;
      // A deployment can briefly serve its old manifest with new chapter files.
      const fresh=await request('/api/chapters',{signal:job.signal});if(!current())return;
      state.chapters=fresh.chapters;await loadChapterAvailability(job.signal);if(!current())return;populateChapters();if(!current()){if(recordRequests.isCurrent(job)&&state.chapter!==chapter){clearRecords();openResidence()}return;}
      data=await request(path,{signal:job.signal});
    }
    if(!current())return;
    state.records=data.records;state.updatedAt=data.updatedAt;state.recordsScope=scope;state.fetchError='';connectionState(true);render();fitMap();refreshStatus();
    $('updated-label').textContent='Stand: '+new Intl.DateTimeFormat('de-DE',{dateStyle:'short',timeStyle:'short'}).format(new Date(data.updatedAt));
  }catch(e){if(!current()||e.name==='AbortError')return;fetchFailed(e,hasPrevious);if(!hasPrevious){renderEmpty('Datenstand nicht erreichbar',e.message);$('record-count').textContent='–'}}
  finally{if(current())$('refresh-button').disabled=false}
}
function distance(r){const a=state.residence?.location,b=r.location;if(!a||!b||state.kind==='awayees')return Infinity;const rad=Math.PI/180;const dLat=(b.lat-a.lat)*rad,dLon=(b.lon-a.lon)*rad;const h=Math.sin(dLat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dLon/2)**2;return 6371*2*Math.atan2(Math.sqrt(h),Math.sqrt(1-h))}
function distanceLabel(r){const d=distance(r);return Number.isFinite(d)?'ca. '+Math.max(1,Math.round(d))+' km':''}
function deadlineLabel(r){if(!/^\d{4}-\d{2}-\d{2}$/.test(r.deadline||''))return '';const d=new Date(r.deadline+'T12:00:00Z');return Number.isNaN(d.valueOf())?'':'bis '+new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Berlin'}).format(d)}
function statusLabel(r){if(state.kind==='sending'&&r.status==='assigned')return hasOpenInterview(r)?'Teilweise übernommen':'Übernommen';return ({open:'Offen',needed:'Interview benötigt',assigned:'In Arbeit',active:'Aktiv',pending:'In Vorbereitung',Participation:'Im Austausch',Preparation:'Vorbereitung',Admission:'Zusage'})[r.status]||r.status||'Aktiv'}
function recordUrgent(r){return r.urgent&&!(state.kind==='sending'&&r.status==='assigned'&&!hasOpenInterview(r))}
function title(r){if(state.kind==='awayees')return r.country||'Gastland noch offen';return r.city|| (state.kind==='sending'?'Homeinterview':state.kind==='families'?'Gastfamilie':'Hostee')+' · '+chapterName(r.chapterId)}
function recordCard(r){const urgent=recordUrgent(r);const btn=element('button','record-card'+(urgent?' urgent':''));btn.dataset.record=r.id;const top=element('div','card-top');top.append(element('span','card-title',title(r)),element('span','badge'+(urgent?' danger':r.status==='assigned'?' picked':''),r.status==='assigned'?statusLabel(r)+(urgent?' · Dringend':''):urgent?'Dringend':statusLabel(r)));btn.append(top,element('div','card-details',state.kind==='awayees'?chapterName(r.chapterId):(r.country? (state.kind==='hostees'?'Aus ':'Gastland: ')+r.country:chapterName(r.chapterId))));const bottom=element('div','card-bottom');bottom.append(element('span',urgent?'deadline':'',deadlineLabel(r)||'AFSer-Details verfügbar'),element('span','',distanceLabel(r)));btn.append(bottom);btn.onclick=()=>selectRecord(r,btn);return btn}
function popup(r){const urgent=recordUrgent(r);const box=element('div','record-popup');box.append(element('span','badge'+(urgent?' danger':r.status==='assigned'?' picked':''),r.status==='assigned'?statusLabel(r)+(urgent?' · Dringend':''):urgent?'Dringend':statusLabel(r)),element('h3','popup-heading',title(r)),element('p','popup-row',chapterName(r.chapterId)));if(r.country)box.append(element('p','popup-row',(state.kind==='hostees'?'Herkunftsland: ':'Gastland: ')+r.country));if(r.pickedAt)box.append(element('p','popup-row','Übernahme erkannt: '+new Intl.DateTimeFormat('de-DE',{dateStyle:'short'}).format(new Date(r.pickedAt+'T12:00:00Z'))));else if(state.kind==='sending'&&r.status==='assigned')box.append(element('p','popup-note','Das Datum der Übernahme ist in AFSer nicht angegeben.'));if(r.deadline)box.append(element('p','popup-row',deadlineLabel(r)));if(distanceLabel(r))box.append(element('p','popup-row',distanceLabel(r)+' von deinem Ort'));if(r.location&&state.kind!=='awayees')box.append(element('p','popup-note','Ungefährer Bereich (ca. '+r.location.radiusKm+' km). Die tatsächliche Adresse wird hier nicht angezeigt.'));if(!r.location)box.append(element('p','popup-note','Für diesen Eintrag ist kein bestätigter Kartenstandort verfügbar.'));const link=sourceLink(r.sourceUrl);if(link){const a=element('a','popup-link',state.kind==='sending'?(hasOpenInterview(r)?'Interview auf AFSer übernehmen':'Übernommenes Interview auf AFSer'):'Details auf AFSer öffnen');a.href=link;a.target='_blank';a.rel='noopener noreferrer';box.append(a,element('p','popup-note',state.kind==='sending'&&hasOpenInterview(r)?'Auf AFSer anmelden und dort für das Interview eintragen.':'AFSer-Login erforderlich.'))}else box.append(element('p','popup-note','Für diesen Eintrag fehlt ein bestätigter AFSer-Link.'));return box}
function selectRecord(r,btn){
  document.querySelectorAll('.record-card.selected').forEach(e=>e.classList.remove('selected'));btn?.classList.add('selected');
  const marker=state.markers.get(r.id),selection=state.selection=(state.selection||0)+1;
  const open=()=>{if(selection!==state.selection)return;if(marker&&map&&state.markers.get(r.id)===marker){
    if(mobileLayout.matches){map.invalidateSize({pan:false});map.setView(marker.getLatLng(),map.getZoom(),{animate:false,reset:true})}else map.panTo(marker.getLatLng());
    const detail=marker.getPopup();detail.options.autoPan=false;marker.openPopup();
  }else if(map)L.popup({autoPan:false}).setLatLng(map.getCenter()).setContent(popup(r)).openOn(map);else toast('Karte nicht verfügbar. AFSer-Link in den Details.')};
  if(mobileLayout.matches&&map){setMobileView('map');document.querySelector('[data-mobile-view="map"]').focus({preventScroll:true});document.querySelector('.mobile-view-switch').scrollIntoView({block:'start'});
    requestAnimationFrame(()=>requestAnimationFrame(open));
  }else open();
}
function render(){if(!state.connected||!state.chapter)return;updateScope();const records=visibleRecords(state.records,state.kind,$('record-filter').value).filter(r=>!$('urgent-only').checked||recordUrgent(r));const sorter=$('sort-select').value;records.sort((a,b)=>sorter==='distance'?distance(a)-distance(b):sorter==='date'?(a.deadline||'9999').localeCompare(b.deadline||'9999'):Number(recordUrgent(b))-Number(recordUrgent(a))||distance(a)-distance(b));$('record-count').textContent=records.length;const urgent=records.filter(recordUrgent).length;$('urgent-count').hidden=!urgent||state.kind==='awayees';$('urgent-count').textContent=urgent+' dringend';$('results-list').replaceChildren(...records.map(recordCard));if(!records.length)renderEmpty('Keine passenden Einträge','Für dieses Komitee gibt es im gewählten Filter keine Einträge. Du kannst die Anzeige oben ändern.');renderNearby(records);renderMap(records)}
function renderNearby(records){const nearby=records.filter(r=>Number.isFinite(distance(r))).sort((a,b)=>distance(a)-distance(b)).slice(0,3);$('nearby-section').hidden=!nearby.length||state.kind!=='sending';$('nearby-results').replaceChildren(...nearby.map(r=>{const b=element('button','nearby-row');b.append(element('span','',title(r)),element('span','',distanceLabel(r)));b.onclick=()=>selectRecord(r,document.querySelector('[data-record="'+CSS.escape(r.id)+'"]'));return b}))}
function renderMap(records){if(!map||!layer)return;map.closePopup();layer.clearLayers();state.markers.clear();if(state.kind==='awayees'){const groups=new Map();for(const r of records){if(!r.location)continue;const key=r.country||'Unbekannt';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r)}for(const [country,group] of groups){const loc=group[0].location;const marker=L.marker([loc.lat,loc.lon],{icon:L.divIcon({className:'country-marker',html:String(group.length),iconSize:[36,36],iconAnchor:[18,18]})});const box=element('div','');box.append(element('h3','popup-heading',country),element('p','popup-row',group.length+' Sendees'));const list=element('div','country-popup-list');for(const [index,r] of group.entries()){const url=sourceLink(r.sourceUrl);const a=element(url?'a':'span','country-popup-link');a.append(element('span','','Eintrag '+(index+1)),element('span','',statusLabel(r)));if(url){a.href=url;a.target='_blank';a.rel='noopener noreferrer'}list.append(a);state.markers.set(r.id,marker)}box.append(list,element('p','popup-note','Nur das Gastland wird angezeigt. Einzelne Einträge öffnen die AFSer-Quelle.'));marker.bindPopup(box,{autoPan:false}).addTo(layer)}}else{for(const r of records){if(!r.location||!Number.isFinite(r.location.lat)||!Number.isFinite(r.location.lon))continue;const urgent=recordUrgent(r);const color=r.status==='assigned'?'#b77a16':urgent?'#bd343c':'#087f79';L.circle([r.location.lat,r.location.lon],{radius:r.location.radiusKm*1000,color,weight:1,opacity:.4,fillColor:color,fillOpacity:.09,interactive:false}).addTo(layer);const marker=L.circleMarker([r.location.lat,r.location.lon],{radius:6,fillColor:color,fillOpacity:1,color:'#fff',weight:2}).bindPopup(popup(r),{autoPan:false}).addTo(layer);state.markers.set(r.id,marker)}}}
function fitMap(){if(!map)return;const points=[...state.markers.values()].map(m=>m.getLatLng());if(points.length)map.fitBounds(L.latLngBounds(points).pad(.25),{maxZoom:state.kind==='awayees'?4:11,animate:!mobileLayout.matches});else if(state.kind==='awayees')map.setView([25,10],2);else if(state.residence?.location&&state.chapter!=='all')map.setView([state.residence.location.lat,state.residence.location.lon],8);else map.setView([51.15,10.45],6)}
$('connection-button').onclick=()=>state.connected&&!state.fetchError?showDialog('privacy-dialog'):reloadPublic();$('residence-button').onclick=openResidence;$('privacy-button').onclick=()=>showDialog('privacy-dialog');if($('footer-privacy-button'))$('footer-privacy-button').onclick=()=>showDialog('privacy-dialog');$('refresh-button').onclick=reloadPublic;$('fit-map').onclick=fitMap;$('urgent-only').onchange=render;$('sort-select').onchange=render;$('record-filter').onchange=()=>{render();fitMap()};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());document.querySelectorAll('[data-route]').forEach(a=>a.onclick=e=>{if(e.ctrlKey||e.metaKey||e.shiftKey)return;e.preventDefault();setRoute(a.dataset.route,true)});document.querySelector('.brand').onclick=e=>{e.preventDefault();setRoute('sending',true)};addEventListener('popstate',()=>setRoute(routeFromPath()));
$('chapter-select').onchange=()=>{state.chapter=$('chapter-select').value;storage.set('afs-public-chapter',state.chapter);updateScope();clearRecords();if(state.chapter)loadRecords()};
let cityTimer;
function cancelPlaceSearch(){clearTimeout(cityTimer);state.placeRequest++;$('city-options').replaceChildren()}
async function findPlaces(query){try{return (await request('/api/places?'+new URLSearchParams({q:query}))).places||[]}catch{return findPublicPlaces(query)}}
async function restoreResidence(){
  if(state.chapter==='all'||state.chapters.some(c=>c.id===state.chapter))return;
  const place=state.residence,chapterAtStart=state.chapter;
  if(searchKey(place?.city||'')==='munchen'){const chapter=state.chapters.find(c=>searchKey(c.name)==='munchen');if(chapter){state.residence={...place,chapterId:chapter.id};state.chapter=chapter.id;return}}
  if(place?.city){
    const matches=await findPlaces(place.postalCode||place.city);
    if(state.residence!==place||state.chapter!==chapterAtStart)return;
    const exact=matches.filter(p=>searchKey(p.city)===searchKey(place.city));
    const chapters=new Set(exact.map(p=>p.chapterId).filter(Boolean));
    if(chapters.size===1){state.residence={...place,chapterId:[...chapters][0]};state.chapter=state.residence.chapterId;return}
  }
  state.chapter='';
}
function openResidence(intake=false,preserveInput=false){
  const firstVisit=intake&&!hasContactDecision();
  cancelPlaceSearch();if(!preserveInput){if(firstVisit){state.selectedPlace=null;$('city-input').value=''}else{state.selectedPlace=state.residence?.city?structuredClone(state.residence):null;$('city-input').value=state.residence?.city||''}}
  $('contact-fields').hidden=!firstVisit;
  for(const id of ['contact-name','contact-email','contact-phone','contact-consent'])$(id).required=firstVisit;
  $('residence-eyebrow').textContent=firstVisit?'KONTAKTFORMULAR':'DEIN WOHNORT';
  $('residence-title').textContent=firstVisit?'Willkommen':'Wo wohnst du?';
  $('residence-intro').textContent=firstVisit?'Gib deine Kontaktdaten und deinen Wohnort ein, bevor du die Karte öffnest.':'Eine Stadt oder Postleitzahl genügt. Wir wählen unser Komitee automatisch aus. Wenn nötig, kannst du die Auswahl über der Karte ändern.';
  $('residence-note').textContent=firstVisit?'Deine Kontaktdaten und dein ausgewählter Ort werden beim Absenden an den privaten AFS-Dienst gesendet.':'Dein Wohnort bleibt in diesem Browser. Wir fragen keine genaue Adresse ab.';
  $('residence-submit').textContent=firstVisit?'Absenden und Karte öffnen':'Karte anzeigen';
  $('residence-submit').disabled=firstVisit&&!contactConfig.enabled;
  $('skip-contact-button').hidden=!firstVisit;
  if($('residence-close'))$('residence-close').hidden=false;
  $('residence-message').textContent=firstVisit&&!contactConfig.enabled?'Das Kontaktformular ist noch nicht eingerichtet. Bitte versuche es später erneut.':'';
  $('contact-purpose').textContent=contactConfig.purpose?'Wir verwenden deine Angaben, um '+contactConfig.purpose+'.':'';
  $('contact-retention').textContent=contactConfig.retentionText;
  $('contact-privacy-copy').textContent=[contactConfig.purpose?'Zweck: '+contactConfig.purpose+'.':'',contactConfig.retentionText,contactConfig.privacyContact?'Datenschutzkontakt: '+contactConfig.privacyContact+'.':''].filter(Boolean).join(' ');
  showDialog('residence-dialog');
}
function selectPlace(place){
  cancelPlaceSearch();state.selectedPlace=place;$('city-input').value=place.city;
  $('residence-message').textContent=place.chapterId?'Ort gefunden. Unser Komitee wird automatisch ausgewählt.':'Ort gefunden. Du kannst unser Komitee anschließend über der Karte auswählen.';
}
$('residence-dialog').addEventListener('close',cancelPlaceSearch);
if($('residence-close'))$('residence-close').onclick=()=>{if(!$('contact-fields').hidden&&!hasContactDecision())storage.set('afs-contact-skipped-v1',contactPromptVersion());$('residence-dialog').close()};
$('residence-dialog').addEventListener('cancel',()=>{if(!$('contact-fields').hidden&&!hasContactDecision())storage.set('afs-contact-skipped-v1',contactPromptVersion())});
$('skip-contact-button').onclick=()=>{storage.set('afs-contact-skipped-v1',contactPromptVersion());$('residence-dialog').close()};
$('contact-privacy-button').onclick=()=>showDialog('privacy-dialog');
$('privacy-dialog').addEventListener('close',()=>{if(!hasContactDecision())openResidence(true,true)});
$('city-input').oninput=()=>{
  state.selectedPlace=null;cancelPlaceSearch();
  const query=$('city-input').value.trim(),id=state.placeRequest;
  $('residence-message').textContent=query.length<2?'Mindestens zwei Buchstaben oder Ziffern eingeben.':'Orte werden gesucht …';
  if(query.length<2)return;
  cityTimer=setTimeout(async()=>{
    try{const places=await findPlaces(query);if(id!==state.placeRequest)return;
      $('city-options').replaceChildren(...places.map(place=>{const b=element('button','city-option',place.label||place.city);b.type='button';
        b.onclick=()=>selectPlace(place);return b}));
      $('residence-message').textContent=places.length?'Bitte einen Ort aus der Liste wählen.':'Kein passender Ort gefunden. Prüfe die Schreibweise oder wähle unser Komitee direkt.';
    }catch{if(id===state.placeRequest)$('residence-message').textContent='Ortsuche gerade nicht verfügbar. Bitte erneut versuchen oder unser Komitee direkt wählen.'}
  },250);
};
$('residence-form').onsubmit=async e=>{
  e.preventDefault();const b=e.submitter,id=state.placeRequest;b.disabled=true;
  try{
    const firstVisit=!$('contact-fields').hidden;
    let place=state.selectedPlace;
    if(!place&&$('city-input').value.trim()){
      const query=$('city-input').value.trim(),places=await findPlaces(query);
      const exact=places.filter(p=>searchKey(p.city)===searchKey(query)||p.postalCode===query);
      if(exact.length!==1){$('residence-message').textContent='Bitte einen eindeutigen Ort aus der Vorschlagsliste wählen.';return}place=exact[0];
    }
    if(id!==state.placeRequest)return;
    if(!place){$('residence-message').textContent='Bitte wähle deinen Ort aus der Vorschlagsliste.';return}
    if(firstVisit){
      if(!contactConfig.enabled||!contactConfig.apiBaseUrl||!contactConfig.noticeVersion){$('residence-message').textContent='Das Kontaktformular ist noch nicht eingerichtet. Bitte versuche es später erneut.';return}
      if(!$('contact-consent').checked){$('residence-message').textContent='Bitte bestätige die Datenschutzhinweise.';return}
      const endpoint=new URL(contactConfig.apiBaseUrl);endpoint.pathname=endpoint.pathname.replace(/\/$/,'')+'/api/contact';endpoint.search='';endpoint.hash='';
      if(endpoint.protocol!=='https:'){ $('residence-message').textContent='Das Kontaktformular ist nur über eine sichere Verbindung verfügbar.';return }
      pendingSubmissionId||=crypto.randomUUID();
      const payload={submissionId:pendingSubmissionId,name:$('contact-name').value.trim(),email:$('contact-email').value.trim(),phone:$('contact-phone').value.trim(),postalCode:place.postalCode||'',city:place.city,interests:[...document.querySelectorAll('#contact-fields input[name="interests"]:checked')].map(input=>input.value),consent:true,consentVersion:contactConfig.noticeVersion,website:$('contact-website').value};
      let response;
      try{response=await fetch(endpoint,{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})}catch{$('residence-message').textContent='Die Angaben konnten gerade nicht gesendet werden. Bitte versuche es erneut.';return}
      if(!response.ok){$('residence-message').textContent=response.status===429?'Bitte warte kurz und versuche es erneut.':'Die Angaben konnten gerade nicht gesendet werden. Bitte versuche es erneut.';return}
      storage.set('afs-contact-submitted-v1',contactConfig.noticeVersion);pendingSubmissionId=null;
    }
    const chapter=place.chapterId||'';
    state.residence=place?{city:place.city,postalCode:place.postalCode,chapterId:chapter,location:place.location}:{chapterId:chapter};
    locationChosen=true;storage.set('afs-public-residence',JSON.stringify(state.residence));storage.set('afs-public-chapter',chapter);state.chapter=chapter;$('chapter-select').value=chapter;updateScope();$('residence-dialog').close();clearRecords();fitMap();if(chapter)await loadRecords();else{renderEmpty('Komitee auswählen','Für deinen Wohnort ist noch kein Komitee bestätigt. Wähle unser Komitee über der Karte.');$('chapter-select').focus()}
  }catch{$('residence-message').textContent='Ort konnte nicht gespeichert werden. Bitte erneut versuchen.'}finally{b.disabled=false}
};
async function loadContactConfig(){
  try{
    const response=await fetch(new URL('assets/contact-config.json',root),{cache:'no-store',referrerPolicy:'no-referrer'});
    if(!response.ok)throw Error();
    const config=await response.json(),endpoint=new URL(config.apiBaseUrl||'');
    if(config.enabled===true&&endpoint.protocol==='https:'&&!endpoint.username&&!endpoint.password&&!endpoint.search&&!endpoint.hash&&config.purpose&&config.retentionText&&config.privacyContact&&config.noticeVersion){contactConfig={...contactConfig,...config,apiBaseUrl:endpoint.origin}}
  }catch{}
  if(!hasContactDecision())openResidence(true);
}
initMap();setMobileView('map');setRoute(state.kind);updateScope();loadContactConfig();loadPublic();
if(location.hash)history.replaceState({},'',location.pathname+location.search);storage.remove('afs-token',true);storage.remove('afs-api');
function refreshVisibleData(){if(state.connected&&state.chapter&&!document.hidden&&!$('refresh-button').disabled)reloadPublic()}
setInterval(refreshVisibleData,60*1000);
document.addEventListener('visibilitychange',refreshVisibleData);
addEventListener('online',()=>state.connected?refreshVisibleData():loadPublic());
