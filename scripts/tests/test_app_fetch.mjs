import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {visibleRecords,hasOpenInterview} from '../../docs/assets/record-filters.js';
import {latestRequest,publicDataStore} from '../../docs/assets/data-client.js';

// Exercise the real application fetch functions with a minimal DOM, and actual
// data-client validation. All records here are invented, with no private store.
const source=(await readFile(new URL('../../docs/assets/app.js',import.meta.url),'utf8')).replace(/^import .*;\n/gm,'').split('initMap();setMobileView(')[0];
const t1='2026-10-05T05:00:00Z',t2='2026-10-05T06:00:00Z';
const manifest=(time=t1)=>({version:1,updatedAt:time,chapters:[{id:'MUC',name:'München'},{id:'FRE',name:'Freiburg'}],defaultChapterId:'MUC'});
const sendingRecord=id=>({id:(id==='MUC'?'a':'b').repeat(20),kind:'sending',chapterId:id,status:'open',urgent:true,city:'Fixture',sourceUrl:'https://www.afser.de/ereignis-liste/avtproject/42.html'});
const hosteeRecord={id:'c'.repeat(20),kind:'hostees',chapterId:'FRE',status:'active',sourceUrl:'https://www.afser.de/fixture'};
const chapter=(id='MUC',time=t1)=>({chapter:id,updatedAt:time,records:{sending:id==='all'?['MUC','FRE'].map(sendingRecord):[sendingRecord(id)],awayees:[],hostees:id==='all'||id==='FRE'?[hosteeRecord]:[],families:[]}});
const chapterForURL=(url,time=t1)=>chapter(String(url).includes('/all.json')?'all':String(url).includes('/FRE.json')?'FRE':'MUC',time);

const response=data=>new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
class Element{
  constructor(){this.textContent='';this.value='';this.hidden=false;this.disabled=false;this.children=[];this.dataset={};this.classList={add(){},remove(){},toggle(){}}}
  append(...items){this.children.push(...items)}
  replaceChildren(...items){this.children=items}
  setAttribute(){} removeAttribute(){} addEventListener(){} close(){} showModal(){}
  cloneNode(){const e=new Element();e.textContent=this.textContent;e.value=this.value;return e}
}
function app(fetchImpl,saved={}){
  const preferences=new Map(Object.entries(saved));
  const elements=new Map();const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
  get('sort-select').value='distance';
  const document={getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>[],querySelector:get,body:new Element()};
  const context=vm.createContext({document,location:{pathname:'/AFS/sending/'},localStorage:{getItem:key=>preferences.get(key)||null,setItem:(key,value)=>preferences.set(key,value)},sessionStorage:{getItem(){return null}},URL,URLSearchParams,Intl,Date,Map,Set,structuredClone,globalThis:{},matchMedia:()=>({matches:false,addEventListener(){}}),ResizeObserver:class{observe(){}},requestAnimationFrame:()=>{},addEventListener(){},setTimeout,clearTimeout,visibleRecords,hasOpenInterview,latestRequest,publicDataStore:(root)=>publicDataStore(root,{fetchImpl}),DEFAULT_RESIDENCE:{city:'München',location:{lat:48.13,lon:11.57}},searchKey:s=>s.toLowerCase().replace('ü','u'),findPublicPlaces:async()=>[]});
  vm.runInContext(source.replace('import.meta.url',"'https://example.invalid/AFS/assets/app.js'"),context);
  return {get,preference:key=>preferences.get(key),run:code=>vm.runInContext(code,context)};
}
test('failed manifest and chapter refresh retain the previous view and show its error',async()=>{
  let failure='';const ui=app(async u=>failure==='manifest'&&String(u).includes('manifest')||failure==='chapter'&&String(u).includes('chapters/')?new Response('',{status:503}):response(String(u).includes('manifest')?manifest():chapterForURL(u)));
  await ui.run('loadPublic()');assert.equal(ui.get('record-count').textContent,1);const date=ui.get('updated-label').textContent;
  for(const mode of ['manifest','chapter']){failure=mode;await ui.run('reloadPublic()');assert.equal(ui.get('record-count').textContent,1);assert.equal(ui.get('updated-label').textContent,date);assert.equal(ui.get('data-notice').hidden,false);assert.match(ui.get('data-notice').textContent,/zuletzt erfolgreich/);assert.equal(ui.get('refresh-button').disabled,false)}
  failure='';await ui.run('reloadPublic()');assert.equal(ui.run('state.fetchError'),'');assert.equal(ui.get('connection-label').textContent,'Öffentliche Karte');
});
test('initial failure is retryable from the connection button',async()=>{
  let offline=true;const ui=app(async u=>offline?new Response('',{status:503}):response(String(u).includes('manifest')?manifest():chapterForURL(u)));
  await ui.run('loadPublic()');assert.equal(ui.run('state.connected'),false);assert.equal(ui.get('record-count').textContent,'–');
  offline=false;await ui.get('connection-button').onclick();assert.equal(ui.run('state.connected'),true);assert.equal(ui.get('record-count').textContent,1);
});
test('slow chapter response cannot replace a newer chapter selection',async()=>{
  let resolve;const delayed=new Promise(r=>resolve=r);const ui=app(async u=>String(u).includes('manifest')?response(manifest()):String(u).includes('/FRE.json')?delayed:response(chapterForURL(u)));
  await ui.run('loadPublic()');const old=ui.run("state.chapter='FRE';clearRecords();loadRecords()");
  await ui.run("state.chapter='MUC';clearRecords();loadRecords()");resolve(response(chapter('FRE')));await old;
  assert.equal(ui.run('state.records[0].chapterId'),'MUC');assert.equal(ui.get('record-count').textContent,1);assert.equal(ui.get('refresh-button').disabled,false);
});
test('switching route clears the old count, urgency, timestamp and records on failure',async()=>{
  let offline=false;const ui=app(async u=>offline?new Response('',{status:503}):response(String(u).includes('manifest')?manifest():chapterForURL(u)));
  await ui.run('loadPublic()');offline=true;
  // setRoute starts its asynchronous read, and loadRecords exercises the same
  // supersession path when another selection arrives before that read finishes.
  await ui.run("state.chapter='FRE';setRoute('hostees');loadRecords()");
  assert.equal(ui.run('state.records.length'),0);assert.equal(ui.get('record-count').textContent,'–');assert.equal(ui.get('urgent-count').hidden,true);assert.equal(ui.get('updated-label').textContent,'');
});
test('a mixed deployment refreshes its manifest once before retrying the chapter',async()=>{
  let manifests=0,chapterReads=0;const ui=app(async u=>String(u).includes('manifest')?response(manifest(++manifests===1?t1:t2)):(chapterReads++,response(chapterForURL(u,t2))));
  await ui.run('loadPublic()');assert.equal(manifests,2);assert.equal(chapterReads,3);assert.equal(ui.run('state.updatedAt'),t2);assert.equal(ui.get('record-count').textContent,1);
});

