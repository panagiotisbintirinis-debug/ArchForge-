"""Updates of the packaged program (owner 18/10: «πρέπει να είναι updatable»).

The Windows package (.github/workflows/windows-package.yml) carries ``build_info.json`` with the commit it was built
from; every push to develop republishes the «ArchForge (develop)» release with a new zip.  The program compares the
two and, when the human agrees, downloads the zip, closes, copies the new files over its own folder and starts again.
Projects and the imported library live outside the program folder, so they stay as they are.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request
import zipfile

REPO = "panagiotisbintirinis-debug/ArchForge-"
RELEASE_TAG = "develop-latest"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}"
ASSET = "ArchForge-windows.zip"


def packaged():
    return bool(getattr(sys, "frozen", False))


def program_dir():
    return os.path.dirname(sys.executable)


last_check_error = None     # why the last check could not answer (Α3: «failed» is not «up to date»)


def current_build():
    """``{"sha": …, "date": …}`` of this package, or None when running from source."""
    if not packaged():
        return None
    path = os.path.join(getattr(sys, "_MEIPASS", program_dir()), "build_info.json")
    global last_check_error
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        last_check_error = f"δεν διαβάστηκε η έκδοση του προγράμματος ({exc})"
        return None


def _fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "ArchForge"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def latest_release(fetch=_fetch_json):
    """``{"sha", "url", "size", "published"}`` of the published package, or None (no release, no network)."""
    global last_check_error
    try:
        rel = fetch(RELEASE_API)
    except Exception as exc:
        last_check_error = f"δεν απάντησε το GitHub ({exc})"
        return None
    asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET), None)
    if asset is None:
        return None
    return {"sha": rel.get("target_commitish", ""), "url": asset["browser_download_url"],
            "size": int(asset.get("size", 0)), "published": rel.get("published_at", "")}


def available_update(build=None, fetch=_fetch_json):
    """The newer release, or None: up to date, running from source, or no answer from GitHub."""
    global last_check_error
    last_check_error = None
    build = build if build is not None else current_build()
    if not build or not build.get("sha"):
        return None
    rel = latest_release(fetch)
    if rel is None or not rel["sha"] or rel["sha"] == build["sha"]:
        return None
    return rel


def download(url, progress=None, chunk=1 << 20):
    """Download and unpack the package; returns the folder holding the new ArchForge.exe."""
    work = tempfile.mkdtemp(prefix="archforge-update-")
    zpath = os.path.join(work, ASSET)
    req = urllib.request.Request(url, headers={"User-Agent": "ArchForge"})
    with urllib.request.urlopen(req, timeout=60) as r, open(zpath, "wb") as out:
        total, done = int(r.headers.get("Content-Length") or 0), 0
        while True:
            block = r.read(chunk)
            if not block:
                break
            out.write(block)
            done += len(block)
            if progress is not None and progress(done, total) is False:
                raise InterruptedError("ακυρώθηκε")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(work)
    os.remove(zpath)
    for root, _dirs, files in os.walk(work):
        if "ArchForge.exe" in files:
            return root
    raise ValueError("το πακέτο δεν έχει ArchForge.exe")


def install_script(new_dir, target_dir, pid):
    """A .cmd that waits for this program to close, copies the new files over it and starts it again."""
    path = os.path.join(tempfile.gettempdir(), "archforge-update.cmd")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "@echo off\r\n"
            ":wait\r\n"
            f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul && (timeout /t 1 >nul & goto wait)\r\n'
            # /E: copy everything, delete nothing — a file the human left in the program folder survives.
            f'robocopy "{new_dir}" "{target_dir}" /E /R:5 /W:1 /NFL /NDL /NJH /NJS >nul\r\n'
            f'start "" "{os.path.join(target_dir, "ArchForge.exe")}"\r\n'
            'del "%~f0"\r\n')
    return path


def run_install_script(path):
    import subprocess
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", path], creationflags=flags, close_fds=True)
