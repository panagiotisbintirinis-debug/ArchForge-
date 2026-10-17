"""Common price book (owner 17/10): saved once, prices every project; the project's own price wins."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.quantities import price_book
from archforge.quantities.quote import costed, price_source


def _project(prices):
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(Entity('price_list', {'trade_prices': prices}, name='Τιμές')))
    return doc


def test_saved_prices_reach_every_project_and_project_prices_win():
    assert price_book.load() == {}                                       # starts empty: nothing invented
    a = _project({'x.code': {'material': 10.0, 'labour': 4.0}})
    assert price_book.save_project_prices(a) == 1
    other = Document()
    row = costed(other, 't', [('Είδος', 'τεμ.', 3.0, {'code': 'x.code'})])[0]
    assert row['amount'] == 42.0 and row['material'] == 30.0 and row['labour'] == 12.0
    assert row['price_source'] == 'κοινός τιμοκατάλογος' and price_source(other, 'x.code') == 'κοινός τιμοκατάλογος'
    own = _project({'x.code': {'material': 1.0, 'labour': 1.0}})
    assert costed(own, 't', [('Είδος', 'τεμ.', 3.0, {'code': 'x.code'})])[0]['amount'] == 6.0
    assert price_source(own, 'x.code') == 'έργο'
    missing = costed(other, 't', [('Άλλο', 'τεμ.', 1.0, {'code': 'never'})])[0]
    assert missing['amount'] is None and missing['price_source'] is None


def test_unreadable_book_is_empty_not_guessed(tmp_path):
    price_book.path().write_text('{not json', encoding='utf-8')
    assert price_book.load() == {}
