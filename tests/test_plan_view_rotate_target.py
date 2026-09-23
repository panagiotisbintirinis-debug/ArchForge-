from types import SimpleNamespace

from archforge.ui.plan_view import PlanView


class _Doc:
    def __init__(self):
        self.selection = ["stale"]

    def select(self, ids, add=False):
        self.selection = list(ids)


class _Controller:
    tool = "rotate"

    def __init__(self):
        self.target = ("stale", "old-handle")

    def set_target(self, entity_id, handle=None):
        self.target = (entity_id, handle)


class _Signal:
    def __init__(self):
        self.count = 0

    def emit(self):
        self.count += 1


def _view(entity_items):
    return SimpleNamespace(
        _entity_items=entity_items,
        doc=_Doc(),
        controller=_Controller(),
        selectionChangedByView=_Signal(),
    )


def test_rotate_tool_acquires_clicked_entity_and_clears_stale_target_on_empty_click():
    hit = object()
    view = _view({hit: "wall-2"})

    assert PlanView._acquire_rotate_target(view, hit) is True
    assert view.doc.selection == ["wall-2"]
    assert view.controller.target == ("wall-2", None)
    assert view.selectionChangedByView.count == 1

    empty = object()
    assert PlanView._acquire_rotate_target(view, empty) is False
    assert view.doc.selection == []
    assert view.controller.target == (None, None)
    assert view.selectionChangedByView.count == 2
