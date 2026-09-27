import subprocess
import sys
import textwrap


def test_pbr_viewport_treats_webengine_import_error_as_unavailable():
    """A broken optional Qt WebEngine binary must not prevent ArchForge import."""
    script = textwrap.dedent(
        """
        import builtins

        real_import = builtins.__import__

        def import_without_webengine(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "PySide6.QtWebEngineWidgets":
                raise ImportError("simulated missing native WebEngine dependency")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = import_without_webengine

        import archforge.ui.pbr_viewport as pbr_viewport

        assert pbr_viewport.QWebEngineView is None
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
