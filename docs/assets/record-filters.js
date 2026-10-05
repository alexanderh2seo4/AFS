export const RECENT_PICK_DAYS=30;
export function hasOpenInterview(record){return record.hasOpenRoles??record.status==='open'}
export function pickedRecently(record,now=new Date()){
  if(!record.pickedAt||record.status!=='assigned')return false;
  const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
  const picked=Date.parse(record.pickedAt),age=Date.parse(today)-picked;
  return Number.isFinite(picked)&&age>=0&&age<=RECENT_PICK_DAYS*24*60*60*1000;
}
export function visibleRecords(records,kind,mode,now=new Date()){
  if(kind==='hopees')return records.filter(r=>mode==='all'||r.status===(mode==='pending'?'pending':'active'));
  if(kind==='sending')return records.filter(r=>mode==='open'?hasOpenInterview(r):mode==='recent'?pickedRecently(r,now):mode==='assigned'?r.status==='assigned':true);
  return records;
}
