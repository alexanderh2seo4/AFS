#!/usr/bin/env python3
"""Publish code and explicitly approved anonymous maps without credentials.

Status is read-only. Every mutation requires an explicit command. Personal data,
access files, logs, binaries and invites must remain in ignored local storage.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "alexanderh2seo4"
SITE_REPO = "AFS"
MCP_REPO = "afser-mcp"


class PublishError(Exception):
    pass


class GitHub:
    def __init__(self):
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode:
            raise PublishError("GitHub credentials are unavailable in the Git credential helper.")
        credential = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        self._token = credential.get("password")
        if not self._token:
            raise PublishError("GitHub credentials are unavailable in the Git credential helper.")

    def request(self, method, path, payload=None, missing_ok=False):
        if not path.startswith("/") or path.startswith("//"):
            raise PublishError("Invalid GitHub API path.")
        request = urllib.request.Request(
            "https://api.github.com" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            method=method,
            headers={
                "Authorization": "Bearer " + self._token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "afs-code-only-publisher",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            if error.code == 404 and missing_ok:
                return None
            # Never dump responses, headers, request objects or credential values.
            raise PublishError(f"GitHub API returned HTTP {error.code} for {method} {path}.") from None
        except (urllib.error.URLError, TimeoutError):
            raise PublishError("GitHub API is unavailable; check the network and retry.") from None

    def check_owner(self):
        if self.request("GET", "/user").get("login") != OWNER:
            raise PublishError("The Git credential helper is signed in to a different GitHub account.")


def repository_summary(repo):
    if repo is None:
        return {"exists": False}
    return {
        "exists": True,
        "name": repo.get("full_name"),
        "visibility": repo.get("visibility"),
        "defaultBranch": repo.get("default_branch"),
        "hasPages": repo.get("has_pages", False),
        "canPush": bool(repo.get("permissions", {}).get("push")),
        "canAdminister": bool(repo.get("permissions", {}).get("admin")),
    }


def status(api):
    result = {}
    for name in (SITE_REPO, MCP_REPO):
        repo = api.request("GET", f"/repos/{OWNER}/{name}", missing_ok=True)
        result[name] = repository_summary(repo)
    pages = api.request("GET", f"/repos/{OWNER}/{SITE_REPO}/pages", missing_ok=True)
    if pages is None:
        result["pages"] = {"enabled": False}
    else:
        builds = api.request("GET", f"/repos/{OWNER}/{SITE_REPO}/pages/builds?per_page=10", missing_ok=True) or []
        build_counts = {}
        for build in builds:
            key = build.get("status", "unknown")
            build_counts[key] = build_counts.get(key, 0) + 1
        result["pages"] = {
            "enabled": True,
            "url": pages.get("html_url"),
            "status": pages.get("status"),
            "source": pages.get("source"),
            "recentBuildCount": len(builds),
            "recentBuildStatuses": build_counts,
        }
    print(json.dumps(result, indent=2))


def ensure_mcp_repo(api):
    repo = api.request("GET", f"/repos/{OWNER}/{MCP_REPO}", missing_ok=True)
    if repo is None:
        repo = api.request("POST", "/user/repos", {
            "name": MCP_REPO,
            "description": "Local AFSER sync, anonymous volunteer map API and MCP server; code only",
            "private": False,
            "auto_init": False,
            "has_wiki": False,
            "has_projects": False,
        })
    if repo.get("private") or repo.get("full_name") != f"{OWNER}/{MCP_REPO}":
        raise PublishError("The MCP repository does not match the expected public code-only repository.")
    print(json.dumps(repository_summary(repo)))


def ensure_pages(api, branch, path):
    remote_branch = api.request("GET", f"/repos/{OWNER}/{SITE_REPO}/branches/{branch}", missing_ok=True)
    if remote_branch is None:
        raise PublishError("Push the publishing branch before configuring GitHub Pages.")
    source_path = path.strip("/")
    entry = f"{source_path}/index.html" if source_path else "index.html"
    entry_exists = api.request("GET", f"/repos/{OWNER}/{SITE_REPO}/contents/{entry}?ref={branch}", missing_ok=True)
    if entry_exists is None:
        raise PublishError("The publishing source must contain index.html on GitHub first.")
    existing = api.request("GET", f"/repos/{OWNER}/{SITE_REPO}/pages", missing_ok=True)
    wanted = {"branch": branch, "path": path}
    if existing is None:
        existing = api.request("POST", f"/repos/{OWNER}/{SITE_REPO}/pages", {"source": wanted})
    elif existing.get("source") != wanted or existing.get("build_type") == "workflow":
        api.request("PUT", f"/repos/{OWNER}/{SITE_REPO}/pages", {"build_type": "legacy", "source": wanted})
        existing = api.request("GET", f"/repos/{OWNER}/{SITE_REPO}/pages")
    print(json.dumps({"enabled": True, "url": existing.get("html_url"), "status": existing.get("status"), "source": existing.get("source")}))


def audit_tracked(directory, mcp=False):
    result = subprocess.run(["git", "ls-files", "-z"], cwd=directory, capture_output=True, check=True)
    files = [item.decode() for item in result.stdout.split(b"\0") if item]
    if not files:
        raise PublishError("The repository has no tracked code to publish.")
    banned_parts = {".private-data", ".venv", "node_modules", "__pycache__", ".git"}
    banned_suffixes = {".sqlite", ".sqlite3", ".db", ".csv", ".tsv", ".log", ".zip", ".tgz", ".png", ".jpg", ".jpeg", ".pdf"}
    blocked = []
    for filename in files:
        path = Path(filename)
        full = directory / path
        allowed_root = path.parts[0] in {"src", "tests"} if mcp else path.parts[0] in {"docs", "scripts"}
        allowed_name = filename in ({"README.md", "pyproject.toml", "uv.lock", ".gitignore", "LICENSE"} if mcp else {"README.md", "AFSER_ACCESS.md", ".gitignore", "LICENSE"})
        if (not allowed_root and not allowed_name) or banned_parts.intersection(path.parts) or path.suffix.lower() in banned_suffixes or path.name in {".afser-password", "invite.html", "source.json", "tokens.json", "bridge.json", "data.json"} or (path.name.startswith(".env") and path.name != ".env.example") or full.is_symlink():
            blocked.append(filename)
    if blocked:
        raise PublishError("Refusing to publish private or unexpected tracked paths: " + ", ".join(blocked))
    if not mcp and (directory / 'docs/data').exists():
        audit_public_data(directory / 'docs/data')
    return len(files)


def audit_public_data(root):
    fields={'id','kind','chapterId','status','urgent','deadline','country','sourceUrl','city','location','hasOpenRoles','pickedAt'}
    manifest=json.loads((root/'manifest.json').read_text())
    if set(manifest) != {'version','updatedAt','chapters','counts','defaultChapterId','defaultResidence','privacy','generation'} or manifest['version'] != 1 or not re.fullmatch(r'[a-f0-9]{64}',manifest.get('generation','')):
        raise PublishError('The public map manifest failed its field audit.')
    for path in root.rglob('*'):
        if path.is_dir():continue
        relative=path.relative_to(root)
        if path.is_symlink() or path.suffix!='.json':raise PublishError('Unexpected public map file.')
        data=json.loads(path.read_text())
        if relative.as_posix()=='manifest.json':continue
        if relative.as_posix()=='places.json':
            if set(data)!={'places','generation'} or data['generation']!=manifest['generation'] or any(not isinstance(row,list) or len(row)!=6 for row in data['places']):
                raise PublishError('The public locality file failed its field audit.')
            continue
        if len(relative.parts)!=2 or relative.parts[0]!='chapters' or not re.fullmatch(r'[A-Za-z0-9_-]+',path.stem) or set(data)!={'chapter','updatedAt','records','generation'} or data['generation']!=manifest['generation']:
            raise PublishError('Unexpected public map dataset path or fields.')
        if set(data['records'])!={'sending','hopees','hostees','families'}:raise PublishError('Unexpected public map category.')
        for kind, records in data['records'].items():
            for record in records:
                if set(record)-fields or record.get('kind')!=kind or not re.fullmatch(r'[0-9a-f]{20}',record.get('id','')):
                    raise PublishError('Unapproved field in public map record.')
                if not record.get('sourceUrl','').startswith('https://www.afser.de/'):
                    raise PublishError('Unapproved public source URL.')
                if 'hasOpenRoles' in record and (kind!='sending' or type(record['hasOpenRoles']) is not bool):
                    raise PublishError('Invalid public interview role metadata.')
                if 'pickedAt' in record:
                    try:
                        valid=kind=='sending' and record['status']=='assigned' and date.fromisoformat(record['pickedAt']).isoformat()==record['pickedAt']
                    except (ValueError,TypeError):
                        valid=False
                    if not valid:raise PublishError('Invalid public pickup date.')
                location=record.get('location')
                if location and (set(location)-{'lat','lon','radiusKm','scope'} or location.get('radiusKm')!=(0 if kind=='hopees' else 1)):
                    raise PublishError('Unapproved public location fields or radius.')


def push(directory, repo, branch, mcp=False):
    expected = f"https://github.com/{OWNER}/{repo}.git"
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=directory, text=True, capture_output=True, check=True).stdout.strip()
    if remote not in {expected, f"git@github.com:{OWNER}/{repo}.git"}:
        raise PublishError("The repository origin does not match the expected GitHub destination.")
    count = audit_tracked(directory, mcp=mcp)
    subprocess.run(["git", "push", "origin", f"HEAD:{branch}"], cwd=directory, check=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    print(json.dumps({"pushed": True, "repository": f"{OWNER}/{repo}", "branch": branch, "trackedCodeFiles": count}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="read sanitized repository, Pages and recent build metadata")
    sub.add_parser("ensure-mcp-repo", help="create the empty public MCP code repository if absent")
    pages = sub.add_parser("ensure-pages", help="enable Pages from existing static code on GitHub")
    pages.add_argument("--branch", default="main")
    pages.add_argument("--path", choices=("/docs", "/"), default="/docs")
    site_push = sub.add_parser("push-site", help="audit tracked paths and push committed site code")
    site_push.add_argument("--branch", default="main")
    mcp_push = sub.add_parser("push-mcp", help="audit tracked paths and push committed MCP code")
    mcp_push.add_argument("--branch", default="main")
    sub.add_parser("audit", help="audit tracked site filenames without reading private data")
    args = parser.parse_args()
    try:
        if args.command == "audit":
            print(json.dumps({"trackedCodeFiles": audit_tracked(ROOT)}))
            return
        if args.command == "push-site":
            push(ROOT, SITE_REPO, args.branch)
            return
        if args.command == "push-mcp":
            push(ROOT / "mcp", MCP_REPO, args.branch, mcp=True)
            return
        api = GitHub()
        api.check_owner()
        if args.command == "status":
            status(api)
        elif args.command == "ensure-mcp-repo":
            ensure_mcp_repo(api)
        else:
            ensure_pages(api, args.branch, args.path)
    except (PublishError, OSError, subprocess.CalledProcessError) as error:
        message = str(error) if isinstance(error, PublishError) else "Local Git command failed; check the repository setup."
        print(message, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
