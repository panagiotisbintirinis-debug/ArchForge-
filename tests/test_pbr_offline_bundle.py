import re

from archforge.ui.pbr_viewport import _THREE_BUNDLE_PATH, pbr_page_html


def test_3d_scene_page_needs_no_internet():
    html = pbr_page_html()
    # No remote scripts/stylesheets/imports (the desktop app must work offline).
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', html)
    assert 'cdn.jsdelivr' not in html and 'importmap' not in html
    assert 'window.__ARCHFORGE_THREE' in html
    # QtWebEngine's setHtml() is limited to 2 MB.
    assert len(html.encode('utf-8')) < 2 * 1024 * 1024


def test_bundled_three_is_present_and_inline_safe():
    text = _THREE_BUNDLE_PATH.read_text(encoding='utf-8')
    assert '</script' not in text
    assert 'window.__ARCHFORGE_THREE' in text
    assert (_THREE_BUNDLE_PATH.parent / 'THREE_LICENSE.txt').exists()
