from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def verify_human_runtime_linkage():
    main_window = ROOT / 'archforge' / 'ui' / 'main_window.py'
    plan_view = ROOT / 'archforge' / 'ui' / 'plan_view.py'
    viewport_3d = ROOT / 'archforge' / 'ui' / 'viewport_3d.py'
    commands = ROOT / 'archforge' / 'core' / 'commands.py'

    required_files = (main_window, plan_view, viewport_3d, commands)
    if any(not path.exists() for path in required_files):
        return False

    main = main_window.read_text(encoding='utf-8')
    plan = plan_view.read_text(encoding='utf-8')
    view3d = viewport_3d.read_text(encoding='utf-8')
    core = commands.read_text(encoding='utf-8')

    required_main = (
        'valueChanged.connect',
        'MutateEntityProperty',
        'self.stack.execute(',
        "self.tool_actions[text] = action",
        "self.plan_view.set_tool('wall')",
        "self.view_3d.set_tool('wall')",
    )
    required_plan = (
        'def mousePressEvent(self,event):',
        'self.controller.pointer_down',
        'self.controller.pointer_up',
    )
    required_3d = (
        'def mousePressEvent(self, event):',
        "if self.active_tool == 'wall'",
        'self.controller.pointer_down',
        'self.controller.pointer_up',
        '_screen_to_work_plane_event',
    )
    required_core = (
        'class MutateEntityProperty(Command):',
        'doc.update(',
    )

    if any(token not in main for token in required_main):
        return False
    if any(token not in plan for token in required_plan):
        return False
    if any(token not in view3d for token in required_3d):
        return False
    if any(token not in core for token in required_core):
        return False

    dead_patterns = (
        'pass  # TODO',
        "print('clicked')",
        'FAKE_UI_PLACEHOLDER',
    )
    checked_ui = '\n'.join((main, plan, view3d))
    if any(pattern in checked_ui for pattern in dead_patterns):
        return False

    return True


if __name__ == '__main__':
    if not verify_human_runtime_linkage():
        print('!!! COMPLIANCE FAILURE: HUMAN UI LINKAGE IS INCOMPLETE !!!')
        print('CI is terminated before tests. Repository branches are left intact.')
        sys.exit(2)

    print('SUCCESS: Human-UI linkage verified. Proceeding to validation.')
