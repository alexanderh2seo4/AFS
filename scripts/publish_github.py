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
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OWNER = "AFS-MUC"
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
        login = self.request("GET", "/user").get("login")
        if login == OWNER:
            return
        membership = self.request("GET", f"/user/memberships/orgs/{OWNER}", missing_ok=True)
        if membership and membership.get("state") == "active" and membership.get("role") in {"admin", "member"}:
            return
        raise PublishError("The Git credential helper is signed in to an account without required access.")


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
        user_login = api.request("GET", "/user").get("login")
        create_path = "/user/repos" if OWNER == user_login else f"/orgs/{OWNER}/repos"
        repo = api.request("POST", create_path, {
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
    banned_suffixes = {".sqlite", ".sqlite3", ".db", ".csv", ".tsv", ".xlsx", ".log", ".zip", ".tgz", ".png", ".jpg", ".jpeg", ".pdf"}
    blocked = []
    for filename in files:
        path = Path(filename)
        full = directory / path
        allowed_root = path.parts[0] in {"src", "tests"} if mcp else path.parts[0] in {"docs", "scripts"}
        allowed_name = filename in ({"README.md", "pyproject.toml", "uv.lock", ".gitignore", "LICENSE"} if mcp else {"README.md", "AFSER_ACCESS.md", ".gitignore", "LICENSE"})
        allowed_returnees_workbook = not mcp and (
            filename == "docs/data/returnees.xlsx"
            or re.fullmatch(r"docs/data/returnees/archive/20\d{2}-(?:0[1-9]|1[0-2])\.xlsx", filename)
        )
        if (not allowed_root and not allowed_name) or banned_parts.intersection(path.parts) or (path.suffix.lower() in banned_suffixes and not allowed_returnees_workbook) or path.name in {".afser-password", "invite.html", "source.json", "tokens.json", "bridge.json", "data.json"} or (path.name.startswith(".env") and path.name != ".env.example") or full.is_symlink():
            blocked.append(filename)
    if blocked:
        raise PublishError("Refusing to publish private or unexpected tracked paths: " + ", ".join(blocked))
    if not mcp:
        audit_contact_config(directory / "docs/assets/contact-config.json")
    if not mcp and (directory / 'docs/data').exists():
        audit_public_data(directory / 'docs/data')
    return len(files)


def audit_contact_config(path):
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        fields = {"enabled", "apiBaseUrl", "purpose", "retentionText", "privacyContact", "noticeVersion"}
        if set(data) != fields or type(data["enabled"]) is not bool:
            raise ValueError()
        for field, limit in (("apiBaseUrl", 500), ("purpose", 500), ("retentionText", 1000), ("privacyContact", 254), ("noticeVersion", 80)):
            if not isinstance(data[field], str) or len(data[field]) > limit:
                raise ValueError()
        endpoint = data["apiBaseUrl"]
        if endpoint:
            parsed = urlsplit(endpoint)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or "*" in endpoint:
                raise ValueError()
        if data["enabled"] and (not endpoint or not all(data[field].strip() for field in ("purpose", "retentionText", "privacyContact", "noticeVersion"))):
            raise ValueError()
    except Exception:
        raise PublishError("The public contact configuration failed its privacy audit.") from None


RETURN_HEADERS = ["Anonymer Schlüssel", "Austauschjahr", "AFS-Seminar 1", "AFS-Seminar 2", "Alle Camps absolviert"]
RETURN_NOTE = "Ein Seminar gilt als absolviert, wenn das entsprechende AFS-Seminarfeld in AFSer ausgefüllt ist. Nur mit diesem AFSer-Zugang erreichbare Returnees."
XLSX_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def audit_returnees_xlsx(path):
    required_parts = {
        "[Content_Types].xml", "_rels/.rels", "docProps/core.xml", "docProps/app.xml",
        "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml",
        "xl/worksheets/sheet1.xml", "xl/worksheets/_rels/sheet1.xml.rels", "xl/tables/table1.xml",
    }
    try:
        with zipfile.ZipFile(path) as workbook:
            if set(workbook.namelist()) != required_parts or workbook.testzip() is not None:
                raise PublishError("The returnee workbook contains unexpected or damaged parts.")
            workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
            sheets = workbook_xml.findall(f"{{{XLSX_MAIN}}}sheets/{{{XLSX_MAIN}}}sheet")
            if len(sheets) != 1 or sheets[0].get("name") != "Returnees" or sheets[0].get("state", "visible") != "visible":
                raise PublishError("The returnee workbook failed its sheet audit.")
            sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
            if sheet.find(f".//{{{XLSX_MAIN}}}f") is not None or sheet.find(f".//{{{XLSX_MAIN}}}hyperlinks") is not None:
                raise PublishError("The returnee workbook contains an unapproved formula or link.")
            table = ET.fromstring(workbook.read("xl/tables/table1.xml"))
            if table.get("name") != "ReturneesTable" or table.get("displayName") != "ReturneesTable":
                raise PublishError("The returnee workbook failed its table audit.")
            table_columns = table.findall(f"{{{XLSX_MAIN}}}tableColumns/{{{XLSX_MAIN}}}tableColumn")
            if [column.get("name") for column in table_columns] != RETURN_HEADERS:
                raise PublishError("The returnee workbook contains unapproved columns.")
            table_ref = table.get("ref", "")
            if not re.fullmatch(r"A5:E(?:[5-9]|[1-9][0-9]+)", table_ref):
                raise PublishError("The returnee workbook has an invalid table range.")
            cells = {}
            for row in sheet.findall(f"{{{XLSX_MAIN}}}sheetData/{{{XLSX_MAIN}}}row"):
                for cell in row.findall(f"{{{XLSX_MAIN}}}c"):
                    ref = cell.get("r", "")
                    if cell.get("t") == "inlineStr":
                        value = "".join(node.text or "" for node in cell.findall(f".//{{{XLSX_MAIN}}}t"))
                    else:
                        value_node = cell.find(f"{{{XLSX_MAIN}}}v")
                        value = value_node.text if value_node is not None else None
                        if cell.get("t") == "b" and value is not None:
                            value = value == "1"
                    cells[ref] = value
            if cells.get("A1") != "AFS Returnees" or not isinstance(cells.get("A2"), str) or not cells["A2"].startswith("Datenstand: ") or cells.get("A3") != RETURN_NOTE:
                raise PublishError("The returnee workbook failed its privacy-note audit.")
            last_row = int(table_ref.split(":", 1)[1][1:])
            if table_ref != f"A5:E{last_row}" or last_row != max(5, max((int(re.search(r"\d+$", ref).group()) for ref in cells if re.match(r"^[A-E]\d+$", ref)), default=5)):
                raise PublishError("The returnee workbook contains data outside its approved table.")
            if [cells.get(f"{column}5") for column in "ABCDE"] != RETURN_HEADERS:
                raise PublishError("The returnee workbook headers do not match its table definition.")
            records = []
            seen = set()
            for row_number in range(6, last_row + 1):
                values = [cells.get(f"{column}{row_number}") for column in "ABCDE"]
                alias, year, seminar1, seminar2, complete = values
                if not isinstance(alias, str) or not re.fullmatch(r"[a-f0-9]{20}", alias) or alias in seen:
                    raise PublishError("The returnee workbook contains an invalid anonymous key.")
                if year is not None:
                    if not re.fullmatch(r"(?:19|20|21)\d{2}", str(year)):
                        raise PublishError("The returnee workbook contains an invalid year.")
                    year = int(year)
                if seminar1 not in {"Absolviert", "Nicht eingetragen"} or seminar2 not in {"Absolviert", "Nicht eingetragen"} or complete not in {"Ja", "Nein"}:
                    raise PublishError("The returnee workbook contains an invalid camp status.")
                if (complete == "Ja") != (seminar1 == "Absolviert" and seminar2 == "Absolviert"):
                    raise PublishError("The returnee workbook has an inconsistent camp status.")
                seen.add(alias)
                records.append([alias, year, seminar1, seminar2, complete])
            if len(records) != last_row - 5:
                raise PublishError("The returnee workbook table row count is inconsistent.")
            return records
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, ValueError, TypeError, AttributeError):
        raise PublishError("The returnee workbook failed its privacy and structure audit.") from None


def audit_public_data(root):
    fields={'id','kind','chapterId','status','urgent','deadline','country','sourceUrl','city','location','hasOpenRoles','pickedAt'}
    manifest=json.loads((root/'manifest.json').read_text())
    if set(manifest) != {'version','updatedAt','chapters','counts','defaultChapterId','defaultResidence','privacy','generation'} or manifest['version'] != 1 or not re.fullmatch(r'[a-f0-9]{64}',manifest.get('generation','')):
        raise PublishError('The public map manifest failed its field audit.')
    returnees = json.loads((root / 'returnees.json').read_text()) if (root / 'returnees.json').is_file() else None
    if returnees is None or set(returnees) != {'version','updatedAt','scope','archiveMonths','records','generation'} or returnees.get('version') != 1 or returnees.get('scope') != 'afser-accessible' or not isinstance(returnees.get('updatedAt'),str) or not re.fullmatch(r'[a-f0-9]{64}',returnees.get('generation','')):
        raise PublishError('The public returnee manifest failed its field audit.')
    if not isinstance(returnees.get('archiveMonths'),list) or any(not isinstance(month,str) or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',month) for month in returnees['archiveMonths']) or returnees['archiveMonths'] != sorted(set(returnees['archiveMonths'])) or not isinstance(returnees.get('records'),list):
        raise PublishError('The public returnee archive index failed its field audit.')
    return_fields={'id','year','seminar1Completed','seminar2Completed','allCampsCompleted'}
    return_ids=set()
    for record in returnees.get('records',[]):
        if not isinstance(record,dict) or set(record)!=return_fields or not re.fullmatch(r'[0-9a-f]{20}',record.get('id','')) or record['id'] in return_ids:
            raise PublishError('The public returnee data failed its field audit.')
        if record['year'] is not None and (type(record['year']) is not int or not 1900 <= record['year'] <= 2100):
            raise PublishError('The public returnee year failed its field audit.')
        if any(type(record[key]) is not bool for key in ('seminar1Completed','seminar2Completed','allCampsCompleted')) or record['allCampsCompleted'] != (record['seminar1Completed'] and record['seminar2Completed']):
            raise PublishError('The public returnee camp fields failed their field audit.')
        return_ids.add(record['id'])
    archive_paths=set()
    for path in root.rglob('*'):
        if path.is_dir():continue
        relative=path.relative_to(root)
        if path.is_symlink():raise PublishError('Unexpected public map file.')
        if path.suffix.lower()=='.xlsx':
            if relative.as_posix()=='returnees.xlsx':
                rows=audit_returnees_xlsx(path)
                expected=[]
                for record in returnees['records']:
                    expected.append([record['id'],record['year'],'Absolviert' if record['seminar1Completed'] else 'Nicht eingetragen','Absolviert' if record['seminar2Completed'] else 'Nicht eingetragen','Ja' if record['allCampsCompleted'] else 'Nein'])
                if rows!=expected:raise PublishError('The current returnee workbook does not match its JSON dataset.')
                continue
            if len(relative.parts)==3 and relative.parts[:2]==('returnees','archive') and re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])\.xlsx',path.name):
                audit_returnees_xlsx(path);archive_paths.add(path.stem);continue
            raise PublishError('Unexpected public workbook path.')
        if path.suffix!='.json':raise PublishError('Unexpected public map file.')
        data=json.loads(path.read_text())
        if relative.as_posix()=='manifest.json':continue
        if relative.as_posix()=='returnees.json':
            continue
        if relative.as_posix()=='places.json':
            if set(data)!={'places','generation'} or data['generation']!=manifest['generation'] or any(not isinstance(row,list) or len(row)!=6 for row in data['places']):
                raise PublishError('The public locality file failed its field audit.')
            continue
        if len(relative.parts)!=2 or relative.parts[0]!='chapters' or not re.fullmatch(r'[A-Za-z0-9_-]+',path.stem) or set(data)!={'chapter','updatedAt','records','generation'} or data['generation']!=manifest['generation']:
            raise PublishError('Unexpected public map dataset path or fields.')
        if set(data['records'])!={'sending','awayees','hostees','families'}:raise PublishError('Unexpected public map category.')
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
                if location and (set(location)-{'lat','lon','radiusKm','scope'} or location.get('radiusKm')!=(0 if kind=='awayees' else 1)):
                    raise PublishError('Unapproved public location fields or radius.')
    if archive_paths!=set(returnees['archiveMonths']) or 'returnees.xlsx' not in {path.relative_to(root).as_posix() for path in root.rglob('*.xlsx')}:
        raise PublishError('The public returnee workbooks do not match the archive index.')


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
