"""Synthetic fixtures: adapter contracts, not engineering validation."""
import copy
import pytest
from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack, UpdateEntity
from archforge.ui.object_properties import property_changes
from archforge.orchestration.ollama import ProjectContext, ProjectAssistant, OllamaError


def project():
    doc = Document()
    for z in (0., 3.):
        doc.add(Entity('wall', {'x1': 0., 'y1': 0., 'x2': 4., 'y2': 0.,
                               'z': z, 'height': 2.7, 'thickness': .15}, name=f'Wall {z}'))
    return doc


def test_snapshot_reads_unselected_upper_floor_and_relationships():
    doc = project()
    before = copy.deepcopy(doc.to_dict())
    context = ProjectContext(doc)
    first = context.call('list_entities', {'offset': 0, 'limit': 1})
    second = context.call('list_entities', {'offset': first['next_offset'], 'limit': 1})
    eid = second['items'][0]['id']
    assert context.call('inspect_entity', {'entity_id': eid})['params']['z'] == 3
    assert doc.to_dict() == before
    doc.update(eid, {'height': 3.5})
    assert context.call('inspect_entity', {'entity_id': eid})['params']['height'] == 2.7


def test_proposal_is_read_only_then_same_manual_command_with_undo():
    doc = project(); eid = next(iter(doc.entities))
    original = copy.deepcopy(doc.to_dict())
    context = ProjectContext(doc)
    result = context.call('propose_properties', {'entity_id': eid, 'values': {'length': 5.9}, 'reason': 'Requested length'})
    assert result['status'] == 'pending_user_apply'
    assert doc.to_dict() == original
    manual = Document.from_dict(copy.deepcopy(original))
    CommandStack(manual).execute(UpdateEntity(eid, property_changes(manual.get(eid), {'length': 5.9})))
    stack = CommandStack(doc)
    stack.execute(context.proposal.build(doc))
    assert doc.to_dict() == manual.to_dict()
    stack.undo()
    assert doc.to_dict() == original
    stack.redo()
    assert doc.to_dict() == manual.to_dict()


def test_stale_proposal_cannot_overwrite_a_later_manual_edit():
    doc = project(); eid = next(iter(doc.entities)); context = ProjectContext(doc)
    context.call('propose_properties', {'entity_id': eid, 'values': {'height': 3.}, 'reason': 'test'})
    doc.update(eid, {'height': 2.9})
    with pytest.raises(OllamaError, match='άλλαξε'):
        context.proposal.build(doc)
    assert doc.get(eid).params['height'] == 2.9


@pytest.mark.parametrize('values', [{'height': float('nan')}, {'height': -1}, {'surprise': 1}, {'height': True}])
def test_invalid_changes_do_not_become_proposals(values):
    doc = project(); context = ProjectContext(doc)
    with pytest.raises((OllamaError, ValueError)):
        context.call('propose_properties', {'entity_id': next(iter(doc.entities)), 'values': values, 'reason': 'test'})
    assert context.proposal is None


def test_locked_entity_and_unknown_tool_rejected():
    doc = project(); eid = next(iter(doc.entities)); doc.get(eid).locked = True
    context = ProjectContext(doc)
    with pytest.raises(OllamaError):
        context.call('propose_properties', {'entity_id': eid, 'values': {'height': 3.}, 'reason': 'test'})
    with pytest.raises(OllamaError):
        context.call('execute_python', {'code': 'print(1)'})


class FakeClient:
    model = 'synthetic-test-model'
    def __init__(self, replies):
        self.replies = iter(replies); self.requests = []
    def chat(self, messages, tools):
        self.requests.append(copy.deepcopy(messages))
        return next(self.replies)


def call(name, **args):
    return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': name, 'arguments': args}}]}


def test_tool_loop_provides_evidence_without_mutations():
    doc = project(); original = copy.deepcopy(doc.to_dict())
    client = FakeClient([call('list_entities', offset=0, limit=20), {'role': 'assistant', 'content': 'Βρήκα δύο τοίχους.'}])
    answer = ProjectAssistant(client).ask(ProjectContext(doc), 'Τι υπάρχει στο έργο;')
    assert answer.text == 'Βρήκα δύο τοίχους.'
    assert any(e['tool'] == 'list_entities' for e in answer.evidence)
    assert client.requests[1][-1]['role'] == 'tool'
    assert doc.to_dict() == original


def test_tool_loop_has_finite_limit():
    client = FakeClient([call('overview')] * 20)
    with pytest.raises(OllamaError, match='όριο'):
        ProjectAssistant(client, max_rounds=2).ask(ProjectContext(project()), 'inspect')


def test_project_paths_are_paged_and_never_disk_paths():
    context = ProjectContext(project())
    assert context.call('read_project', {'path': ['entities'], 'limit': 1})['next_offset'] == 1
    assert context.call('read_project', {'path': ['entities', 1, 'params', 'z']}) == {'value': 3.}
    with pytest.raises((KeyError, OllamaError)):
        context.call('read_project', {'path': ['/etc/passwd']})
    assert context.call('program_help', {'limit': 1})['source'].startswith('docs/TOOLBOX.md')


