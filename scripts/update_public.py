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


def publish(sync=False):
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


def run():
    descriptor = os.open(PRIVATE/'public-update.lock',os.O_RDWR|os.O_CREAT,0o600)
    fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM,lambda *_:STOP.set())
    signal.signal(signal.SIGINT,lambda *_:STOP.set())
    save(running=True,pid=os.getpid(),intervalSeconds=1800)
    try:
        # Initial snapshot is published explicitly before this service starts.
        while not STOP.wait(1800):
            try:
                publish(sync=True)
            except Exception:
                save(error='update_failed_previous_public_snapshot_retained')
                print('Update failed; previous public snapshot retained.',flush=True)
    finally:
        save(running=False,pid=None)
        os.close(descriptor)


def background():
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    if state.get('running') and state.get('pid'):
        try:
            os.kill(state['pid'],0)
            raise RuntimeError('already_running')
        except ProcessLookupError:
            pass
    log=os.open(PRIVATE/'public-update.log',os.O_APPEND|os.O_CREAT|os.O_WRONLY,0o600)
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        try:
            process.wait(timeout=1)
            raise RuntimeError('startup_failed')
        except subprocess.TimeoutExpired:
            print('Local public-data updater started; interval 30 minutes, current login session.')
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
    args=parser.parse_args()
    try:
        if args.action=='once':publish()
        elif args.action=='sync-and-publish':publish(sync=True)
        elif args.action=='run':run()
        elif args.action=='background':background()
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
