"""Λίστα εργασιών Α3 (Astra 28/10, κατηγορία Α): a damaged settings / price file is never overwritten blind.

Reproduced before the fix: a price book cut short (power loss, sync tool) + one new price = 1 of 50 prices left;
a damaged settings.json + one saved setting = every other setting (user materials included) gone.
"""
import glob
import json
import os

import pytest

from archforge.project import persistence
from archforge.quantities import price_book
from archforge.ui import autosave


@pytest.fixture(autouse=True)
def _clean_list():
    persistence.damaged_user_files()
    yield
    persistence.damaged_user_files()      # never leaks a warning into another test's window


def _fifty(path):
    text = json.dumps({"trade_prices": {f"c{i}": {"material": 10.0 + i, "labour": 5.0} for i in range(50)}})
    path.write_text(text[:-3], encoding="utf-8")         # cut short
    return text[:-3]


def test_a_cut_price_book_is_kept_before_a_new_price_is_saved(tmp_path):
    book = price_book.path()
    cut = _fifty(book)
    price_book.save({"new": {"material": 1.0, "labour": 1.0}})
    copies = glob.glob(str(book) + ".broken-*")
    assert len(copies) == 1
    assert open(copies[0], encoding="utf-8").read() == cut           # all 50 prices, byte for byte
    assert persistence.damaged_user_files() == [(os.path.abspath(book), copies[0])]
    assert price_book.load() == {"new": {"material": 1.0, "labour": 1.0}}


def test_settings_damaged_are_kept_before_one_setting_is_saved(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(autosave, "_settings_path", lambda: str(settings))
    damaged = '{"user_materials": {"m1": {}, "m2": {}}, "autosave_minutes": 3'
    settings.write_text(damaged, encoding="utf-8")
    assert autosave.load_settings() == {}
    autosave.save_settings({"recent": []})
    copies = glob.glob(str(settings) + ".broken-*")
    assert [open(c, encoding="utf-8").read() for c in copies] == [damaged]   # one copy, however often it is read
    assert json.loads(settings.read_text(encoding="utf-8")) == {"recent": []}


def test_a_file_that_cannot_even_be_read_is_not_written_over(tmp_path, monkeypatch):
    book = price_book.path()
    book.write_text(json.dumps({"trade_prices": {"a": {"material": 2.0, "labour": None}}}), encoding="utf-8")
    real_open = open

    def locked(path, *a, **k):
        if os.path.abspath(os.fspath(path)) == os.path.abspath(book):
            raise PermissionError("locked by another program")
        return real_open(path, *a, **k)
    monkeypatch.setattr("builtins.open", locked)
    with pytest.raises(persistence.UserDataError):
        price_book.save({"new": {"material": 1.0, "labour": 1.0}})
    monkeypatch.undo()
    assert json.loads(book.read_text(encoding="utf-8"))["trade_prices"] == {"a": {"material": 2.0, "labour": None}}


def test_a_missing_file_is_simply_empty(tmp_path):
    assert persistence.read_user_json(tmp_path / "none.json") == {}
    assert persistence.damaged_user_files() == []
