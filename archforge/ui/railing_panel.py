"""Ιδιότητες κάγκελου: Greek rows of the Inspector for a ``railing`` entity.

Every edit goes through ``UpdateEntity`` on the window's command stack (one
undo each); a rejected value (e.g. a clear gap over 11 cm) leaves the
Document unchanged and says why in the status bar.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLabel

from archforge.architecture import railings as R
from archforge.core.commands import UpdateEntity

_RANGES = {'height': (0.3, 3.0), 'handrail_size': (0.02, 0.40), 'post_spacing': (0.3, R.MAX_POST_SPACING),
           'gap': (0.02, R.MAX_GAP), 'base_height': (0.0, 2.7), 'z': (-100.0, 1000.0)}


def type_changes(params, railing_type):
    """Changing the type also brings that type's handrail and finish."""
    spec = R.TYPES[railing_type]
    return {'railing_type': railing_type, 'handrail': spec['handrail'], 'handrail_size': spec['size'], 'metal': spec['metal']}


def apply(window, eid, changes):
    try:
        window.stack.execute(UpdateEntity(eid, changes))
    except (ValueError, KeyError) as exc:
        window.statusBar().showMessage(f'Κάγκελο: η τιμή δεν έγινε δεκτή — {exc}', 6000)
    window._redraw_views(all_views=True)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window.refresh_inspector)      # rebuild the form outside the widget's signal


def summary(params):
    posts = len(R.post_positions(params))
    gap = R.max_clear_gap(params)
    lines = [f"{R.length(params):.2f} τρέχοντα μέτρα · {posts} ορθοστάτες"]
    if gap:
        lines.append(f"Μέγιστο καθαρό κενό {gap * 100:.1f} cm (όριο {R.MAX_GAP * 100:.0f} cm)")
    if params['railing_type'] in ('bars', 'cable'):
        lines.append('⚠ Οριζόντια πλήρωση: σκαρφαλώνεται — όχι όπου παίζουν μικρά παιδιά')
    lines.append('<i>Ύψος ≥ 1,00 m σε μπαλκόνια/δώματα, 0,90 m πάνω από τη μύτη σκαλοπατιού · '
                 'κενό ≤ 10–11 cm (ΝΟΚ / Κτιριοδομικός, πρακτική — προς έλεγχο)</i>')
    return '<br>'.join(lines)


def add_railing_rows(window, eid):
    form, p = window.form, dict(window.doc.get(eid).params)

    def combo(label, options, current, on_change):
        box = QComboBox()
        for value, text in options.items():
            box.addItem(text, value)
        box.setCurrentIndex(max(0, box.findData(current)))
        box.currentIndexChanged.connect(lambda _i, w=box: on_change(w.currentData()))
        form.addRow(label, box)
        return box

    combo('Τύπος κάγκελου', {k: v['label'] for k, v in R.TYPES.items()}, p['railing_type'],
          lambda v: v != p['railing_type'] and apply(window, eid, type_changes(p, v)))
    combo('Κουπαστή', R.HANDRAILS, p.get('handrail'),
          lambda v: v != p.get('handrail') and apply(window, eid, {'handrail': v}))
    if p['railing_type'] not in ('timber', 'parapet'):
        combo('Μέταλλο', R.METALS, p.get('metal'), lambda v: v != p.get('metal') and apply(window, eid, {'metal': v}))
    for key, label in R.PARAM_NAMES.items():
        if key not in p:
            continue
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(*_RANGES[key])
        spin.setSingleStep(0.01)
        spin.setValue(float(p[key]))
        spin.editingFinished.connect(
            lambda k=key, w=spin: abs(w.value() - float(p[k])) > 1e-9 and apply(window, eid, {k: w.value()}))
        form.addRow(label, spin)
    # Finishes per role: the type's default or a palette material (surface_materials[role]).
    from archforge.rendering.materials import MATERIAL_PRESETS
    present = sorted(set(R.railing_mesh(p)[2]), key=R.ROLES.index)
    current = dict(p.get('surface_materials') or {})
    for role in present:
        options = {'': 'Του τύπου'} | {mid: spec['name'] for mid, spec in MATERIAL_PRESETS.items()}

        def set_role(v, role=role):
            if (current.get(role) or '') == (v or ''):
                return
            mats = dict(current)
            if v:
                mats[role] = v
            else:
                mats.pop(role, None)
            apply(window, eid, {'surface_materials': mats})
        combo(f'Υλικό: {R.ROLE_NAMES[role]}', options, current.get(role, ''), set_role)
    info = QLabel(summary(p))
    info.setWordWrap(True)
    form.addRow('', info)
