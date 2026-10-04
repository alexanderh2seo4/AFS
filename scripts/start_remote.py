#!/usr/bin/env python3
"""Supervise a private loopback bridge and a temporary HTTPS Quick Tunnel.

The dataset and invite stay on this computer. Quick Tunnel URLs change after a
restart and have no uptime guarantee. Use a named tunnel for a stable endpoint.
"""

import argparse
import datetime
import fcntl
import hashlib
import io
import json
import os
import plistlib
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".private-data"
LABEL = "de.afser.maps.local"
WEBSITE = "https://alexanderh2seo4.github.io/AFS/"
TUNNEL_PATTERN = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com")
STATE = PRIVATE / "remote-state.json"
STOP = threading.Event()


class RemoteError(Exception):
    pass


def private_directory(path):
    if path.is_symlink():
        raise RemoteError("A private directory must not be a symlink.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def private_write(path, content):
    private_directory(path.parent)
    if path.is_symlink():
        raise RemoteError("A private configuration file must not be a symlink.")
    temp = path.with_name("." + path.name + f".{os.getpid()}.tmp")
    descriptor = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content.encode() if isinstance(content, str) else content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        path.chmod(0o600)
    finally:
        temp.unlink(missing_ok=True)


def read_config(path, default):
    if not path.exists():
        return default
    if path.is_symlink():
        raise RemoteError("A private configuration file must not be a symlink.")
    return json.loads(path.read_text())


def get_url(url, limit=2_000_000):
    request = urllib.request.Request(url, headers={"User-Agent": "afs-local-map-supervisor"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise RemoteError("The download exceeds its expected size.")
        return data


def download_cloudflared():
    if sys.platform != "darwin" or os.uname().machine != "arm64":
        raise RemoteError("This download command supports macOS arm64 only.")
    release = json.loads(get_url("https://api.github.com/repos/cloudflare/cloudflared/releases/latest"))
    asset = next((item for item in release.get("assets", ()) if item.get("name") == "cloudflared-darwin-arm64.tgz"), None)
    if not asset or release.get("draft") or release.get("prerelease"):
        raise RemoteError("The official cloudflared release does not contain the required stable asset.")
    digest = asset.get("digest", "")
    url = asset.get("browser_download_url", "")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest) or not url.startswith("https://github.com/cloudflare/cloudflared/releases/download/"):
        raise RemoteError("The official release is missing a valid SHA-256 digest or download URL.")
    archive = get_url(url, limit=60_000_000)
    archive_hash = hashlib.sha256(archive).hexdigest()
    if archive_hash != digest.split(":", 1)[1]:
        raise RemoteError("The official cloudflared archive failed SHA-256 verification.")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        members = [member for member in tar.getmembers() if member.name.lstrip("./") == "cloudflared"]
        if len(members) != 1 or not members[0].isfile() or members[0].size > 100_000_000:
            raise RemoteError("The verified cloudflared archive has an unexpected layout.")
        stream = tar.extractfile(members[0])
        if stream is None:
            raise RemoteError("The verified archive does not contain a regular binary.")
        binary = stream.read()
    destination = private_directory(PRIVATE / "bin") / "cloudflared"
    private_write(destination, binary)
    destination.chmod(0o700)
    body_match = re.search(r"cloudflared-darwin-arm64\.tgz:\s*([a-f0-9]{64})", release.get("body", ""))
    body_hash = body_match.group(1) if body_match else None
    metadata = {
        "release": release.get("tag_name"),
        "source": url,
        "archiveSha256": archive_hash,
        "binarySha256": hashlib.sha256(binary).hexdigest(),
        "verifiedAgainstGitHubAssetDigest": True,
        "releaseBodyChecksumMatches": body_hash == archive_hash if body_hash else None,
    }
    private_write(PRIVATE / "cloudflared-release.json", json.dumps(metadata, indent=2))
    print(json.dumps({"installed": str(destination), "release": metadata["release"], "sha256Verified": True, "releaseBodyChecksumMatches": metadata["releaseBodyChecksumMatches"]}))


def validate_website(website):
    url = urlsplit(website)
    if url.scheme != "https" or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise RemoteError("The hosted website must be an HTTPS URL without credentials or parameters.")
    try:
        with urllib.request.urlopen(urllib.request.Request(website, headers={"User-Agent": "afs-local-map-supervisor"}), timeout=20) as response:
            if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                raise RemoteError("The hosted website is not available yet.")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        raise RemoteError("The hosted website is not available yet; publish and verify GitHub Pages first.") from None


def prepare(website):
    validate_website(website)
    private_directory(PRIVATE)
    if not (PRIVATE / "bin" / "cloudflared").is_file():
        raise RemoteError("Download the verified cloudflared binary first.")
    uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    if not Path(uv).is_file() or not (ROOT / "mcp" / "pyproject.toml").exists():
        raise RemoteError("The uv runtime or local MCP project is unavailable.")
    bridge = read_config(PRIVATE / "bridge.json", {})
    bridge["pollSeconds"] = 1800
    origin = urlsplit(website)
    origins = bridge.get("origins", ["http://localhost:5173", "http://127.0.0.1:5173"])
    bridge["origins"] = list(dict.fromkeys([*origins, f"{origin.scheme}://{origin.netloc}"]))
    private_write(PRIVATE / "bridge.json", json.dumps(bridge, indent=2))
    config = {"website": website.rstrip("/") + "/", "uv": str(Path(uv).resolve()), "port": int(bridge.get("port", 8765))}
    private_write(PRIVATE / "remote-config.json", json.dumps(config, indent=2))
    return config


def update_state(**items):
    state = read_config(STATE, {})
    state.update(items)
    state["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    private_write(STATE, json.dumps(state, indent=2))


def command(config, action, *extra):
    return [config["uv"], "run", "--project", str(ROOT / "mcp"), "afser-data", "--data-dir", str(PRIVATE), action, *extra]


def loopback_ready(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def terminate(process):
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def read_tunnel(process, events):
    # Discard raw tunnel output. It can contain host and network metadata.
    for line in process.stdout:
        match = TUNNEL_PATTERN.search(line)
        if match:
            events.put(match.group(0))


def refresh_invite(config, endpoint):
    bridge = read_config(PRIVATE / "bridge.json", {})
    bridge["remoteHosts"] = [host for host in bridge.get("remoteHosts", ()) if not host.endswith(".trycloudflare.com")]
    private_write(PRIVATE / "bridge.json", json.dumps(bridge, indent=2))
    result = subprocess.run(command(config, "invite", "--website", config["website"], "--endpoint", endpoint, "--label", "owner"), capture_output=True, text=True)
    if result.returncode:
        raise RemoteError("The backend could not generate a private map invite.")
    # The CLI writes the token only into the private invite. Never forward stdout.
    update_state(endpoint=endpoint, invitePath=str(PRIVATE / "invite.html"), inviteReady=True)
    print(f"Private invite refreshed: {PRIVATE / 'invite.html'}", flush=True)


def run(config):
    os.umask(0o077)
    lock = os.open(PRIVATE / "remote-run.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock)
        raise RemoteError("The AFS map supervisor is already running.") from None
    service = tunnel = None
    logs = private_directory(PRIVATE / "launch")
    log_path = logs / "service.log"
    log_descriptor = os.open(log_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    with os.fdopen(log_descriptor, "ab", buffering=0) as service_log:
        signal.signal(signal.SIGTERM, lambda *_: STOP.set())
        signal.signal(signal.SIGINT, lambda *_: STOP.set())
        try:
            if loopback_ready(config["port"]):
                raise RemoteError("The map API port is already occupied; stop the previous local service first.")
            update_state(running=True, supervisorPid=os.getpid(), website=config["website"], inviteReady=False, endpoint=None, mode="temporary-quick-tunnel")
            while not STOP.is_set():
                if service is None or service.poll() is not None:
                    terminate(tunnel)
                    tunnel = None
                    service = subprocess.Popen(command(config, "serve"), stdout=service_log, stderr=subprocess.STDOUT, start_new_session=True)
                    deadline = time.monotonic() + 60
                    while not loopback_ready(config["port"]) and service.poll() is None and time.monotonic() < deadline and not STOP.wait(0.5):
                        pass
                    if STOP.is_set():
                        break
                    if service.poll() is not None or not loopback_ready(config["port"]):
                        terminate(service)
                        service = None
                        update_state(inviteReady=False, error="local_service_unavailable")
                        STOP.wait(10)
                        continue
                if tunnel is None or tunnel.poll() is not None:
                    terminate(tunnel)
                    update_state(inviteReady=False, endpoint=None)
                    tunnel = subprocess.Popen([str(PRIVATE / "bin" / "cloudflared"), "tunnel", "--url", f"http://127.0.0.1:{config['port']}", "--no-autoupdate"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
                    events = queue.Queue()
                    threading.Thread(target=read_tunnel, args=(tunnel, events), daemon=True).start()
                    deadline = time.monotonic() + 90
                    endpoint = None
                    while time.monotonic() < deadline and tunnel.poll() is None and not STOP.is_set():
                        try:
                            endpoint = events.get(timeout=0.5)
                            break
                        except queue.Empty:
                            pass
                    if not endpoint:
                        terminate(tunnel)
                        tunnel = None
                        update_state(error="tunnel_unavailable", inviteReady=False)
                        STOP.wait(10)
                        continue
                    refresh_invite(config, endpoint)
                    update_state(error=None, servicePid=service.pid, tunnelPid=tunnel.pid)
                STOP.wait(2)
        finally:
            terminate(tunnel)
            terminate(service)
            update_state(running=False, inviteReady=False, supervisorPid=None, servicePid=None, tunnelPid=None)
            os.close(lock)


def launch_target():
    return f"gui/{os.getuid()}/{LABEL}"


def owned_plist():
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def install(config):
    if sys.platform != "darwin":
        raise RemoteError("Persistent launchctl setup requires macOS.")
    plist_path = owned_plist()
    existing = subprocess.run(["launchctl", "print", launch_target()], capture_output=True)
    if plist_path.exists() or plist_path.is_symlink() or existing.returncode == 0:
        raise RemoteError("The launchctl label or plist already exists; this tool will not overwrite it.")
    private_directory(PRIVATE / "launch")
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    config_plist = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "run"],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 15,
        "ProcessType": "Background",
        "Umask": 0o077,
        "StandardOutPath": str(PRIVATE / "launch" / "supervisor.log"),
        "StandardErrorPath": str(PRIVATE / "launch" / "supervisor-error.log"),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "AFSER_PRIVATE_DIR": str(PRIVATE)},
    }
    fd = os.open(plist_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        plistlib.dump(config_plist, stream)
    result = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)], capture_output=True)
    if result.returncode:
        plist_path.unlink()
        raise RemoteError("launchctl could not start the private map supervisor.")
    print(f"Installed {LABEL}. Current private invite: {PRIVATE / 'invite.html'}")


def stop(uninstall=False):
    path = owned_plist()
    if not path.is_file() or path.is_symlink():
        raise RemoteError("No supervisor plist owned by this project exists.")
    with path.open("rb") as stream:
        data = plistlib.load(stream)
    if data.get("Label") != LABEL or data.get("ProgramArguments", [None, None])[1:2] != [str(Path(__file__).resolve())]:
        raise RemoteError("The launchctl plist belongs to another setup and will not be changed.")
    subprocess.run(["launchctl", "bootout", launch_target()], capture_output=True)
    if uninstall:
        path.unlink()
    print("Private map supervisor stopped." + (" LaunchAgent removed." if uninstall else " Use the start command to re-enable it."))


def start(restart=False):
    path = owned_plist()
    if not path.is_file() or path.is_symlink():
        raise RemoteError("No supervisor plist owned by this project exists.")
    with path.open("rb") as stream:
        data = plistlib.load(stream)
    if data.get("Label") != LABEL or data.get("ProgramArguments", [None, None])[1:2] != [str(Path(__file__).resolve())]:
        raise RemoteError("The launchctl plist belongs to another setup and will not be changed.")
    active = subprocess.run(["launchctl", "print", launch_target()], capture_output=True).returncode == 0
    if not active:
        result = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], capture_output=True)
    elif restart:
        # KeepAlive launches a replacement after the supervisor has gracefully
        # stopped its child process groups. A forced kill could orphan them.
        result = subprocess.run(["launchctl", "kill", "SIGTERM", launch_target()], capture_output=True)
    else:
        print("The private map LaunchAgent is already enabled.")
        return
    if result.returncode:
        raise RemoteError("launchctl could not start the private map supervisor.")
    print(f"Private map supervisor {'restarted' if restart else 'started'}. Reopen {PRIVATE / 'invite.html'} for the current invite.")


def status():
    data = read_config(STATE, {})
    keys = ("running", "mode", "website", "inviteReady", "invitePath", "updatedAt", "error")
    summary = {key: data[key] for key in keys if key in data}
    pid = data.get("supervisorPid")
    if pid:
        try:
            os.kill(int(pid), 0)
        except (OSError, ValueError):
            summary["running"] = False
            summary["inviteReady"] = False
    summary["installed"] = owned_plist().exists()
    print(json.dumps(summary, indent=2))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="download and SHA-256 verify the official macOS arm64 cloudflared asset")
    for action in ("prepare", "install"):
        choice = sub.add_parser(action, help="configure without launching" if action == "prepare" else "configure and start a persistent private LaunchAgent")
        choice.add_argument("--website", default=WEBSITE)
    sub.add_parser("run", help="run the previously prepared supervisor in the foreground")
    sub.add_parser("status", help="show only sanitized supervisor metadata")
    sub.add_parser("start", help="restart the project's stopped LaunchAgent without replacing it")
    sub.add_parser("restart", help="restart the project's LaunchAgent and refresh its temporary invite")
    sub.add_parser("stop", help="stop the project's own LaunchAgent")
    sub.add_parser("uninstall", help="stop and remove the project's own LaunchAgent")
    args = parser.parse_args()
    try:
        if args.command == "download":
            download_cloudflared()
        elif args.command == "status":
            status()
        elif args.command in {"stop", "uninstall"}:
            stop(uninstall=args.command == "uninstall")
        elif args.command in {"start", "restart"}:
            start(restart=args.command == "restart")
        elif args.command in {"prepare", "install"}:
            config = prepare(args.website)
            if args.command == "install":
                install(config)
            else:
                print("Private supervisor configured. No service or tunnel was started.")
        else:
            config = read_config(PRIVATE / "remote-config.json", None)
            if not config:
                raise RemoteError("Prepare or install the private supervisor first.")
            run(config)
    except (RemoteError, OSError, ValueError, urllib.error.URLError, subprocess.SubprocessError) as error:
        print(str(error) if isinstance(error, RemoteError) else "Private supervisor setup failed; check the local configuration.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
