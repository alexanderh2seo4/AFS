import assert from 'node:assert/strict';
import test from 'node:test';
import {DataError,latestRequest,publicDataStore,readJSON} from '../../docs/assets/data-client.js';

const response = data => new Response(JSON.stringify(data), {headers:{'content-type':'application/json'}});
const manifest = time => ({version:1,updatedAt:time,chapters:[{id:'MUC',name:'München'},{id:'FRE',name:'Freiburg'}],defaultChapterId:'MUC'});
const t1 = '2026-10-05T05:00:00Z', t2 = '2026-10-05T06:00:00Z';
const record = (chapter='MUC') => ({id:'a'.repeat(20),kind:'sending',chapterId:chapter,status:'open',urgent:false,sourceUrl:'https://www.afser.de/ereignis-liste/avtproject/42.html'});
const chapter = (time=t1,id='MUC') => ({updatedAt:time,chapter:id,records:{sending:[record(id)],awayees:[],hostees:[],families:[]}});
const deferred = () => {let resolve; const promise=new Promise(r=>resolve=r);return {promise,resolve};};

test('offline, HTTP errors, HTML200 and broken JSON never become an empty dataset',async()=>{
  for(const fetchImpl of [async()=>{throw Error('private request details');},async()=>new Response('',{status:503}),async()=>new Response('<html>error</html>',{headers:{'content-type':'text/html'}}),async()=>new Response('{',{headers:{'content-type':'application/json'}})]){
    await assert.rejects(readJSON('https://example.invalid/data.json',{fetchImpl}),e=>e instanceof DataError&&!e.message.includes('private'));
  }
});
test('a stalled fetch times out, while user cancellation remains distinguishable',async()=>{
  const stall=(_url,{signal})=>new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')),{once:true}));
  await assert.rejects(readJSON('https://example.invalid',{fetchImpl:stall,timeoutMs:10}),e=>e.code==='timeout');
  const controller=new AbortController(); const pending=readJSON('https://example.invalid',{fetchImpl:stall,signal:controller.signal});controller.abort();
  await assert.rejects(pending,e=>e.name==='AbortError');
});
test('latest-request guard rejects an older response even if its fetch ignores abort',()=>{
  const requests=latestRequest(),old=requests.begin(),latest=requests.begin();
  assert.equal(old.signal.aborted,true);assert.equal(requests.isCurrent(old),false);assert.equal(requests.isCurrent(latest),true);
  requests.cancel();assert.equal(requests.isCurrent(latest),false);
});
test('chapter routes are scoped, malformed documents fail closed, successful retries work',async()=>{
  const queue=[response(manifest(t1)),response({...chapter(),chapter:'FRE'}),response(chapter())];
  const urls=[];const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async u=>{urls.push(String(u));return queue.shift();}});
  await store.refresh();await assert.rejects(store.records('sending','MUC'),e=>e.code==='invalid');
  assert.equal((await store.records('sending','MUC')).records.length,1);
  assert.equal(urls.length,3);assert.match(urls[2],/\/AFS\/data\/chapters\/MUC.json\?v=/);
  await assert.rejects(store.records('sending','unknown'),e=>e.code==='invalid');
});
test('a failed refresh preserves the last validated manifest and chapter cache',async()=>{
  let offline=false;const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async u=>{if(offline)throw Error('offline');return response(String(u).includes('manifest')?manifest(t1):chapter());}});
  await store.refresh();await store.records('sending','MUC');offline=true;
  await assert.rejects(store.refresh());assert.equal(store.manifest.updatedAt,t1);assert.equal((await store.records('sending','MUC')).records.length,1);
});
test('refresh while a chapter fetch is pending cannot reinsert the old generation',async()=>{
  const pending=deferred();let manifestCalls=0;
  const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async u=>String(u).includes('manifest')?response(manifest(++manifestCalls===1?t1:t2)):String(u).includes(encodeURIComponent(t1))?pending.promise:response(chapter(t2))});
  await store.refresh();const old=store.records('sending','MUC');await store.refresh();pending.resolve(response(chapter(t1)));
  await assert.rejects(old,e=>e.name==='AbortError');assert.equal((await store.records('sending','MUC')).updatedAt,t2);
});
test('mixed CDN snapshot, private fields, wrong chapters and missing kinds are refused',async()=>{
  for(const bad of [chapter(t2),{...chapter(),records:{sending:[]}},{...chapter(),records:{...chapter().records,sending:[{...record(),name:'Private fixture'}]}},{...chapter(),records:{...chapter().records,sending:[record('FRE')]}}]){
    const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async u=>response(String(u).includes('manifest')?manifest(t1):bad)});
    await store.refresh();await assert.rejects(store.records('sending','MUC'),DataError);
  }
});
test('chapter documents using hopees category are accepted and normalized to awayees',async()=>{
  const legacyChapter={updatedAt:t1,chapter:'MUC',records:{sending:[record('MUC')],hopees:[{id:'d'.repeat(20),kind:'hopees',chapterId:'MUC',status:'active',sourceUrl:'https://www.afser.de/fixture'}],hostees:[],families:[]}};
  const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async u=>response(String(u).includes('manifest')?manifest(t1):legacyChapter)});
  await store.refresh();
  const res=await store.records('awayees','MUC');
  assert.equal(res.records.length,1);
  assert.equal(res.records[0].kind,'awayees');
  assert.equal(res.records[0].id,'d'.repeat(20));
  const resHopees=await store.records('hopees','MUC');
  assert.equal(resHopees.records.length,1);
  assert.equal(resHopees.records[0].kind,'awayees');
});
test('a failed shared geography download can be retried',async()=>{
  let reads=0;const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async u=>String(u).includes('manifest')?response(manifest(t1)):++reads===1?new Response('',{status:503}):response({places:[['80331','München','MUC',48.13,11.57,'80331']]})});
  await store.refresh();await assert.rejects(store.places());assert.equal((await store.places()).length,1);
});

test('geography must match the published generation and contain valid chapter coordinates',async()=>{
  const generation='b'.repeat(64),row=['postal-fixture','München','MUC',48.13,11.57,'80331'];
  for(const data of [{places:[row],generation:'c'.repeat(64)},{places:[[...row.slice(0,3),999,11.57,'80331']],generation},{places:[[...row.slice(0,2),'unknown',...row.slice(3)]],generation},{places:[row.slice(0,5)],generation}]){
    const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async u=>response(String(u).includes('manifest')?{...manifest(t1),generation}:data)});
    await store.refresh();await assert.rejects(store.places(),DataError);
  }
});

test('committee availability comes from validated records per section and reuses the aggregate',async()=>{
  const all={...chapter(t1,'all'),records:{sending:[record('MUC'),{...record('FRE'),id:'b'.repeat(20)},{...record('unassigned'),id:'c'.repeat(20)}],awayees:[],hostees:[{...record('FRE'),id:'d'.repeat(20),kind:'hostees'}],families:[]}};
  const reads=[];const store=publicDataStore('https://example.invalid/AFS/',{fetchImpl:async url=>{reads.push(String(url));return response(String(url).includes('manifest')?manifest(t1):all)}});
  await store.refresh();
  assert.deepEqual(await store.availableChapterIds(),{sending:['MUC','FRE','unassigned'],awayees:[],hostees:['FRE'],families:[]});
  await store.availableChapterIds();await store.records('sending','all');
  assert.equal(reads.filter(url=>url.includes('/chapters/')).length,1);
});
