"""The main Prices dialog and trade quote must read one project price book."""
import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep.project_pricebook import project_prices, set_project_price
from archforge.mep.trade_costing import PriceEntry
from archforge.quantities.quote import trade_prices


def test_legacy_dialog_prices_are_visible_to_the_project_quote():
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('price_list', {'trade_prices': {'fixture': {'material': 1., 'labour': 2.}}, 'vat': 0.})))
    price = project_prices(doc)['fixture']
    assert price.material_unit_price == 1. and price.labour_unit_price == 2.


def test_canonical_trade_prices_are_visible_to_the_main_quote():
    doc = Document(); stack = CommandStack(doc)
    set_project_price(stack, doc, 'fixture', PriceEntry(1., 2., source='TEST_FIXTURE'))
    assert trade_prices(doc)['fixture'] == {'material': 1., 'labour': 2.}


def test_conflicting_duplicate_price_representations_are_reported():
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('price_list', {'trade_prices': {'fixture': {'material': 1., 'labour': 2.}},
                      'entries': {'fixture': {'material_unit_price': 9., 'labour_unit_price': 2.}}})))
    with pytest.raises(ValueError, match='conflicting'):
        project_prices(doc)


def test_editing_a_legacy_book_migrates_without_losing_unedited_prices():
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('price_list', {'trade_prices': {'one': {'material': 1., 'labour': 2.},
                                                                  'two': {'material': 3., 'labour': None}}})))
    before = doc.to_dict()
    set_project_price(stack, doc, 'one', PriceEntry(4., 5., source='TEST_FIXTURE'))
    prices = project_prices(doc)
    assert prices['one'].material_unit_price == 4.
    assert prices['two'].material_unit_price == 3. and prices['two'].labour_unit_price is None
    stack.undo()
    assert doc.to_dict() == before