test('all available clears urgency, loads every chapter including unassigned interviews, and preserves residence',async()=>{
  const all={...chapter('all'),records:{...chapter().records,sending:['MUC','FRE','unassigned'].map((id,index)=>({...chapter(id).records.sending[0],id:String(index+1).repeat(20)}))}};
  const urls=[];
  const ui=app(async url=>{urls.push(String(url));return response(String(url).includes('manifest')?manifest():String(url).includes('/all.json')?all:chapter());});
  await ui.run('loadPublic()');
  const residence=ui.run('JSON.stringify(state.residence)');ui.get('urgent-only').checked=true;
  await ui.get('show-all-button').onclick();
  assert.equal(ui.run('state.chapter'),'all');assert.equal(ui.get('chapter-select').value,'all');
  assert.equal(ui.get('urgent-only').checked,false);assert.equal(ui.get('record-count').textContent,3);
  assert.equal(ui.preference('afs-public-chapter'),'all');assert.equal(ui.run('JSON.stringify(state.residence)'),residence);
  assert(urls.some(url=>/\/chapters\/all.json/.test(url)));
  await ui.run("setRoute('families');loadRecords()");
  assert.equal(ui.run('state.chapter'),'all');assert.equal(ui.get('chapter-select').value,'all');
});
test('saved nationwide scope survives bootstrap instead of being reset to the residence chapter',async()=>{
  const all={...chapter('all'),records:{...chapter().records,sending:[chapter().records.sending[0]]}};
  const ui=app(async url=>response(String(url).includes('manifest')?manifest():all),{'afs-public-chapter':'all'});
  await ui.run('loadPublic()');assert.equal(ui.run('state.chapter'),'all');assert.equal(ui.get('record-count').textContent,1);
});

test('picker shows only committees with data for the current section and falls back to all when the selected committee is empty',async()=>{
  const ui=app(async url=>response(String(url).includes('manifest')?manifest():chapterForURL(url)));
  await ui.run('loadPublic()');
  assert.deepEqual(ui.get('chapter-select').children.map(option=>option.value),['','all','MUC','FRE']);
  await ui.run("setRoute('hostees');loadRecords()");
  assert.deepEqual(ui.get('chapter-select').children.map(option=>option.value),['','all','FRE']);
  assert.equal(ui.run('state.chapter'),'all');assert.equal(ui.get('record-count').textContent,1);
  assert.equal(ui.run('state.residence.city'),'München');
  await ui.run("setRoute('families');loadRecords()");
  assert.deepEqual(ui.get('chapter-select').children.map(option=>option.value),['','all']);
  assert.equal(ui.get('record-count').textContent,0);
});

test('navigation sync updates returnees, brand and route links to canonical absolute URLs', async () => {
  const ui = app(async u => response(manifest()));
  ui.run(`
    const brand = { href: './', className: 'brand' };
    const route = { href: 'hostees/', dataset: { route: 'hostees' }, classList: { toggle(){}, add(){}, remove(){} }, setAttribute(){}, removeAttribute(){} };
    const ret = { href: 'returnees/', textContent: 'Returnees', classList: { toggle(){}, add(){}, remove(){} }, setAttribute(){}, removeAttribute(){} };
    const contact = { href: 'Kontaktformular/', className: 'contact-form-link' };
    document.querySelectorAll = selector => {
      if (selector === '.brand') return [brand];
      if (selector === '[data-route]') return [route];
      if (selector === 'nav a') return [route, ret];
      if (selector.includes('Kontaktformular')) return [contact];
      return [];
    };
    syncNavigation();
    globalThis.__navResult = { brandHref: brand.href, routeHref: route.href, retHref: ret.href, contactHref: contact.href };
  `);
  const result = ui.run('globalThis.__navResult');
  assert.equal(result.brandHref, 'https://example.invalid/AFS/');
  assert.equal(result.routeHref, 'https://example.invalid/AFS/hostees/');
  assert.equal(result.retHref, 'https://example.invalid/AFS/returnees/');
  assert.equal(result.contactHref, 'https://example.invalid/AFS/Kontaktformular/');
});
