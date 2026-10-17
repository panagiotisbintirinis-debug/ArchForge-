"""Test isolation: the common price book (quantities/price_book.py) lives in the user's data folder —
tests never read or write the real one."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_price_book(tmp_path, monkeypatch):
    from archforge.quantities import price_book
    monkeypatch.setattr(price_book, "path", lambda: tmp_path / "price_book.json")
