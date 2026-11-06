"""Remembered results (core/state_memo.py, wall bands, room bindings) never cross from one document to another."""
import copy
import gc

from archforge.core.model import Document, Entity
from archforge.core.state_memo import doc_token, state_key


def test_a_new_document_never_gets_an_old_ones_key_even_at_the_same_address():
    keys = set()
    for _ in range(50):                      # freed documents: their addresses get reused
        d = Document()
        keys.add(state_key(d)); del d; gc.collect()
    assert len(keys) == 50


def test_a_copy_has_its_own_token():
    d = Document(); d.add(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 3, 'y2': 0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    c = copy.deepcopy(d)
    assert doc_token(c) != doc_token(d) and doc_token(d) == doc_token(d)
