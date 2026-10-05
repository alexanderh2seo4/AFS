#!/usr/bin/env python3
"""Update anonymous GitHub snapshots while the private importer stays local."""
import argparse
import datetime
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.private-data'
STATE = PRIVATE / 'public-update-status.json'
STOP = threading.Event()


def save(**items):
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    state.update(items)
    state['checkedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    temp = STATE.with_suffix('.tmp')
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(state, stream)
    temp.replace(STATE)


def checked(args, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('operation_failed')
    return result.stdout


def publish(sync=False,follow_main=False):
    if follow_main:
        for repository in (ROOT, ROOT/'mcp'):
            if checked(['git','status','--porcelain','--untracked-files=no'],cwd=repository).strip():
                raise RuntimeError('working_tree_changes_present')
            checked(['git','pull','--ff-only','origin','main'],cwd=repository)
    uv = shutil.which('uv') or str(Path.home() / '.local/bin/uv')
    command = [uv,'run','--project',str(ROOT/'mcp'),'afser-data','--data-dir',str(PRIVATE)]
    if sync:
        checked(command+['sync'])
    checked(command+['export-public','--output',str(ROOT/'docs/data')])
    checked([sys.executable,str(ROOT/'scripts/publish_github.py'),'audit'])
    if checked(['git','diff','--cached','--name-only']).strip():
        raise RuntimeError('staged_changes_present')
    checked(['git','add','--','docs/data'])
    paths=checked(['git','diff','--cached','--name-only']).splitlines()
    if any(not p.startswith('docs/data/') for p in paths):
        raise RuntimeError('unexpected_staged_path')
    if paths:
        checked(['git','commit','-m','Update anonymous AFS map data'])
    checked([sys.executable,str(ROOT/'scripts/publish_github.py'),'push-site'])
    save(lastSuccessAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),error=None)
    print('Anonymous GitHub snapshot published.',flush=True)


def run(interval=1800, initial=False, follow_main=False):
    descriptor = os.open(PRIVATE/'public-update.lock',os.O_RDWR|os.O_CREAT,0o600)
    fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM,lambda *_:STOP.set())
    signal.signal(signal.SIGINT,lambda *_:STOP.set())
    save(running=True,pid=os.getpid(),intervalSeconds=interval)
    try:
        first = initial
        while first or not STOP.wait(interval):
            first = False
            try:
                publish(sync=True,follow_main=follow_main)
            except Exception:
                save(error='update_failed_previous_public_snapshot_retained')
                print('Update failed; previous public snapshot retained.',flush=True)
    finally:
        save(running=False,pid=None)
        os.close(descriptor)


def background(interval=1800, initial=False, follow_main=False):
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    if state.get('running') and state.get('pid'):
        try:
            os.kill(state['pid'],0)
            raise RuntimeError('already_running')
        except ProcessLookupError:
            pass
    log=os.open(PRIVATE/'public-update.log',os.O_APPEND|os.O_CREAT|os.O_WRONLY,0o600)
    try:
        args=[sys.executable,str(Path(__file__).resolve()),'run','--interval',str(interval)]
        if initial:args.append('--initial-sync')
        if follow_main:args.append('--follow-main')
        process=subprocess.Popen(args,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        try:
            process.wait(timeout=1)
            raise RuntimeError('startup_failed')
        except subprocess.TimeoutExpired:
            print(f'Public-data updater started; interval {interval} seconds.')
    finally:
        os.close(log)


def stop():
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    pid=state.get('pid')
    if not isinstance(pid,int) or pid<=1:
        raise RuntimeError('not_running')
    meta=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
    if str(Path(__file__).resolve())+' run' not in meta.stdout:
        raise RuntimeError('not_running')
    os.kill(pid,signal.SIGTERM)
    print('Local public-data updater shutdown requested.')


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['once','sync-and-publish','run','background','status','stop'])
    parser.add_argument('--interval',type=int,default=1800,help='seconds between completed imports (minimum 60)')
    parser.add_argument('--initial-sync',action='store_true',help='import immediately when starting the continuous worker')
    parser.add_argument('--follow-main',action='store_true',help='fast-forward the dedicated server checkout before each import')
    args=parser.parse_args()
    if args.interval<60:parser.error('interval must be at least 60 seconds')
    try:
        if args.action=='once':publish()
        elif args.action=='sync-and-publish':publish(sync=True)
        elif args.action=='run':run(args.interval,args.initial_sync,args.follow_main)
        elif args.action=='background':background(args.interval,args.initial_sync,args.follow_main)
        elif args.action=='stop':stop()
        else:
            state=json.loads(STATE.read_text()) if STATE.exists() else {}
            if state.get('pid'):
                try:os.kill(state['pid'],0)
                except ProcessLookupError:state['running']=False
            print(json.dumps({k:v for k,v in state.items() if k!='pid'}))
    except Exception:
        print('Public update could not complete; no private output was printed.',file=sys.stderr)
        raise SystemExit(1) from None


if __name__=='__main__':main()
