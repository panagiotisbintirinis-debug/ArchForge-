"""Owner 18/10: the packaged program must be updatable — it compares its build with the published release."""
import io
import os
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge import updates


def _release(sha, assets=True):
    return {"target_commitish": sha, "published_at": "2026-10-18T09:00:00Z",
            "assets": [{"name": updates.ASSET, "browser_download_url": "https://example/z.zip", "size": 200 << 20}] if assets else []}


def test_newer_release_is_offered_same_build_is_not():
    fetch = lambda _url: _release("bbb")
    assert updates.available_update({"sha": "aaa"}, fetch)["url"] == "https://example/z.zip"
    assert updates.available_update({"sha": "bbb"}, fetch) is None


def test_no_answer_no_package_or_source_run_offer_nothing():
    def offline(_url):
        raise OSError("no network")
    assert updates.available_update({"sha": "aaa"}, offline) is None
    assert updates.available_update({"sha": "aaa"}, lambda _u: _release("bbb", assets=False)) is None
    assert updates.available_update({}, lambda _u: _release("bbb")) is None
    assert not updates.packaged() and updates.current_build() is None      # tests run from source


def test_install_script_waits_copies_without_deleting_and_restarts(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.tempfile, "gettempdir", lambda: str(tmp_path))
    text = open(updates.install_script(r"C:\t\ArchForge", r"C:\Apps\ArchForge", 4242), encoding="utf-8").read()
    assert 'PID eq 4242' in text
    assert r'robocopy "C:\t\ArchForge" "C:\Apps\ArchForge" /E' in text and "/MIR" not in text
    assert "ArchForge.exe" in text.split("start", 1)[1]


def test_download_unpacks_the_folder_with_the_exe(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ArchForge/ArchForge.exe", b"MZ")
        z.writestr("ArchForge/_internal/samples/S01.archforge", b"{}")
    data = buf.getvalue()

    class Resp(io.BytesIO):
        headers = {"Content-Length": str(len(data))}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda *_a, **_k: Resp(data))
    seen = []
    folder = updates.download("https://example/z.zip", lambda d, t: seen.append((d, t)))
    assert os.path.isfile(os.path.join(folder, "ArchForge.exe")) and seen[-1] == (len(data), len(data))
