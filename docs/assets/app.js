import {latestRequest,publicDataStore} from './data-client.js';
import {DEFAULT_RESIDENCE,findPublicPlaces,searchKey} from './locations.js';
const $ = id => document.getElementById(id);
const root = new URL('../', import.meta.url);
const publicData=publicDataStore(root);
const recordRequests=latestRequest(),bootstrapRequests=latestRequest();
const routes = {
  sending: {eyebrow:'SENDING · HOMEINTERVIEWS', title:'Ein Gespräch. Ein Anfang.',description:'Finde offene Homeinterviews in deiner Nähe und melde dich direkt auf AFSer an.',unit:'offene Interviews',list:'Offene Interviews'},
  hopees: {eyebrow:'SENDING · HOPEES & AWAYEES', title:'Dein Komitee. In der Welt.',description:'Sieh, in welche Länder eure Hopees reisen und wo eure Awayees gerade sind.',unit:'aktive Teilnehmende',list:'Hopees & Awayees'},
  hostees: {eyebrow:'HOSTING · HOSTEES', title:'Die Welt zu Gast.',description:'Aktive Gastschüler*innen deines Komitees – anonymisiert und mit Link zu AFSer.',unit:'aktive Hostees',list:'Hostees'},
  families: {eyebrow:'HOSTING · GASTFAMILIEN', title:'Austausch beginnt zu Hause.',description:'Aktive Gastfamilien und offene Hosting-Homeinterviews in deinem Komitee.',unit:'aktive Gastfamilien',list:'Gastfamilien'}
};
const storage = {get(k,session=false){try{return (session?sessionStorage:localStorage).getItem(k)}catch{return null}},set(k,v,session=false){try{(session?sessionStorage:localStorage).setItem(k,v)}catch{}},remove(k,session=false){try{(session?sessionStorage:localStorage).removeItem(k)}catch{}}};
const state = {kind:routeFromPath(),chapters:[],records:[],chapter:'',residence:null,selectedPlace:null,updatedAt:null,request:0,placeRequest:0,connected:false,markers:new Map(),chapterData:new Map(),manifest:null,placeRows:null};
try {const saved=JSON.parse(storage.get('afs-public-residence')||'null');if(saved&&typeof saved==='object'&&(typeof saved.city==='string'||typeof saved.chapterId==='string'))state.residence=saved}catch{}
state.residence||=structuredClone(DEFAULT_RESIDENCE);state.chapter=state.residence.chapterId||'';
function routeFromPath(){return location.pathname.split('/').filter(Boolean).findLast(part=>Object.hasOwn(routes,part))||'sending'}
function element(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function showDialog(id){document.querySelectorAll('dialog[open]').forEach(d=>d.close());$(id).showModal()}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,5000)}
function sourceLink(value){try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='www.afser.de'&&!u.username&&!u.password?u.href:null}catch{return null}}
async function request(path,{signal}={}){const u=new URL(path,'https://local.invalid');if(u.pathname==='/api/chapters'){state.manifest=await publicData.refresh({signal});return {chapters:state.manifest.chapters}}if(u.pathname==='/api/status')return state.manifest;if(u.pathname==='/api/records')return publicData.records(u.searchParams.get('kind'),u.searchParams.get('chapter'),{signal});if(u.pathname==='/api/places'){state.placeRows=await publicData.places({signal});return {places:await findPublicPlaces(u.searchParams.get('q')||'',state.placeRows)}}throw Error('Unbekannte Datenabfrage.')}
let map,layer;
const mobileLayout=matchMedia('(max-width:760px)');
function setMobileView(view){
  document.body.dataset.mobileView=view;
  document.querySelectorAll('[data-mobile-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mobileView===view)));
  if(view==='map'&&map){map.stop();map.invalidateSize({pan:false});fitMap()}
}
document.querySelectorAll('[data-mobile-view]').forEach(button=>button.onclick=()=>setMobileView(button.dataset.mobileView));
// Remeasure Leaflet when a hidden phone map becomes visible or changes size.
const mapResizeObserver=new ResizeObserver(entries=>{
  if(entries.some(entry=>entry.contentRect.width&&entry.contentRect.height))requestAnimationFrame(()=>map?.invalidateSize({pan:false}));
});
mapResizeObserver.observe($('map-panel'));
function initMap(){if(!globalThis.L){$('map').append(element('p','empty-state','Die Kartenbibliothek konnte nicht geladen werden. Die Liste bleibt verfügbar.'));return}map=L.map('map',{scrollWheelZoom:true,zoomControl:true,maxZoom:13,minZoom:2}).setView([state.residence?.location?.lat||48.1374,state.residence?.location?.lon||11.5755],8);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'© <a href="https://www.openstreetmap.org/copyright" rel="noopener noreferrer" target="_blank">OpenStreetMap</a>'}).addTo(map);layer=L.layerGroup().addTo(map);map.on('popupclose',()=>document.querySelectorAll('.record-card.selected').forEach(e=>e.classList.remove('selected')))}
function setRoute(kind,push=false){state.kind=Object.hasOwn(routes,kind)?kind:'sending';const r=routes[state.kind];document.title='AFS Karte · '+(state.kind==='families'?'Gastfamilien':state.kind.charAt(0).toUpperCase()+state.kind.slice(1));$('eyebrow').textContent=r.eyebrow;$('page-title').textContent=r.title;$('page-description').textContent=r.description;$('record-unit').textContent=r.unit;$('list-heading').textContent=r.list;$('urgent-control').hidden=state.kind!=='sending'&&state.kind!=='families';$('urgent-only').checked=false;$('map-top-note').textContent=state.kind==='hopees'?'Nur Gastländer, keine Wohnadressen':'Standorte als ungefähre Bereiche';$('map-legend').hidden=state.kind==='hopees';$('sort-select').hidden=state.kind==='hopees';document.querySelectorAll('[data-route]').forEach(a=>{a.href=new URL(a.dataset.route+'/',root);a.classList.toggle('active',a.dataset.route===state.kind);if(a.dataset.route===state.kind)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});if(push)history.pushState({},'',new URL(state.kind+'/',root));clearRecords();if(state.connected&&state.chapter)loadRecords()}
function clearRecords(){recordRequests.cancel();state.request++;state.recordsScope=null;state.updatedAt=null;state.fetchError='';$('updated-label').textContent='';$('data-notice').hidden=true;map?.closePopup();state.records=[];state.markers.clear();layer?.clearLayers();$('record-count').textContent='–';$('urgent-count').hidden=true;$('nearby-section').hidden=true;$('results-list').replaceChildren();$('refresh-button').disabled=!state.connected||!state.chapter;if(!state.connected)renderEmpty('Öffentlicher Datenstand','Die anonymisierten Kartendaten werden von GitHub geladen.');else if(!state.chapter)renderEmpty('Welches Komitee?','Wähle deinen Wohnort oder dein Komitee, um die passenden Einträge zu sehen.');}
function renderEmpty(title,copy){const box=element('div','empty-state');box.append(element('div','empty-icon','⌖'),element('h3','',title),element('p','',copy));const btn=element('button','primary',state.chapter?'Aktualisieren':'Wohnort oder Komitee wählen');btn.onclick=!state.connected?loadPublic:!state.chapter?openResidence:reloadPublic;box.append(btn);$('results-list').replaceChildren(box)}
function populateChapters(){const options=[element('option','','Bitte auswählen'),...state.chapters.map(c=>{const o=element('option','',c.name);o.value=c.id;return o})];options[0].value='';const all=element('option','','Alle Komitees · Deutschland');all.value='all';$('chapter-select').replaceChildren(...options,all);$('chapter-select').disabled=!state.connected;$('residence-chapter').replaceChildren(...options.map(o=>o.cloneNode(true)));$('residence-chapter').disabled=!state.connected;$('residence-chapter').value=state.residence?.chapterId||'';$('chapter-select').value=state.chapter;if(state.chapter&&$('chapter-select').value!==state.chapter)state.chapter='';updateScope()}
function chapterName(id){return id==='unassigned'?'Komitee noch offen':state.chapters.find(c=>c.id===id)?.name||id||'Komitee noch offen'}
function updateScope(){$('scope-note').textContent=state.chapter==='all'?'Du siehst ausdrücklich alle Komitees.':state.chapter?'Nur Einträge aus '+chapterName(state.chapter):'Wähle deinen Wohnort oder dein Komitee.';$('residence-label').textContent=state.residence?.city|| (state.residence?.chapterId?chapterName(state.residence.chapterId):'Wo wohnst du?')}
function connectionState(ok){$('connection-button').classList.toggle('connected',ok);$('connection-label').textContent=ok?'Öffentliche Karte':state.updatedAt?'Zuletzt geladener Stand':'Datenstand laden'}
function fetchFailed(error,hasPrevious){state.fetchError=(error.message||'Daten konnten nicht geladen werden.')+(hasPrevious?' Du siehst weiterhin den zuletzt erfolgreich geladenen Stand.':'');connectionState(false);refreshStatus()}
async function loadPublic(){
  const job=bootstrapRequests.begin();$('refresh-button').disabled=true;
  try{
    const data=await request('/api/chapters',{signal:job.signal});if(!bootstrapRequests.isCurrent(job))return;
    state.chapters=data.chapters;state.connected=true;await restoreResidence();if(!bootstrapRequests.isCurrent(job))return;
    populateChapters();connectionState(true);
    if(state.chapter)await loadRecords();else{clearRecords();openResidence()}
  }catch(e){if(!bootstrapRequests.isCurrent(job)||e.name==='AbortError')return;state.connected=false;clearRecords();populateChapters();renderEmpty('Datenstand nicht erreichbar',e.message);fetchFailed(e,false)}
  finally{if(bootstrapRequests.isCurrent(job))$('refresh-button').disabled=!state.connected||!state.chapter}
}
async function reloadPublic(){
  if(!state.connected)return loadPublic();
  const job=bootstrapRequests.begin();recordRequests.cancel();state.request++;$('refresh-button').disabled=true;
  try{
    const data=await request('/api/chapters',{signal:job.signal});if(!bootstrapRequests.isCurrent(job))return;
    state.chapters=data.chapters;populateChapters();
    if(state.chapter)await loadRecords();else{clearRecords();openResidence()}
  }catch(e){if(!bootstrapRequests.isCurrent(job)||e.name==='AbortError')return;fetchFailed(e,!!state.updatedAt);if(!state.updatedAt){renderEmpty('Datenstand nicht erreichbar',e.message);$('record-count').textContent='–'}}
  finally{if(bootstrapRequests.isCurrent(job))$('refresh-button').disabled=!state.connected||!state.chapter}
}
function refreshStatus(){const time=new Date(state.manifest?.updatedAt),stale=Number.isFinite(time.valueOf())&&Date.now()-time.valueOf()>24*60*60*1000;$('data-notice').hidden=!state.fetchError&&!stale;$('data-notice').textContent=state.fetchError||'Dieser veröffentlichte Datenstand ist älter als 24 Stunden. Aktuelle Details findest du auf AFSer.';$('sync-info').textContent='Die Website lädt den zuletzt auf GitHub veröffentlichten anonymisierten Datenstand. Der lokale Importer kann aktualisierte Daten veröffentlichen; die Karte bleibt auch ohne ihn erreichbar.';}
async function loadRecords(){
  if(!state.connected||!state.chapter)return;
  const job=recordRequests.begin(),id=++state.request,kind=state.kind,chapter=state.chapter,scope=kind+':'+chapter;
  const hasPrevious=state.recordsScope===scope&&!!state.updatedAt;
  const current=()=>id===state.request&&recordRequests.isCurrent(job)&&state.kind===kind&&state.chapter===chapter;
  if(!hasPrevious){map?.closePopup();layer?.clearLayers();state.markers.clear();state.records=[];state.updatedAt=null;state.recordsScope=null;state.fetchError='';$('updated-label').textContent='';$('data-notice').hidden=true;$('record-count').textContent='…';$('urgent-count').hidden=true;$('nearby-section').hidden=true;$('results-list').replaceChildren(element('div','empty-state','Einträge werden geladen …'))}
  $('refresh-button').disabled=true;
  try{
    const path='/api/records?'+new URLSearchParams({kind,chapter});let data;
    try{data=await request(path,{signal:job.signal})}
    catch(e){
      if(e.code!=='changed'||!current())throw e;
      // A deployment can briefly serve its old manifest with new chapter files.
      const fresh=await request('/api/chapters',{signal:job.signal});if(!current())return;
      state.chapters=fresh.chapters;populateChapters();if(!current()){if(recordRequests.isCurrent(job)&&state.chapter!==chapter){clearRecords();openResidence()}return;}
      data=await request(path,{signal:job.signal});
    }
    if(!current())return;
    state.records=data.records;state.updatedAt=data.updatedAt;state.recordsScope=scope;state.fetchError='';connectionState(true);render();fitMap();refreshStatus();
    $('updated-label').textContent='Stand: '+new Intl.DateTimeFormat('de-DE',{dateStyle:'short',timeStyle:'short'}).format(new Date(data.updatedAt));
  }catch(e){if(!current()||e.name==='AbortError')return;fetchFailed(e,hasPrevious);if(!hasPrevious){renderEmpty('Datenstand nicht erreichbar',e.message);$('record-count').textContent='–'}}
  finally{if(current())$('refresh-button').disabled=false}
}
function distance(r){const a=state.residence?.location,b=r.location;if(!a||!b||state.kind==='hopees')return Infinity;const rad=Math.PI/180;const dLat=(b.lat-a.lat)*rad,dLon=(b.lon-a.lon)*rad;const h=Math.sin(dLat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dLon/2)**2;return 6371*2*Math.atan2(Math.sqrt(h),Math.sqrt(1-h))}
function distanceLabel(r){const d=distance(r);return Number.isFinite(d)?'ca. '+Math.max(1,Math.round(d))+' km':''}
function deadlineLabel(r){if(!/^\d{4}-\d{2}-\d{2}$/.test(r.deadline||''))return '';const d=new Date(r.deadline+'T12:00:00Z');return Number.isNaN(d.valueOf())?'':'bis '+new Intl.DateTimeFormat('de-DE',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'Europe/Berlin'}).format(d)}
function statusLabel(r){return ({open:'Offen',needed:'Interview benötigt',assigned:'In Arbeit',active:'Aktiv',pending:'In Vorbereitung',Participation:'Im Austausch',Preparation:'Vorbereitung',Admission:'Zusage'})[r.status]||r.status||'Aktiv'}
function title(r){if(state.kind==='hopees')return r.country||'Gastland noch offen';return r.city|| (state.kind==='sending'?'Homeinterview':state.kind==='families'?'Gastfamilie':'Hostee')+' · '+chapterName(r.chapterId)}
function recordCard(r){const btn=element('button','record-card'+(r.urgent?' urgent':''));btn.dataset.record=r.id;const top=element('div','card-top');top.append(element('span','card-title',title(r)),element('span','badge'+(r.urgent?' danger':''),r.urgent?'Dringend':statusLabel(r)));btn.append(top,element('div','card-details',state.kind==='hopees'?chapterName(r.chapterId):(r.country? (state.kind==='hostees'?'Aus ':'Gastland: ')+r.country:chapterName(r.chapterId))));const bottom=element('div','card-bottom');bottom.append(element('span',r.urgent?'deadline':'',deadlineLabel(r)||'AFSer-Details verfügbar'),element('span','',distanceLabel(r)));btn.append(bottom);btn.onclick=()=>selectRecord(r,btn);return btn}
function popup(r){const box=element('div','record-popup');box.append(element('span','badge'+(r.urgent?' danger':''),r.urgent?'Dringend':statusLabel(r)),element('h3','popup-heading',title(r)),element('p','popup-row',chapterName(r.chapterId)));if(r.country)box.append(element('p','popup-row',(state.kind==='hostees'?'Herkunftsland: ':'Gastland: ')+r.country));if(r.deadline)box.append(element('p','popup-row',deadlineLabel(r)));if(distanceLabel(r))box.append(element('p','popup-row',distanceLabel(r)+' von deinem Ort'));if(r.location&&state.kind!=='hopees')box.append(element('p','popup-note','Ungefährer Bereich (ca. '+r.location.radiusKm+' km). Die tatsächliche Adresse wird hier nicht angezeigt.'));if(!r.location)box.append(element('p','popup-note','Für diesen Eintrag ist kein bestätigter Kartenstandort verfügbar.'));const link=sourceLink(r.sourceUrl);if(link){const a=element('a','popup-link',state.kind==='sending'?'Interview auf AFSer öffnen':'Details auf AFSer öffnen');a.href=link;a.target='_blank';a.rel='noopener noreferrer';box.append(a,element('p','popup-note',state.kind==='sending'?'Auf AFSer anmelden und dort für das Interview eintragen.':'AFSer-Login erforderlich.'))}else box.append(element('p','popup-note','Für diesen Eintrag fehlt ein bestätigter AFSer-Link.'));return box}
function selectRecord(r,btn){document.querySelectorAll('.record-card.selected').forEach(e=>e.classList.remove('selected'));btn?.classList.add('selected');if(mobileLayout.matches&&map){setMobileView('map');document.querySelector('[data-mobile-view="map"]').focus({preventScroll:true});document.querySelector('.mobile-view-switch').scrollIntoView({block:'start'})}const marker=state.markers.get(r.id);if(marker&&map){map.panTo(marker.getLatLng(),{animate:!mobileLayout.matches});marker.openPopup()}else if(map){L.popup().setLatLng(map.getCenter()).setContent(popup(r)).openOn(map)}else toast('Karte nicht verfügbar. AFSer-Link in den Details.');}
function render(){if(!state.connected||!state.chapter)return;const records=state.records.filter(r=>!$('urgent-only').checked||r.urgent);const sorter=$('sort-select').value;records.sort((a,b)=>sorter==='distance'?distance(a)-distance(b):sorter==='date'?(a.deadline||'9999').localeCompare(b.deadline||'9999'):Number(b.urgent)-Number(a.urgent)||distance(a)-distance(b));$('record-count').textContent=records.length;const urgent=state.records.filter(r=>r.urgent).length;$('urgent-count').hidden=!urgent||state.kind==='hopees';$('urgent-count').textContent=urgent+' dringend';$('results-list').replaceChildren(...records.map(recordCard));if(!records.length)renderEmpty('Hier ist gerade nichts offen',state.kind==='sending'?'Für dieses Komitee sind aktuell keine passenden offenen Sending-Homeinterviews vorhanden.':'Für dieses Komitee sind aktuell keine relevanten aktiven Einträge vorhanden.');renderNearby(records);renderMap(records)}
function renderNearby(records){const nearby=records.filter(r=>Number.isFinite(distance(r))).sort((a,b)=>distance(a)-distance(b)).slice(0,3);$('nearby-section').hidden=!nearby.length||state.kind!=='sending';$('nearby-results').replaceChildren(...nearby.map(r=>{const b=element('button','nearby-row');b.append(element('span','',title(r)),element('span','',distanceLabel(r)));b.onclick=()=>selectRecord(r,document.querySelector('[data-record="'+CSS.escape(r.id)+'"]'));return b}))}
function renderMap(records){if(!map||!layer)return;map.closePopup();layer.clearLayers();state.markers.clear();if(state.kind==='hopees'){const groups=new Map();for(const r of records){if(!r.location)continue;const key=r.country||'Unbekannt';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r)}for(const [country,group] of groups){const loc=group[0].location;const marker=L.marker([loc.lat,loc.lon],{icon:L.divIcon({className:'country-marker',html:String(group.length),iconSize:[36,36],iconAnchor:[18,18]})});const box=element('div','');box.append(element('h3','popup-heading',country),element('p','popup-row',group.length+' aktive Teilnehmende'));const list=element('div','country-popup-list');for(const [index,r] of group.entries()){const url=sourceLink(r.sourceUrl);const a=element(url?'a':'span','country-popup-link');a.append(element('span','','Eintrag '+(index+1)),element('span','',statusLabel(r)));if(url){a.href=url;a.target='_blank';a.rel='noopener noreferrer'}list.append(a);state.markers.set(r.id,marker)}box.append(list,element('p','popup-note','Nur das Gastland wird angezeigt. Einzelne Einträge öffnen die AFSer-Quelle.'));marker.bindPopup(box).addTo(layer)}}else{for(const r of records){if(!r.location||!Number.isFinite(r.location.lat)||!Number.isFinite(r.location.lon))continue;const color=r.urgent?'#bd343c':'#087f79';L.circle([r.location.lat,r.location.lon],{radius:r.location.radiusKm*1000,color,weight:1,opacity:.4,fillColor:color,fillOpacity:.09,interactive:false}).addTo(layer);const marker=L.circleMarker([r.location.lat,r.location.lon],{radius:r.urgent?8:6,fillColor:color,fillOpacity:1,color:'#fff',weight:2}).bindPopup(popup(r)).addTo(layer);state.markers.set(r.id,marker)}}}
function fitMap(){if(!map)return;const points=[...state.markers.values()].map(m=>m.getLatLng());if(points.length)map.fitBounds(L.latLngBounds(points).pad(.25),{maxZoom:state.kind==='hopees'?4:11,animate:!mobileLayout.matches});else if(state.kind==='hopees')map.setView([25,10],2);else if(state.residence?.location&&state.chapter!=='all')map.setView([state.residence.location.lat,state.residence.location.lon],8);else map.setView([51.15,10.45],6)}
$('connection-button').onclick=()=>state.connected&&!state.fetchError?showDialog('privacy-dialog'):reloadPublic();$('residence-button').onclick=openResidence;$('privacy-button').onclick=()=>showDialog('privacy-dialog');$('refresh-button').onclick=reloadPublic;$('fit-map').onclick=fitMap;$('urgent-only').onchange=render;$('sort-select').onchange=render;
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());document.querySelectorAll('[data-route]').forEach(a=>a.onclick=e=>{if(e.ctrlKey||e.metaKey||e.shiftKey)return;e.preventDefault();setRoute(a.dataset.route,true)});document.querySelector('.brand').onclick=e=>{e.preventDefault();setRoute('sending',true)};addEventListener('popstate',()=>setRoute(routeFromPath()));
$('chapter-select').onchange=()=>{state.chapter=$('chapter-select').value;updateScope();clearRecords();if(state.chapter)loadRecords()};
let cityTimer;
function cancelPlaceSearch(){clearTimeout(cityTimer);state.placeRequest++;$('city-options').replaceChildren()}
async function findPlaces(query){try{return (await request('/api/places?'+new URLSearchParams({q:query}))).places||[]}catch{return findPublicPlaces(query)}}
async function restoreResidence(){
  if(state.chapters.some(c=>c.id===state.residence?.chapterId)||state.residence?.chapterId==='all'){state.chapter=state.residence.chapterId;return}
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
function openResidence(){
  cancelPlaceSearch();state.selectedPlace=state.residence?.city?structuredClone(state.residence):null;
  $('city-input').value=state.residence?.city||'';$('residence-chapter').value=state.residence?.chapterId||state.chapter||'';
  $('residence-message').textContent='';showDialog('residence-dialog');
}
function selectPlace(place){
  cancelPlaceSearch();state.selectedPlace=place;$('city-input').value=place.city;$('residence-chapter').value=place.chapterId||'';
  $('residence-message').textContent=place.chapterId?'Komitee gefunden: '+chapterName(place.chapterId):'Für diesen Ort ist kein Komitee bestätigt. Bitte wähle es direkt aus.';
}
$('residence-dialog').addEventListener('close',cancelPlaceSearch);
$('city-input').oninput=()=>{
  state.selectedPlace=null;cancelPlaceSearch();$('residence-chapter').value='';
  const query=$('city-input').value.trim(),id=state.placeRequest;
  $('residence-message').textContent=query.length<2?'Mindestens zwei Buchstaben oder Ziffern eingeben.':'Orte werden gesucht …';
  if(query.length<2)return;
  cityTimer=setTimeout(async()=>{
    try{const places=await findPlaces(query);if(id!==state.placeRequest)return;
      $('city-options').replaceChildren(...places.map(place=>{const b=element('button','city-option',place.label||place.city);b.type='button';
        if(place.chapterId)b.append(element('small','',chapterName(place.chapterId)));b.onclick=()=>selectPlace(place);return b}));
      $('residence-message').textContent=places.length?'Bitte einen Ort aus der Liste wählen.':'Kein passender Ort gefunden. Prüfe die Schreibweise oder wähle dein Komitee direkt.';
    }catch{if(id===state.placeRequest)$('residence-message').textContent='Ortsuche gerade nicht verfügbar. Bitte erneut versuchen oder dein Komitee direkt wählen.'}
  },250);
};
$('residence-chapter').onchange=()=>{cancelPlaceSearch();if(state.selectedPlace?.chapterId&&state.selectedPlace.chapterId!==$('residence-chapter').value)state.selectedPlace=null;if(!state.selectedPlace)$('city-input').value='';$('residence-message').textContent=''};
$('residence-form').onsubmit=async e=>{
  e.preventDefault();const b=e.submitter,id=state.placeRequest;b.disabled=true;
  try{
    let place=state.selectedPlace;
    if(!place&&$('city-input').value.trim()){
      const query=$('city-input').value.trim(),places=await findPlaces(query);
      const exact=places.filter(p=>searchKey(p.city)===searchKey(query)||p.postalCode===query);
      if(exact.length!==1){$('residence-message').textContent='Bitte einen eindeutigen Ort aus der Vorschlagsliste wählen.';return}place=exact[0];
    }
    if(id!==state.placeRequest)return;
    const chapter=$('residence-chapter').value||place?.chapterId||'';
    if(!chapter){$('residence-message').textContent='Bitte wähle einen gefundenen Ort oder dein Komitee.';return}
    state.residence=place?{city:place.city,postalCode:place.postalCode,chapterId:chapter,location:place.location}:{chapterId:chapter};
    storage.set('afs-public-residence',JSON.stringify(state.residence));state.chapter=chapter;$('chapter-select').value=chapter;updateScope();$('residence-dialog').close();clearRecords();fitMap();await loadRecords();
  }catch{$('residence-message').textContent='Ort konnte nicht gespeichert werden. Bitte erneut versuchen.'}finally{b.disabled=false}
};
initMap();setMobileView('list');setRoute(state.kind);updateScope();loadPublic();
if(location.hash)history.replaceState({},'',location.pathname+location.search);storage.remove('afs-token',true);storage.remove('afs-api');
setInterval(()=>{if(state.connected&&state.chapter&&!document.hidden)reloadPublic()},5*60*1000);
