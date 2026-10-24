"""Test isolation: the common price book (quantities/price_book.py) lives in the user's data folder —
tests never read or write the real one."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_price_book(tmp_path, monkeypatch):
    from archforge.quantities import price_book
    monkeypatch.setattr(price_book, "path", lambda: tmp_path / "price_book.json")


@pytest.fixture(autouse=True, scope="module")
def _release_windows():
    """Windows a test file opened are deleted when the file ends.

    109 test files open ``MainWindow()`` and never close it; each keeps its 3D view (QtWebEngine) and its
    renderer processes alive, so a full run grew to hundreds of processes and ~16 GB and was killed without
    a message.  Per file, not per test: tests in one file may share a window.  ``deleteLater`` without
    ``close()`` so no «unsaved changes» question is asked.
    """
    from PySide6.QtWidgets import QApplication
    from shiboken6 import getCppPointer
    key = lambda w: getCppPointer(w)[0]
    app = QApplication.instance()
    before = set(map(key, app.topLevelWidgets())) if app is not None else set()
    yield
    app = QApplication.instance()
    if app is None:
        return
    from PySide6.QtCore import QEvent
    for w in app.topLevelWidgets():
        if key(w) not in before:
            w.hide()
            w.deleteLater()
    for _ in range(3):
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
