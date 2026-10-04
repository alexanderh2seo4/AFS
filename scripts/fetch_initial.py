"""Fetch national API payloads automatically; output counts/schema only, never records."""
import json, os, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from discover_source import connect, PRIVATE, BASE
TASKS = ['getAllChapters', 'getAllRegions', 'getAllStudents', 'getAllFamiliesWithStudents', 'getHostingPotentialFamilies', 'getAllHostingStudentProfiles', 'getAllFwdStudents', 'getAllInterviews']

def keys(value, prefix='', depth=0):
    found = set()
    if depth>5: return found
    if isinstance(value, dict):
        for k,v in value.items():
            path=prefix+'.'+k if prefix else k
            found.add(path); found.update(keys(v,path,depth+1))
    elif isinstance(value,list):
        for item in value: found.update(keys(item,prefix+'[]',depth+1))
    return found

if __name__=='__main__':
    opener,_=connect()
    folder=PRIVATE/'initial';folder.mkdir(exist_ok=True,mode=0o700)
    for task in TASKS:
        try:
            url=BASE+'/index.php?option=com_participantslist&controller=participantslist&task='+task+'&format=json'
            raw=opener.open(url,timeout=120).read()
            obj=json.loads(raw)
            target=folder/(task+'.json');target.write_bytes(raw);os.chmod(target,0o600)
            records=obj.get('records',[]) if isinstance(obj,dict) else []
            if isinstance(records,str):
                try: records=json.loads(records)
                except: records=[]
            print(json.dumps({'task':task,'count':len(records) if isinstance(records,list) else None,'error':bool(obj.get('error')) if isinstance(obj,dict) else True,'schema':sorted(keys(records))},ensure_ascii=False),flush=True)
        except Exception as e: print(json.dumps({'task':task,'errorType':type(e).__name__}),flush=True)