def test_transport_checks_model_support_and_context_without_guessing(monkeypatch):
    from archforge.orchestration.ollama import OllamaClient
    monkeypatch.delenv('ARCHFORGE_OLLAMA_MODEL', raising=False)
    client = OllamaClient()
    responses = {'/api/tags': {'models': [{'name': 'fixture'}]},
                 '/api/show': {'capabilities': ['tools'], 'model_info': {'fixture.context_length': 32768}},
                 '/api/chat': {'done': True, 'message': {'role': 'assistant', 'content': 'ok'}}}
    calls = []
    def request(path, data=None):
        calls.append((path, data)); return responses[path]
    monkeypatch.setattr(client, 'request', request)
    assert client.chat([{'role': 'user', 'content': 'test'}], [])['content'] == 'ok'
    assert client.model == 'fixture' and calls[-1][1]['stream'] is False
    with pytest.raises(OllamaError, match='context'):
        client.chat([{'role': 'user', 'content': 'x' * 20000}], [])
    responses['/api/chat']['done_reason'] = 'length'
    with pytest.raises(OllamaError, match='ολοκληρώθηκε'):
        client.chat([], [])
    client._ready = False
    responses['/api/show']['capabilities'] = ['completion']
    with pytest.raises(OllamaError, match='tools'):
        client.prepare()
    responses['/api/tags']['models'].append({'name': 'other'})
    client.model = ''
    with pytest.raises(OllamaError, match='ARCHFORGE_OLLAMA_MODEL'):
        client.prepare()


@pytest.mark.parametrize('url', ['https://example.org', 'http://user:pass@localhost:11434', 'http://localhost:11434/api'])
def test_external_endpoints_rejected(url):
    from archforge.orchestration.ollama import OllamaClient
    with pytest.raises(OllamaError):
        OllamaClient(base_url=url)


def test_real_http_shape_with_local_fixture_server():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from archforge.orchestration.ollama import OllamaClient
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(b'{"models":[{"name":"fixture"}]}')
        def log_message(self, *args):
            pass  # Test-only HTTP fixture.
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        assert OllamaClient(base_url=f'http://127.0.0.1:{server.server_port}').models() == ['fixture']
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_existing_panel_async_ask_apply_undo_and_stale_reply(monkeypatch):
    import threading
    import time
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui import ollama_assistant as ui
    from archforge.orchestration.ollama import Answer
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    # Owner requested in-panel activation; exercise the real provider selector.
    window.assistant_provider.setCurrentIndex(1)
    release = threading.Event(); entered = threading.Event()
    try:
        from archforge.core.commands import AddEntity
        entity = next(iter(project().entities.values()))
        window.stack.execute(AddEntity(entity))
        window._refresh_assistant()
        original = copy.deepcopy(window.doc.to_dict())
        def fake_ask(self, context, question, history=()):
            assert threading.current_thread() is not threading.main_thread()
            entered.set()
            assert release.wait(5)
            context.call('propose_properties', {'entity_id': entity.id, 'values': {'height': 3.}, 'reason': '<b>user request</b>'})
            return Answer('Έτοιμη πρόταση', context.evidence, context.proposal)
        monkeypatch.setattr(ui.ProjectAssistant, 'ask', fake_ask)
        window.assistant_text.setText('Άλλαξε το ύψος σε 3 m')
        window._assistant_ask()
        assert entered.wait(2)
        assert window.doc.to_dict() == original
        release.set()
        deadline = time.monotonic() + 5
        while window._ollama_controller._job is not None and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.01)
        assert window._ollama_controller._job is None
        assert window._assistant_proposals[0].key.startswith('ollama:')
        assert '&lt;b&gt;' in window._assistant_proposals[0].detail
        window.assistant_list.setCurrentRow(0)
        window._apply_assistant_proposal()
        assert window.doc.get(entity.id).params['height'] == 3.
        window.stack.undo()
        assert window.doc.to_dict() == original
        # A manual edit during a later request invalidates the answer and its proposal.
        release.clear(); entered.clear()
        window.assistant_text.setText('Πάλι')
        window._assistant_ask(); assert entered.wait(2)
        window.stack.execute(UpdateEntity(entity.id, {'height': 2.9}))
        release.set()
        deadline = time.monotonic() + 5
        while window._ollama_controller._job is not None and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.01)
        assert 'παλιά απάντηση απορρίφθηκε' in window.assistant_reply.text()
        assert ui.pending_proposal(window) is None
    finally:
        release.set()
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone(6000)
        app.processEvents()
        window._mark_clean(); window.close(); app.processEvents()


def test_launcher_restores_panel_and_connection_selector(monkeypatch):
    import time
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.assistant_panel import OllamaClient
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.show(); app.processEvents()
        window._assistant_dock.hide(); app.processEvents()
        QTest.mouseClick(window.assistant_launcher, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert window._assistant_dock.isVisible()
        assert window.assistant_pages.tabText(0) == 'Συνομιλία'
        assert window.assistant_tools_layout.count() == 2
        window._layout_assist.start('kitchen')
        assert window.assistant_pages.currentWidget() is window.assistant_arrangement_page
        QTest.mouseClick(window.assistant_launcher, Qt.MouseButton.LeftButton)
        assert window.assistant_pages.currentIndex() == 0
        monkeypatch.setattr(OllamaClient, 'models', lambda self: ['fixture-a', 'fixture-b'])
        QTest.mouseClick(window.assistant_connect, Qt.MouseButton.LeftButton)
        deadline = time.monotonic() + 3
        while window._assistant_connection_controller.job is not None and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.01)
        assert window.assistant_model.count() == 2
        assert window.assistant_model.currentIndex() == -1  # User chooses; no guessed model.
        assert window.assistant_provider.currentIndex() == 1
        assert '2 μοντέλα' in window.assistant_connection.text()
        window.assistant_reply.add_message('ΕΣΥ', '<script>literal text</script>')
        window.assistant_reply.setText('Δεύτερη απάντηση')
        assert '<script>literal text</script>' in window.assistant_reply.toPlainText()
        assert 'Δεύτερη απάντηση' in window.assistant_reply.toPlainText()
    finally:
        window._mark_clean(); window.close(); app.processEvents()
