export const DEFAULT_RESIDENCE = Object.freeze({city:'München',postalCode:'80331',location:{lat:48.1374,lon:11.5755}});

export function searchKey(value){
  const key=String(value).trim().toLocaleLowerCase('de').normalize('NFKD').replace(/\p{M}/gu,'').replace(/ß/g,'ss').replace(/ae/g,'a').replace(/oe/g,'o').replace(/ue/g,'u').replace(/[^a-z0-9]+/g,' ').trim();
  return key==='munich'?'munchen':key;
}

let indexPromise;
export async function findPublicPlaces(query,chapterRows=[]){
  if(!indexPromise)indexPromise=import('./locations-de.js').then(({default:data})=>data.rows).catch(error=>{indexPromise=null;throw error});
  return searchPlaces(await indexPromise,query,chapterRows);
}

export function searchPlaces(rows,query,chapterRows=[]){
  const key=searchKey(query);
  if(key.length<2||key.length>80)return [];
  const postal=/^\d+$/.test(key);
  const chapters=new Map(chapterRows.map(row=>[String(row[5]||row[0]),row[2]]));
  const groups=new Map();
  for(const [code,city,region,lat,lon] of rows){
    const cityKey=searchKey(city);
    if(postal?!code.startsWith(key):!cityKey.startsWith(key)&&!cityKey.split(' ').some(word=>word.startsWith(key)))continue;
    const chapterId=chapters.get(code)||null;
    const id=[cityKey,region,chapterId||'',postal?code:''].join('|');
    if(!groups.has(id))groups.set(id,{id,city,region,chapterId,postalCode:code,location:{lat:0,lon:0},count:0,rank:postal?(code===key?0:1):(cityKey===key?0:cityKey.startsWith(key)?1:2)});
    const place=groups.get(id);place.location.lat+=lat;place.location.lon+=lon;place.count++;
  }
  return [...groups.values()].sort((a,b)=>a.rank-b.rank||a.city.localeCompare(b.city,'de')||a.region.localeCompare(b.region,'de')||a.postalCode.localeCompare(b.postalCode)).slice(0,20).map(({count,rank,...place})=>({...place,label:place.city+' · '+(postal?place.postalCode+' · ':'')+place.region,location:{lat:place.location.lat/count,lon:place.location.lon/count}}));
}
